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
        border-radius: 6px !important;
    }

    .search-wrap div[data-testid="stTextInput"] input{
        background: #ffecec !important;
        border: 1px solid #ff6b6b !important;
        border-radius: 10px !important;
        padding: 10px 12px !important;
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
    "id", "defect_title", "module", "category", "environment", "priority",
    "reported_by", "reporter_email", "assigned_to", "status"
]
# All fields that should be present in the DB
DB_FIELDS = DISPLAY_COLS + ["description", "comments"]

# ==========================================
# 3. DB / LOAD
# ==========================================
@st.cache_resource
def get_engine():
    db_url = st.secrets.get("SUPABASE_DATABASE_URL") if hasattr(st, "secrets") else None
    db_url = db_url or os.getenv("SUPABASE_DATABASE_URL")
    if not db_url:
        st.error("Missing SUPABASE_DATABASE_URL.")
        st.stop()
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
    return create_engine(db_url, pool_pre_ping=True)

@st.cache_data(ttl=60)
def load_data():
    try:
        with get_engine().connect() as conn:
            df = pd.read_sql(text("SELECT * FROM public.defects ORDER BY id DESC"), conn)
        
        if df.empty: return df

        # Ensure all columns exist
        for col in DB_FIELDS:
            if col not in df.columns:
                df[col] = ""
        
        df = df.fillna("")
        # Ensure ID is a string for consistent filtering
        df["id"] = df["id"].astype(str)
        return df
    except Exception as e:
        st.error(f"Database Error: {e}")
        return pd.DataFrame(columns=DB_FIELDS)

# ==========================================
# 4. DIALOGS
# ==========================================

@st.dialog("➕ Create New Defect")
def create_defect_dialog():
    with st.form("create_form", clear_on_submit=True):
        st.subheader("New Registration")
        t_in = st.text_input("Summary *")
        c1, c2, c3 = st.columns(3)
        m_in = c1.selectbox("Module", MODULES)
        cat_in = c2.selectbox("Category", CATEGORIES)
        env_in = c3.selectbox("Environment", ENVS)

        c4, c5 = st.columns(2)
        p_in = c4.selectbox("Priority", PRIORITIES)
        n_in = c5.text_input("Reporter Name *")

        e_in = st.text_input("Reporter Email *")
        d_in = st.text_area("Description")

        if st.form_submit_button("Submit to Astra", use_container_width=True):
            if not t_in or not n_in or "@" not in e_in:
                st.error("Please fill required fields.")
            else:
                with get_engine().begin() as conn:
                    conn.execute(text("""
                        INSERT INTO public.defects 
                        (defect_title, module, priority, category, environment, reported_by, reporter_email, description, status, assigned_to)
                        VALUES (:t, :m, :p, :c, :env, :rn, :re, :d, 'New', 'Unassigned')
                    """), {"t": t_in, "m": m_in, "p": p_in, "c": cat_in, "env": env_in, "rn": n_in, "re": e_in, "d": d_in})
                st.cache_data.clear()
                st.rerun()

@st.dialog("✏️ Edit Defect")
def edit_defect_dialog(record: dict):
    with st.form("edit_full_form"):
        st.subheader(f"Editing Record ID: {record['id']}")
        
        # Row 1: Title
        new_title = st.text_input("Summary", value=str(record.get("defect_title", "")))

        # Row 2: Status, Priority, Agent
        c1, c2, c3 = st.columns(3)
        idx_status = STATUSES.index(record['status']) if record['status'] in STATUSES else 0
        idx_priority = PRIORITIES.index(record['priority']) if record['priority'] in PRIORITIES else 0
        idx_agent = AGENTS.index(record['assigned_to']) if record['assigned_to'] in AGENTS else 0
        
        new_status = c1.selectbox("Status", STATUSES, index=idx_status)
        new_pri = c2.selectbox("Priority", PRIORITIES, index=idx_priority)
        new_agent = c3.selectbox("Assigned To", AGENTS, index=idx_agent)

        # Row 3: Module, Category, Env
        c4, c5, c6 = st.columns(3)
        idx_mod = MODULES.index(record['module']) if record['module'] in MODULES else 0
        idx_cat = CATEGORIES.index(record['category']) if record['category'] in CATEGORIES else 0
        idx_env = ENVS.index(record['environment']) if record['environment'] in ENVS else 0

        new_mod = c4.selectbox("Module", MODULES, index=idx_mod)
        new_cat = c5.selectbox("Category", CATEGORIES, index=idx_cat)
        new_env = c6.selectbox("Environment", ENVS, index=idx_env)

        # Row 4: Reporter Info
        c7, c8 = st.columns(2)
        new_rep_name = c7.text_input("Reporter Name", value=str(record.get("reported_by", "")))
        new_rep_email = c8.text_input("Reporter Email", value=str(record.get("reporter_email", "")))

        # Row 5: Long Text
        new_desc = st.text_area("Detailed Description", value=str(record.get("description", "")))
        new_comm = st.text_area("Internal Comments", value=str(record.get("comments", "")))

        submit = st.form_submit_button("💾 Save All Changes", use_container_width=True)
        
        if submit:
            try:
                with get_engine().begin() as conn:
                    conn.execute(text("""
                        UPDATE public.defects SET
                        defect_title=:t, status=:s, priority=:p, assigned_to=:a,
                        module=:m, category=:c, environment=:env,
                        reported_by=:rn, reporter_email=:re,
                        description=:d, comments=:comm, updated_at=NOW()
                        WHERE id=:id
                    """), {
                        "t": new_title, "s": new_status, "p": new_pri, "a": new_agent,
                        "m": new_mod, "c": new_cat, "env": new_env,
                        "rn": new_rep_name, "re": new_rep_email,
                        "d": new_desc, "comm": new_comm, "id": int(record['id'])
                    })
                st.cache_data.clear()
                st.session_state.editing_id = None
                st.rerun()
            except Exception as e:
                st.error(f"Error saving: {e}")

# ==========================================
# 5. MAIN APP LOGIC
# ==========================================
if "editing_id" not in st.session_state:
    st.session_state.editing_id = None

df = load_data()

# 5a. Header & Metrics
st.title(f"🛡️ {APP_NAME}")
if not df.empty:
    k1, k2, k3 = st.columns(3)
    k1.markdown(f'<div class="metric-card global-bucket"><h3>Total Defects</h3><h1>{len(df)}</h1></div>', unsafe_allow_html=True)
    active_count = len(df[~df["status"].isin(["Resolved", "Closed"])])
    k2.markdown(f'<div class="metric-card open-bucket"><h3>Active Items</h3><h1>{active_count}</h1></div>', unsafe_allow_html=True)
    res_count = len(df[df["status"].isin(["Resolved", "Closed"])])
    k3.markdown(f'<div class="metric-card resolved-bucket"><h3>Resolved</h3><h1>{res_count}</h1></div>', unsafe_allow_html=True)

# 5b. Tabs
tab_tracker, tab_insights = st.tabs(["📂 Defect Tracker", "📊 Insights"])

with tab_tracker:
    # Action Bar
    col_btn, col_srch = st.columns([1, 2])
    with col_btn:
        if st.button("➕ ADD NEW DEFECT", use_container_width=True):
            create_defect_dialog()
    
    with col_srch:
        search_query = st.text_input("🔍 Search Summary, Reporter, or Module...", placeholder="Search...")

    # Filtering Logic
    if not df.empty:
        if search_query:
            # Create a combined string for searching
            mask = df.apply(lambda row: search_query.lower() in row.astype(str).str.cat(sep=' ').lower(), axis=1)
            display_df = df[mask]
        else:
            display_df = df

        # Data Table
        selection = st.dataframe(
            display_df[DISPLAY_COLS],
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row"
        )

        # Handle Selection
        selected_rows = selection.get("selection", {}).get("rows", [])
        if selected_rows:
            selected_idx = selected_rows[0]
            # Map the filtered row back to the actual ID
            st.session_state.editing_id = display_df.iloc[selected_idx]["id"]
            st.rerun()

    else:
        st.info("No records found.")

# 5c. Logic to open Dialog
if st.session_state.editing_id:
    # Fetch the full record from the original dataframe
    rec_to_edit = df[df["id"] == st.session_state.editing_id]
    if not rec_to_edit.empty:
        edit_defect_dialog(rec_to_edit.iloc[0].to_dict())
    else:
        st.session_state.editing_id = None

with tab_insights:
    if not df.empty:
        st.subheader("High-Level Statistics")
        fig = px.histogram(df, x="module", color="status", barmode="group", title="Defects by Module & Status")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No data for insights.")
