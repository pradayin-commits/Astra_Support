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
# 2. CONSTANTS
# ==========================================
MODULES = ["PLM", "PP", "FI", "SD", "MM", "QM", "ABAP", "BASIS", "OTHER"]
PRIORITIES = ["P1 - Critical", "P2 - High", "P3 - Medium", "P4 - Low"]
STATUSES = ["New", "In Progress", "Blocked", "Resolved", "Closed", "Reopened"]
CATEGORIES = ["Functional", "UI/UX", "Data", "Security", "Performance"]
ENVS = ["Production", "UAT", "QA", "Development"]
AGENTS = ["Unassigned", "Sarah Jenkins", "David Chen", "Maria Garcia", "Kevin Lee"]

DISPLAY_COLS = [
    "id", "defect_title", "module", "category", "environment",
    "priority", "reported_by", "reporter_email", "assigned_to", "status"
]

REQUIRED_COLS = set(DISPLAY_COLS + ["description", "comments"])

# ==========================================
# 3. DATABASE
# ==========================================
def get_db_url():
    url = st.secrets.get("SUPABASE_DATABASE_URL") if hasattr(st, "secrets") else None
    url = url or os.getenv("SUPABASE_DATABASE_URL")
    if not url:
        st.error("SUPABASE_DATABASE_URL not found")
        st.stop()
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg2://", 1)
    return url

@st.cache_resource
def get_engine():
    return create_engine(get_db_url(), pool_pre_ping=True)

@st.cache_data(ttl=60)
def load_data():
    try:
        with get_engine().connect() as conn:
            df = pd.read_sql("SELECT * FROM public.defects ORDER BY id DESC", conn)

        for col in REQUIRED_COLS:
            if col not in df.columns:
                df[col] = ""
            df[col] = df[col].fillna("")

        df["id"] = pd.to_numeric(df["id"], errors="coerce").astype("Int64").astype(str)
        return df
    except Exception as e:
        st.warning(e)
        return pd.DataFrame(columns=list(REQUIRED_COLS))

# ==========================================
# 4. SEARCH (FIXED)
# ==========================================
def fast_search(df, q):
    q = (q or "").strip().lower()
    if not q or df.empty:
        return df
    cols = [c for c in DISPLAY_COLS if c in df.columns]
    haystack = df[cols].astype(str).agg(" | ".join, axis=1).str.lower()
    return df[haystack.str.contains(q, regex=False, na=False)]

# ==========================================
# 5. SIDEBAR
# ==========================================
with st.sidebar:
    st.header("⚙️ System Controls")
    if st.button("🔄 SYNC DATA NOW", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.divider()
    st.markdown("### 📖 SOP")
    st.write("1. Add defect")
    st.write("2. Click row to edit")
    st.write("3. Assign agent")

# ==========================================
# 6. SESSION STATE
# ==========================================
if "editing_id" not in st.session_state:
    st.session_state.editing_id = None

# ==========================================
# 7. DIALOGS
# ==========================================
@st.dialog("➕ Create New Defect")
def create_defect_dialog():
    with st.form("create_form"):
        title = st.text_input("Summary *")
        module = st.selectbox("Module", MODULES)
        category = st.selectbox("Category", CATEGORIES)
        env = st.selectbox("Environment", ENVS)
        priority = st.selectbox("Priority", PRIORITIES)
        reporter = st.text_input("Reporter Name *")
        email = st.text_input("Reporter Email *")
        desc = st.text_area("Description")

        if st.form_submit_button("Submit"):
            if not title or not reporter or "@" not in email:
                st.error("Invalid input")
                return
            with get_engine().begin() as conn:
                conn.execute(text("""
                    INSERT INTO public.defects
                    (defect_title, module, category, environment, priority,
                     reported_by, reporter_email, description, status, assigned_to)
                    VALUES
                    (:t,:m,:c,:e,:p,:r,:re,:d,'New','Unassigned')
                """), dict(
                    t=title, m=module, c=category, e=env,
                    p=priority, r=reporter, re=email, d=desc
                ))
            st.cache_data.clear()
            st.rerun()

@st.dialog("✏️ Modify Defect")
def edit_defect_dialog(rec):
    with st.form("edit_form"):
        title = st.text_input("Summary", rec["defect_title"])
        status = st.selectbox("Status", STATUSES, index=STATUSES.index(rec["status"]))
        priority = st.selectbox("Priority", PRIORITIES, index=PRIORITIES.index(rec["priority"]))
        agent = st.selectbox("Assigned To", AGENTS, index=AGENTS.index(rec["assigned_to"]))
        desc = st.text_area("Description", rec["description"])
        comm = st.text_area("Comments", rec["comments"])

        c1, c2 = st.columns(2)
        save = c1.form_submit_button("💾 Save")
        cancel = c2.form_submit_button("✖ Cancel")

        if cancel:
            st.session_state.editing_id = None
            st.rerun()

        if save:
            with get_engine().begin() as conn:
                conn.execute(text("""
                    UPDATE public.defects SET
                    defect_title=:t,status=:s,priority=:p,
                    assigned_to=:a,description=:d,comments=:c,
                    updated_at=NOW()
                    WHERE id=:id
                """), dict(
                    t=title, s=status, p=priority,
                    a=agent, d=desc, c=comm,
                    id=int(rec["id"])
                ))
            st.cache_data.clear()
            st.session_state.editing_id = None
            st.rerun()

# ==========================================
# 8. MAIN UI
# ==========================================
df = load_data()
st.title(f"🛡️ {APP_NAME}")

tab1, tab2 = st.tabs(["📂 Defect Tracker", "📊 Insights"])

with tab1:
    if st.button("➕ ADD NEW DEFECT"):
        create_defect_dialog()

    search = st.text_input("🔍 Search")
    disp_df = fast_search(df, search)

    if not disp_df.empty:
        event = st.dataframe(
            disp_df[DISPLAY_COLS],
            hide_index=True,
            use_container_width=True,
            selection_mode="single-row",
            on_select="rerun"
        )

        if event and event.selection.rows:
            row = event.selection.rows[0]
            st.session_state.editing_id = disp_df.iloc[row]["id"]
            st.rerun()

    if st.session_state.editing_id:
        rec = df[df["id"] == st.session_state.editing_id]
        if not rec.empty:
            edit_defect_dialog(rec.iloc[0].to_dict())

with tab2:
    if not df.empty:
        st.subheader("👤 Agent Workload")
        gdf = df.groupby(["assigned_to", "status"]).size().reset_index(name="Items")
        fig = px.bar(
            gdf, x="Items", y="assigned_to",
            color="status", orientation="h", text_auto=True
        )
        fig.update_layout(barmode="stack", legend_title_text="Status Legend")
        st.plotly_chart(fig, use_container_width=True)
