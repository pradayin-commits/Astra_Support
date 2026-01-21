import os
import datetime as dt
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text
import plotly.express as px

# ==========================================
# 1. BRANDING & BOSCH-STYLE UI DESIGN
# ==========================================
APP_NAME = "Astra Defect Tracker"
st.set_page_config(page_title=APP_NAME, page_icon="🛡️", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #f0f2f6; }
    
    /* KPI Cards */
    .metric-card {
        border-radius: 12px; padding: 20px; color: white; margin-bottom: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.15);
    }
    .global-bucket { background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%); }
    .open-bucket { background: linear-gradient(135deg, #ea580c 0%, #fb923c 100%); }
    .resolved-bucket { background: linear-gradient(135deg, #166534 0%, #22c55e 100%); }
    
    .metric-card h3 { margin: 0; font-size: 14px; opacity: 0.8; text-transform: uppercase; }
    .metric-card h1 { margin: 5px 0 0 0; font-size: 32px; font-weight: 800; }

    /* Create Button Styling */
    div[data-testid="stButton"] > button {
        background-color: #064e3b !important;
        color: #ffffff !important;
        border-radius: 4px !important;
        font-weight: 700 !important;
        border: none !important;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. DATABASE UTILITIES
# ==========================================
MODULES = ["PLM", "PP", "FI", "SD", "MM", "QM", "ABAP", "BASIS", "OTHER"]
PRIORITIES = ["P1 - Critical", "P2 - High", "P3 - Medium", "P4 - Low"]
STATUSES = ["New", "In Progress", "Blocked", "Resolved", "Closed", "Reopened"]

@st.cache_resource
def get_engine():
    db_url = st.secrets.get("SUPABASE_DATABASE_URL") or os.getenv("SUPABASE_DATABASE_URL")
    if not db_url: st.stop()
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
    return create_engine(db_url, pool_pre_ping=True)

def load_data():
    try:
        with get_engine().connect() as conn:
            df = pd.read_sql(text("SELECT * FROM public.defects ORDER BY id DESC"), conn)
            df.columns = [c.lower() for c in df.columns]
            return df
    except:
        return pd.DataFrame()

def load_one_defect(record_id):
    try:
        with get_engine().connect() as conn:
            res = pd.read_sql(text("SELECT * FROM public.defects WHERE id = :id"), conn, params={"id": int(record_id)})
            res.columns = [c.lower() for c in res.columns]
            return res.iloc[0].to_dict() if not res.empty else None
    except:
        return None

# ==========================================
# 3. DIALOGS
# ==========================================
@st.dialog("➕ Create New Defect")
def create_defect_dialog():
    with st.form("create_form", clear_on_submit=True):
        st.write("**Mandatory Information**")
        title = st.text_input("Defect Summary *")
        c1, c2 = st.columns(2)
        mod = c1.selectbox("SAP Module", MODULES)
        pri = c2.selectbox("Priority", PRIORITIES)
        rep = st.text_input("Reported By *")
        desc = st.text_area("Description")
        
        if st.form_submit_button("Submit to Astra", use_container_width=True):
            if not title or not rep:
                st.error("Please fill in all mandatory fields (*).")
            else:
                with get_engine().begin() as conn:
                    conn.execute(text("""
                        INSERT INTO public.defects (defect_title, module, priority, reported_by, description, status) 
                        VALUES (:t, :m, :p, :r, :d, 'New')
                    """), {"t": title, "m": mod, "p": pri, "r": rep, "d": desc})
                st.cache_data.clear()
                st.success("Defect successfully registered.")
                st.rerun()

@st.dialog("✏️ Modify Defect")
def edit_defect_dialog(record):
    with st.form("edit_form"):
        st.markdown(f"### ID: {record['id']}")
        new_title = st.text_input("Summary", value=record.get('defect_title', ''))
        c1, c2 = st.columns(2)
        
        s_idx = STATUSES.index(record['status']) if record['status'] in STATUSES else 0
        p_idx = PRIORITIES.index(record['priority']) if record['priority'] in PRIORITIES else 0
        
        new_status = c1.selectbox("Status", STATUSES, index=s_idx)
        new_pri = c2.selectbox("Priority", PRIORITIES, index=p_idx)
        new_desc = st.text_area("Description", value=record.get('description', ''))
        
        col_save, col_cancel = st.columns(2)
        if col_save.form_submit_button("Save Changes", use_container_width=True):
            with get_engine().begin() as conn:
                conn.execute(text("""
                    UPDATE public.defects SET defect_title=:t, status=:s, priority=:p, description=:d WHERE id=:id
                """), {"t": new_title, "s": new_status, "p": new_pri, "d": new_desc, "id": record['id']})
            st.cache_data.clear()
            st.session_state.editing_id = None
            st.rerun()
        if col_cancel.form_submit_button("Cancel", use_container_width=True):
            st.session_state.editing_id = None
            st.rerun()

# ==========================================
# 4. MAIN DASHBOARD UI
# ==========================================
df = load_data()

if 'editing_id' not in st.session_state:
    st.session_state.editing_id = None

st.title(f"🛡️ {APP_NAME}")

# KPI Row
if not df.empty:
    k1, k2, k3 = st.columns(3)
    k1.markdown(f'<div class="metric-card global-bucket"><h3>Global Items</h3><h1>{len(df)}</h1></div>', unsafe_allow_html=True)
    k2.markdown(f'<div class="metric-card open-bucket"><h3>Active Items</h3><h1>{len(df[~df["status"].isin(["Resolved", "Closed"])])}</h1></div>', unsafe_allow_html=True)
    k3.markdown(f'<div class="metric-card resolved-bucket"><h3>Resolved Total</h3><h1>{len(df[df["status"].isin(["Resolved", "Closed"])])}</h1></div>', unsafe_allow_html=True)

# Tabs
tab_insights, tab_tracker = st.tabs(["📊 Performance Insights", "📂 Defect Tracker"])

with tab_insights:
    if not df.empty:
        st.subheader("Analytical Drill-Down")
        d1, d2, d3 = st.columns(3)
        cat_1 = d1.selectbox("Filter By", ["module", "priority", "status"])
        val_1 = d2.selectbox(f"Value", ["All Data"] + sorted(df[cat_1].unique().tolist()))
        cat_2 = d3.selectbox("Pivot By", [c for c in ["status", "priority", "module"] if c != cat_1])
        c_df = df if val_1 == "All Data" else df[df[cat_1] == val_1]
        g1, g2 = st.columns(2)
        g1.plotly_chart(px.pie(c_df, names=cat_2, hole=0.4, title="Distribution"), use_container_width=True)
        g2.plotly_chart(px.bar(c_df.groupby(cat_2).size().reset_index(name='Count'), x=cat_2, y='Count', color=cat_2, title="Defect Volume"), use_container_width=True)

with tab_tracker:
    st.subheader("Defect Table")
    
    # Action Row
    c_btn, c_search = st.columns([0.25, 0.75])
    with c_btn:
        # THE CREATE BUTTON
        if st.button("➕ CREATE NEW DEFECT", use_container_width=True):
            create_defect_dialog()
            
    with c_search:
        search = st.text_input("🔍 Search Defects", label_visibility="collapsed", placeholder="Filter by ID, Title, Reporter...")

    st.info("💡 **Selection Instruction:** Click the checkbox on the left to open the **Modify Defect** window.")

    disp_df = df
    if search:
        disp_df = df[df.apply(lambda r: search.lower() in r.astype(str).str.lower().values, axis=1)]
    disp_df = disp_df.reset_index(drop=True)

    # Defect Table
    event = st.dataframe(
        disp_df, 
        use_container_width=True, 
        hide_index=True, 
        on_select="rerun", 
        selection_mode="single-row",
        column_config={
            "id": st.column_config.TextColumn("ID", help="System ID"),
            "defect_title": st.column_config.TextColumn("Summary", width="large"),
            "created_at": st.column_config.DatetimeColumn("Date", format="DD/MM/YYYY")
        }
    )

    if event and event.selection.rows:
        row_idx = event.selection.rows[0]
        st.session_state.editing_id = disp_df.at[row_idx, 'id']

    if st.session_state.editing_id is not None:
        rec = load_one_defect(st.session_state.editing_id)
        if rec:
            edit_defect_dialog(rec)
