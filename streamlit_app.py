import os
import datetime as dt
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

# ==========================================
# 1. SETUP & BRANDING
# ==========================================
APP_NAME = "Astra Defect Tracker"
st.set_page_config(page_title=APP_NAME, page_icon="🛡️", layout="wide")

# Constants
MODULES = ["PLM", "PP", "FI", "SD", "MM", "QM", "ABAP", "BASIS", "OTHER"]
PRIORITIES = ["P1 - Critical", "P2 - High", "P3 - Medium", "P4 - Low"]
STATUSES = ["New", "In Progress", "Blocked", "Resolved", "Closed", "Reopened"]
CATEGORIES = ["Functional", "UI/UX", "Data", "Security", "Performance"]
ENVS = ["Production", "UAT", "QA", "Development"]

@st.cache_resource
def get_engine():
    db_url = st.secrets.get("SUPABASE_DATABASE_URL") or os.getenv("SUPABASE_DATABASE_URL")
    if not db_url: st.stop()
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
    return create_engine(db_url, pool_pre_ping=True)

# ==========================================
# 2. DATA LOADERS
# ==========================================
def load_data():
    try:
        with get_engine().connect() as conn:
            return pd.read_sql(text("SELECT * FROM public.defects ORDER BY id DESC"), conn)
    except: return pd.DataFrame()

def load_history(defect_id):
    try:
        with get_engine().connect() as conn:
            return pd.read_sql(text("SELECT old_status, new_status, changed_at FROM public.defect_history WHERE defect_id = :id ORDER BY changed_at DESC"), 
                            conn, params={"id": int(defect_id)})
    except: return pd.DataFrame()

# ==========================================
# 3. DIALOGS
# ==========================================
@st.dialog("➕ Create New Defect")
def create_defect_dialog():
    with st.form("create_form", clear_on_submit=True):
        st.write("### 📝 New Registration")
        title = st.text_input("Summary *")
        c1, c2, c3 = st.columns(3)
        mod = c1.selectbox("Module", MODULES)
        cat = c2.selectbox("Category", CATEGORIES)
        env = c3.selectbox("Environment", ENVS)
        
        c4, c5 = st.columns(2)
        pri = c4.selectbox("Priority", PRIORITIES)
        rep_name = c5.text_input("Reporter Name *")
        rep_email = st.text_input("Reporter Email *")
        
        desc = st.text_area("Initial Description")
        
        if st.form_submit_button("Submit to Astra", use_container_width=True):
            if not title or not rep_name or not "@" in rep_email:
                st.error("Please provide a valid Summary, Name, and Email.")
            else:
                with get_engine().begin() as conn:
                    conn.execute(text("""
                        INSERT INTO public.defects (defect_title, module, priority, category, environment, reported_by, reporter_email, description) 
                        VALUES (:t, :m, :p, :c, :e, :rn, :re, :d)
                    """), {"t": title, "m": mod, "p": pri, "c": cat, "e": env, "rn": rep_name, "re": rep_email, "d": desc})
                st.cache_data.clear()
                st.rerun()

@st.dialog("✏️ Modify & Display Defect")
def edit_defect_dialog(record):
    with st.form("edit_form"):
        st.markdown(f"### 📑 Record ID: {record['id']}")
        
        # Section 1: Core Info
        new_title = st.text_input("Summary", value=record['defect_title'])
        c1, c2, c3 = st.columns(3)
        old_status = record['status']
        new_status = c1.selectbox("Status", STATUSES, index=STATUSES.index(old_status) if old_status in STATUSES else 0)
        new_pri = c2.selectbox("Priority", PRIORITIES, index=PRIORITIES.index(record['priority']) if record['priority'] in PRIORITIES else 0)
        new_assign = c3.text_input("Assigned To", value=record.get('assigned_to', 'Unassigned'))
        
        # Section 2: Details & Notes
        st.write("---")
        new_desc = st.text_area("Description", value=record['description'])
        new_comm = st.text_area("Internal Comments", value=record.get('comments', ''))
        new_res = st.text_area("Resolution Notes", value=record.get('resolution_notes', ''))
        
        # Section 3: System Info (Dates)
        st.write("---")
        st.markdown("**🛡️ System Information**")
        d1, d2, d3 = st.columns(3)
        d1.text_input("Created At", value=str(record['created_at']), disabled=True)
        d2.text_input("Last Updated", value=str(record['updated_at']), disabled=True)
        res_date = str(record['resolved_at']) if record['resolved_at'] else "N/A"
        d3.text_input("Resolved At", value=res_date, disabled=True)

        col_s, col_c = st.columns(2)
        if col_s.form_submit_button("💾 Save Changes", use_container_width=True):
            resolved_at = dt.datetime.now() if new_status in ["Resolved", "Closed"] else record['resolved_at']
            with get_engine().begin() as conn:
                conn.execute(text("""
                    UPDATE public.defects SET 
                    defect_title=:t, status=:s, priority=:p, assigned_to=:a, 
                    description=:d, comments=:c, resolution_notes=:r, 
                    resolved_at=:ra, updated_at=NOW() WHERE id=:id
                """), {"t": new_title, "s": new_status, "p": new_pri, "a": new_assign, 
                       "d": new_desc, "c": new_comm, "r": new_res, "ra": resolved_at, "id": record['id']})
                
                if new_status != old_status:
                    conn.execute(text("INSERT INTO public.defect_history (defect_id, old_status, new_status, changed_by) VALUES (:id, :o, :n, :u)"),
                                {"id": record['id'], "o": old_status, "n": new_status, "u": record['reported_by']})
            st.cache_data.clear()
            st.session_state.editing_id = None
            st.rerun()
        if col_c.form_submit_button("✖️ Cancel", use_container_width=True):
            st.session_state.editing_id = None
            st.rerun()

    # History Section
    st.write("#### 🕒 Status Change History")
    h_df = load_history(record['id'])
    if not h_df.empty: st.dataframe(h_df, use_container_width=True, hide_index=True)

# ==========================================
# 4. MAIN UI
# ==========================================
df = load_data()
if 'editing_id' not in st.session_state: st.session_state.editing_id = None

st.title(f"🛡️ {APP_NAME}")

# KPIs
if not df.empty:
    k1, k2, k3 = st.columns(3)
    k1.metric("Global Items", len(df))
    k2.metric("Open Defects", len(df[~df['status'].isin(['Resolved', 'Closed'])]))
    k3.metric("Resolved", len(df[df['status'].isin(['Resolved', 'Closed'])]))

tab_tracker, tab_insights = st.tabs(["📂 Defect Tracker", "📊 Performance Insights"])

with tab_tracker:
    st.header("Defect Tracker")
    if st.button("➕ ADD NEW DEFECT", use_container_width=False):
        create_defect_dialog()

    search = st.text_input("Quick Filter (ID, Summary, Module, Email...)", placeholder="Search registry...")
    
    if not df.empty:
        disp_df = df if not search else df[df.apply(lambda r: search.lower() in r.astype(str).str.lower().values, axis=1)]
        disp_df['id_str'] = disp_df['id'].astype(str) # For LinkColumn safety
        
        event = st.dataframe(
            disp_df[['id_str', 'defect_title', 'module', 'priority', 'assigned_to', 'reported_by', 'status']], 
            use_container_width=True, 
            hide_index=True, 
            on_select="rerun", 
            selection_mode="single-row",
            column_config={"id_str": st.column_config.LinkColumn("ID (Edit)")}
        )

        if event and event.selection.rows:
            st.session_state.editing_id = disp_df.iloc[event.selection.rows[0]]['id']

        if st.session_state.editing_id:
            rec = df[df['id'] == st.session_state.editing_id].iloc[0].to_dict()
            edit_defect_dialog(rec)
