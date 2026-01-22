import os
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text
import plotly.express as px

# ==========================================
# 1. BRANDING & UI DESIGN
# ==========================================
APP_NAME = "Astra Defect Tracker"
st.set_page_config(page_title=APP_NAME, page_icon="🛡️", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #f0f2f6; }
    .metric-card {
        border-radius: 12px; padding: 20px; color: white; margin-bottom: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.15);
    }
    .global-bucket { background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%); }
    .open-bucket { background: linear-gradient(135deg, #ea580c 0%, #fb923c 100%); }
    .resolved-bucket { background: linear-gradient(135deg, #166534 0%, #22c55e 100%); }

    div[data-testid="stButton"] > button {
        background-color: #064e3b !important;
        color: white !important;
        font-weight: 700 !important;
        border-radius: 4px !important;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. CONSTANTS & UTILITIES
# ==========================================
MODULES = ["PLM", "PP", "FI", "SD", "MM", "QM", "ABAP", "BASIS", "OTHER"]
PRIORITIES = ["P1 - Critical", "P2 - High", "P3 - Medium", "P4 - Low"]
STATUSES = ["New", "In Progress", "Blocked", "Resolved", "Closed", "Reopened"]
CATEGORIES = ["Functional", "UI/UX", "Data", "Security", "Performance"]
ENVS = ["Production", "UAT", "QA", "Development"]
AGENTS = ["Unassigned", "Sarah Jenkins", "David Chen", "Maria Garcia", "Kevin Lee"]

DISPLAY_COLS = [
    "id", "defect_title", "module", "category", "environment", "priority",
    "reported_by", "reporter_email", "assigned_to", "status"
]
REQUIRED_COLS = set(DISPLAY_COLS + ["description", "comments"])

def _get_db_url() -> str:
    db_url = st.secrets.get("SUPABASE_DATABASE_URL") if hasattr(st, "secrets") else None
    db_url = db_url or os.getenv("SUPABASE_DATABASE_URL")
    if not db_url:
        st.error("Missing SUPABASE_DATABASE_URL in Streamlit secrets or environment variables.")
        st.stop()
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
    return db_url

@st.cache_resource
def get_engine():
    return create_engine(_get_db_url(), pool_pre_ping=True)

@st.cache_data(ttl=60)
def load_data() -> pd.DataFrame:
    try:
        with get_engine().connect() as conn:
            df = pd.read_sql(text("SELECT * FROM public.defects ORDER BY id DESC"), conn)

        if df.empty:
            return df

        # Ensure required columns exist and are safe for string ops
        for c in REQUIRED_COLS:
            if c not in df.columns:
                df[c] = ""

        # Normalize id
        df["id"] = pd.to_numeric(df["id"], errors="coerce").astype("Int64").astype(str)

        # Fill NA across all required columns to avoid search / UI bugs
        for c in REQUIRED_COLS:
            df[c] = df[c].fillna("")

        return df
    except Exception as e:
        st.warning(f"Could not load data from DB: {e}")
        return pd.DataFrame(columns=list(REQUIRED_COLS))

# ✅ FIXED SEARCH (literal match, not regex)
def fast_search(df: pd.DataFrame, q: str) -> pd.DataFrame:
    q = (q or "").strip().lower()
    if not q or df.empty:
        return df
    cols = [c for c in DISPLAY_COLS if c in df.columns]
    haystack = df[cols].astype(str).agg(" | ".join, axis=1).str.lower()
    # IMPORTANT: regex=False makes search literal and stable
    return df[haystack.str.contains(q, na=False, regex=False)]

# ==========================================
# 3. SIDEBAR
# ==========================================
with st.sidebar:
    st.header("⚙️ System Controls")
    if st.button("🔄 SYNC DATA NOW", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.info("Force a refresh to pull the latest records from the Astra database.")

    st.divider()
    st.markdown("### 📖 Standard Operating Procedure")
    st.write("**1. Registration:** Use '+ ADD NEW' to log a ticket.")
    st.write("**2. Modification:** Click a row in the table to edit.")
    st.write("**3. Assignment:** Select an Agent for workload tracking.")

# ==========================================
# 4. SESSION STATE
# ==========================================
if "editing_id" not in st.session_state:
    st.session_state.editing_id = None

# ==========================================
# 5. DIALOGS
# ==========================================
@st.dialog("➕ Create New Defect")
def create_defect_dialog():
    with st.form("create_form", clear_on_submit=True):
        st.write("### 📝 New Registration")
        title_in = st.text_input("Summary *")
        c1, c2, c3 = st.columns(3)
        mod_in = c1.selectbox("Module", MODULES)
        cat_in = c2.selectbox("Category", CATEGORIES)
        env_in = c3.selectbox("Environment", ENVS)

        c4, c5 = st.columns(2)
        pri_in = c4.selectbox("Priority", PRIORITIES)
        name_in = c5.text_input("Reporter Name *")

        email_in = st.text_input("Reporter Email *")
        desc_in = st.text_area("Initial Description")

        submitted = st.form_submit_button("Submit to Astra", use_container_width=True)
        if submitted:
            t = (title_in or "").strip()
            n = (name_in or "").strip()
            e = (email_in or "").strip()

            if not t or not n or "@" not in e:
                st.error("Validation Error: Please provide valid Summary, Name, and Email.")
                return

            with get_engine().begin() as conn:
                conn.execute(
                    text("""
                        INSERT INTO public.defects
                        (defect_title, module, priority, category, environment,
                         reported_by, reporter_email, description, status, assigned_to)
                        VALUES (:t, :m, :p, :c, :env, :rn, :re, :d, 'New', 'Unassigned')
                    """),
                    {"t": t, "m": mod_in, "p": pri_in, "c": cat_in, "env": env_in,
                     "rn": n, "re": e, "d": desc_in}
                )

            st.cache_data.clear()
            st.rerun()

@st.dialog("✏️ Modify Defect")
def edit_defect_dialog(record: dict):
    with st.form("edit_form"):
        st.markdown(f"### 📑 Record ID: {record.get('id','')}")

        new_title = st.text_input("Summary", value=str(record.get("defect_title", "")))

        c1, c2, c3 = st.columns(3)
        old_status = str(record.get("status", "New"))
        old_priority = str(record.get("priority", PRIORITIES[0]))
        old_agent = str(record.get("assigned_to", "Unassigned"))

        new_status = c1.selectbox(
            "Status",
            STATUSES,
            index=STATUSES.index(old_status) if old_status in STATUSES else 0
        )
        new_pri = c2.selectbox(
            "Priority",
            PRIORITIES,
            index=PRIORITIES.index(old_priority) if old_priority in PRIORITIES else 0
        )
        new_assign = c3.selectbox(
            "Assigned To Agent",
            AGENTS,
            index=AGENTS.index(old_agent) if old_agent in AGENTS else 0
        )

        st.write("---")
        new_desc = st.text_area("Description", value=str(record.get("description", "")))
        new_comm = st.text_area("Comments", value=str(record.get("comments", "")))

        b1, b2 = st.columns(2)
        save_clicked = b1.form_submit_button("💾 Save Changes", use_container_width=True, key="save_btn")
        cancel_clicked = b2.form_submit_button("✖️ Cancel", use_container_width=True, key="cancel_btn")

        if cancel_clicked:
            st.session_state.editing_id = None
            st.rerun()

        if save_clicked:
            rec_id_str = str(record.get("id", "")).strip()
            rec_id_int = int(float(rec_id_str))  # handles "12", "12.0", etc.

            try:
                with get_engine().begin() as conn:
                    conn.execute(
                        text("""
                            UPDATE public.defects SET
                                defect_title = :t,
                                status       = :s,
                                priority     = :p,
                                assigned_to  = :a,
                                description  = :d,
                                comments     = :c,
                                updated_at   = NOW()
                            WHERE id = :id
                        """),
                        {"t": new_title, "s": new_status, "p": new_pri, "a": new_assign,
                         "d": new_desc, "c": new_comm, "id": rec_id_int}
                    )

                st.toast(f"✅ Record {rec_id_str} Updated!", icon="🛡️")
                st.cache_data.clear()
                st.session_state.editing_id = None
                st.rerun()
            except Exception as e:
                st.error(f"❌ Save Failed: {e}")

# ==========================================
# 6. MAIN UI
# ==========================================
df = load_data()

st.title(f"🛡️ {APP_NAME}")

if not df.empty:
    k1, k2, k3 = st.columns(3)
    k1.markdown(
        f'<div class="metric-card global-bucket"><h3>Global Items</h3><h1>{len(df)}</h1></div>',
        unsafe_allow_html=True
    )
    active = df[~df["status"].isin(["Resolved", "Closed"])]
    resolved = df[df["status"].isin(["Resolved", "Closed"])]
    k2.markdown(
        f'<div class="metric-card open-bucket"><h3>Active</h3><h1>{len(active)}</h1></div>',
        unsafe_allow_html=True
    )
    k3.markdown(
        f'<div class="metric-card resolved-bucket"><h3>Resolved Total</h3><h1>{len(resolved)}</h1></div>',
        unsafe_allow_html=True
    )
else:
    st.info("Database is empty. Add a new defect to begin.")

st.divider()

tab_tracker, tab_insights = st.tabs(["📂 Defect Tracker", "📊 Performance Insights"])

with tab_tracker:
    st.subheader("Action Registry")
    st.info("💡 **Instructions:** Click any row below to modify the record or assign an agent.")

    if st.button("➕ ADD NEW DEFECT"):
        create_defect_dialog()

    search = st.text_input("🔍 Quick Filter", placeholder="Search registry...")
    disp_df = fast_search(df, search)

    if not disp_df.empty:
        event = st.dataframe(
            disp_df[[c for c in DISPLAY_COLS if c in disp_df.columns]],
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            column_config={
                "id": st.column_config.TextColumn("ID"),
                "defect_title": st.column_config.TextColumn("Summary")
            }
        )

        if event and getattr(event, "selection", None) and event.selection.rows:
            selected_row = event.selection.rows[0]
            selected_id = disp_df.iloc[selected_row]["id"]
            st.session_state.editing_id = selected_id
            st.rerun()
    else:
        st.warning("No matching records found.")

    if st.session_state.editing_id and not df.empty:
        rec = df[df["id"] == st.session_state.editing_id]
        if not rec.empty:
            edit_defect_dialog(rec.iloc[0].to_dict())
        else:
            st.session_state.editing_id = None

with tab_insights:
    st.header("📊 Performance Insights")
    if not df.empty:
        c1, c2, c3 = st.columns(3)
        dim_options = {
            "module": "Module",
            "priority": "Priority",
            "status": "Status",
            "category": "Category",
            "environment": "Env",
        }
        primary_dim = c1.selectbox(
            "1. Analysis Dimension",
            options=list(dim_options.keys()),
            format_func=lambda x: dim_options[x]
        )
        unique_vals = sorted([v for v in df[primary_dim].dropna().unique().tolist()])
        selected_val = c2.selectbox(
            f"2. Filter Specific {dim_options[primary_dim]}",
            options=["All Data"] + unique_vals
        )
        pivot_dim = c3.selectbox(
            "3. Pivot/Compare By",
            options=[opt for opt in dim_options.keys() if opt != primary_dim],
            format_func=lambda x: dim_options[x]
        )

        chart_df = df if selected_val == "All Data" else df[df[primary_dim] == selected_val]
        st.divider()

        g1, g2 = st.columns(2)
        fig_bar = px.bar(
            chart_df.groupby(pivot_dim).size().reset_index(name="Count"),
            x=pivot_dim, y="Count", color=pivot_dim,
            title=f"Volume by {dim_options[pivot_dim]}"
        )
        g1.plotly_chart(fig_bar, use_container_width=True)

        fig_pie = px.pie(
            chart_df, names=pivot_dim, hole=0.5,
            title=f"% Distribution of {dim_options[pivot_dim]}"
        )
        g2.plotly_chart(fig_pie, use_container_width=True)

        st.subheader("👤 Agent Workload by Status")
        agent_status_df = df.groupby(["assigned_to", "status"]).size().reset_index(name="Items")

        fig_agent = px.bar(
            agent_status_df,
            x="Items",
            y="assigned_to",
            color="status",
            orientation="h",
            text_auto=True,
            title="Workload Distribution & Progress Status",
        )
       fig_agent.update_layout(barmode="stack", legend_title_text="Status Legend")
        st.plotly_chart(fig_agent, use_container_width=True)
    else:
        st.warning("No data for insights.")
