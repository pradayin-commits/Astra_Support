import os
import datetime as dt
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text
import plotly.express as px

# ==========================================
# 1. BRANDING & UI
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
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. DATABASE LOGIC
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
            df = pd.read_sql(text("SELECT id, defect_title, module, priority, reported_by, reporter_email, status, description FROM public.defects ORDER BY id DESC"), conn)
            # CRITICAL FIX: Convert ID to string to prevent JS e.includes error
            df['id'] = df['id'].astype(str)
            return df
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
        c1, c2 = st.columns(2)
        mod = c1.selectbox("Module", MODULES)
        pri = c2.selectbox("Priority", PRIORITIES)
        rep_name = st.text_input("Reported By (Name) *")
        rep_email = st.text_input("Reporter Email *")
        desc = st.text_area("Description")
        
        if st.form_submit_button("Submit to Astra", use_container_width=True):
            if not title or not rep_name or not rep_email:
                st.error("Summary, Name, and Email are mandatory.")
            else:
                with get_engine().begin() as conn:
                    conn.execute(text("""
                        INSERT INTO public.defects (defect_title, module, priority, reported_by, reporter_email, description, status) 
                        VALUES (:t, :m, :p, :rn, :re, :d, 'New')
                    """), {"t": title, "m": mod, "p": pri, "rn": rep_name, "re": rep_email, "d": desc})
                st.cache_data.clear()
                st.rerun()

@st.dialog("✏️ Modify Defect")
def edit_defect_dialog(record):
    with st.form("edit_form"):
        st.markdown(f"### 📑 Record ID: {record['id']}")
        new_title = st.text_input("Summary", value=record['defect_title'])
        c1, c2 = st.columns(2)
        
        old_status = record['status']
        new_status = c1.selectbox("Status", STATUSES, index=STATUSES.index(old_status) if old_status in STATUSES else 0)
        new_pri = c2.selectbox("Priority", PRIORITIES, index=PRIORITIES.index(record['priority']) if record['priority'] in PRIORITIES else 0)
        
        st.text_input("Email", value=record['reporter_email'], disabled=True)
        new_desc = st.text_area("Description", value=record['description'])
        
        col_s, col_c = st.columns(2)
        if col_s.form_submit_button("💾 Save Changes", use_container_width=True):
            with get_engine().begin() as conn:
                conn.execute(text("UPDATE public.defects SET defect_title=:t, status=:s, priority=:p, description=:d WHERE id=:id"),
                            {"t": new_title, "s": new_status, "p": new_pri, "d": new_desc, "id": int(record['id'])})
                if new_status != old_status:
                    conn.execute(text("INSERT INTO public.defect_history (defect_id, old_status, new_status, changed_by) VALUES (:id, :o, :n, :u)"),
                                {"id": int(record['id']), "o": old_status, "n": new_status, "u": record['reported_by']})
            st.cache_data.clear()
            st.session_state.editing_id = None
            st.rerun()
        if col_c.form_submit_button("✖️ Cancel", use_container_width=True):
            st.session_state.editing_id = None
            st.rerun()

    st.divider()
    st.write("#### 🕒 Status Change History")
    h_df = load_history(record['id'])
    if not h_df.empty:
        st.dataframe(h_df, use_container_width=True, hide_index=True)

# ==========================================
# 4. MAIN UI
# ==========================================
df = load_data()
if 'editing_id' not in st.session_state: st.session_state.editing_id = None

st.title(f"🛡️ {APP_NAME}")

# KPIs
if not df.empty:
    k1, k2, k3 = st.columns(3)
    k1.markdown(f'<div class="metric-card global-bucket"><h3>Global</h3><h1>{len(df)}</h1></div>', unsafe_allow_html=True)
    k2.markdown(f'<div class="metric-card open-bucket"><h3>Active</h3><h1>{len(df[~df["status"].isin(["Resolved", "Closed"])])}</h1></div>', unsafe_allow_html=True)
    k3.markdown(f'<div class="metric-card resolved-bucket"><h3>Resolved</h3><h1>{len(df[df["status"].isin(["Resolved", "Closed"])])}</h1></div>', unsafe_allow_html=True)

st.divider()

# TABS
tab_tracker, tab_insights = st.tabs(["📂 Defect Tracker", "📊 Performance Insights"])

with tab_tracker:
    st.header("Defect Tracker")
    
    # Action area
    c_btn, _ = st.columns([0.2, 0.8])
    with c_btn:
        if st.button("➕ ADD NEW DEFECT", use_container_width=True):
            create_defect_dialog()

    st.write("🔍 Search the table by **ID, Summary, Module, or Email**.")
    search = st.text_input("Quick Filter", label_visibility="collapsed", placeholder="Type keywords...")
    
    st.info("💡 **Instruction:** Click any **ID** to open the record editor.")

    disp_df = df
    if search:
        disp_df = df[df.apply(lambda r: search.lower() in r.astype(str).str.lower().values, axis=1)]
    
    if not disp_df.empty:
        # LinkColumn requires strings!
        event = st.dataframe(
            disp_df[['id', 'defect_title', 'module', 'priority', 'reported_by', 'reporter_email', 'status']], 
            use_container_width=True, 
            hide_index=True, 
            on_select="rerun", 
            selection_mode="single-row",
            column_config={"id": st.column_config.LinkColumn("ID (Edit)")}
        )

        if event and event.selection.rows:
            # Save selected ID to session state
            st.session_state.editing_id = disp_df.iloc[event.selection.rows[0]]['id']

        if st.session_state.editing_id:
            # Fetch record for dialog
            rec = disp_df[disp_df['id'] == st.session_state.editing_id].iloc[0].to_dict()
            edit_defect_dialog(rec)
    else:
        st.warning("No records found.")

with tab_insights:
    st.header("Performance Insights")
    if not df.empty:
        g1, g2 = st.columns(2)
        g1.plotly_chart(px.pie(df, names='priority', hole=0.4, title="Priority Distribution"), use_container_width=True)
        g2.plotly_chart(px.bar(df.groupby('module').size().reset_index(name='Cnt'), x='module', y='Cnt', title="Module Volume"), use_container_width=True)
