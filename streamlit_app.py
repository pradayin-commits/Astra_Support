import os
import datetime as dt
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
            df['id'] = df['id'].astype(str) # String cast for JS safety
            return df
    except: return pd.DataFrame()

def load_history(defect_id):
    try:
        with get_engine().connect() as conn:
            return pd.read_sql(text("SELECT old_status, new_status, changed_at FROM public.defect_history WHERE defect_id = :id ORDER BY changed_at DESC"), 
                            conn, params={"id": int(defect_id)})
    except: return pd.DataFrame()

# ==========================================
# 3. INTERACTIVE DIALOGS
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
        
        if st.form_submit_button("Submit to Astra", use_container_width=True):
            clean_title = title_in.strip()
            clean_name = name_in.strip()
            clean_email = email_in.strip()
            
            if not clean_title:
                st.error("❌ Summary is required.")
            elif not clean_name:
                st.error("❌ Reporter Name is required.")
            elif not clean_email or "@" not in clean_email:
                st.error("❌ Valid Reporter Email is required.")
            else:
                try:
                    with get_engine().begin() as conn:
                        conn.execute(text("""
                            INSERT INTO public.defects 
                            (defect_title, module, priority, category, environment, reported_by, reporter_email, description) 
                            VALUES (:t, :m, :p, :c, :e, :rn, :re, :d)
                        """), {
                            "t": clean_title, "m": mod_in, "p": pri_in, 
                            "c": cat_in, "e": env_in, "rn": clean_name, 
                            "re": clean_email, "d": desc_in
                        })
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Database Error: {e}")

@st.dialog("✏️ Modify Defect")
def edit_defect_dialog(record):
    with st.form("edit_form"):
        st.markdown(f"### 📑 Record ID: {record['id']}")
        
        new_title = st.text_input("Summary", value=record['defect_title'])
        c1, c2, c3 = st.columns(3)
        
        old_status = record['status']
        new_status = c1.selectbox("Status", STATUSES, index=STATUSES.index(old_status) if old_status in STATUSES else 0)
        new_pri = c2.selectbox("Priority", PRIORITIES, index=PRIORITIES.index(record['priority']) if record['priority'] in PRIORITIES else 0)
        new_assign = c3.text_input("Assigned To Agent", value=record.get('assigned_to', 'Unassigned'))
        
        st.write("---")
        new_desc = st.text_area("Description", value=record['description'])
        new_comm = st.text_area("Comments", value=record.get('comments', ''))
        new_res = st.text_area("Resolution Notes", value=record.get('resolution_notes', ''))
        
        st.write("---")
        st.markdown("**🛡️ System Metadata**")
        d1, d2, d3 = st.columns(3)
        d1.text_input("Created", value=str(record['created_at'])[:16], disabled=True)
        d2.text_input("Last Update", value=str(record['updated_at'])[:16], disabled=True)
        d3.text_input("Resolved", value=str(record['resolved_at'])[:16] if record['resolved_at'] else "N/A", disabled=True)

        col_s, col_c = st.columns(2)
        if col_s.form_submit_button("💾 Save Changes", use_container_width=True):
            res_date = dt.datetime.now() if new_status in ["Resolved", "Closed"] else record['resolved_at']
            with get_engine().begin() as conn:
                conn.execute(text("""
                    UPDATE public.defects SET 
                    defect_title=:t, status=:s, priority=:p, assigned_to=:a, 
                    description=:d, comments=:c, resolution_notes=:r, 
                    resolved_at=:ra, updated_at=NOW() WHERE id=:id
                """), {"t": new_title, "s": new_status, "p": new_pri, "a": new_assign, 
                       "d": new_desc, "c": new_comm, "r": new_res, "ra": res_date, "id": int(record['id'])})
                
                if new_status != old_status:
                    conn.execute(text("INSERT INTO public.defect_history (defect_id, old_status, new_status, changed_by) VALUES (:id, :o, :n, :u)"),
                                {"id": int(record['id']), "o": old_status, "n": new_status, "u": record['reported_by']})
            st.cache_data.clear()
            st.session_state.editing_id = None
            st.rerun()
        if col_c.form_submit_button("✖️ Cancel", use_container_width=True):
            st.session_state.editing_id = None
            st.rerun()

    st.write("#### 🕒 Status Change History")
    h_df = load_history(record['id'])
    if not h_df.empty: st.dataframe(h_df, use_container_width=True, hide_index=True)

# ==========================================
# 4. MAIN UI
# ==========================================
df = load_data()
if 'editing_id' not in st.session_state: st.session_state.editing_id = None

st.title(f"🛡️ {APP_NAME}")

if not df.empty:
    k1, k2, k3 = st.columns(3)
    k1.markdown(f'<div class="metric-card global-bucket"><h3>Global Items</h3><h1>{len(df)}</h1></div>', unsafe_allow_html=True)
    k2.markdown(f'<div class="metric-card open-bucket"><h3>Active</h3><h1>{len(df[~df["status"].isin(["Resolved", "Closed"])])}</h1></div>', unsafe_allow_html=True)
    k3.markdown(f'<div class="metric-card resolved-bucket"><h3>Resolved Total</h3><h1>{len(df[df["status"].isin(["Resolved", "Closed"])])}</h1></div>', unsafe_allow_html=True)

st.divider()

# Tab Reordering: Defect Tracker is FIRST
tab_tracker, tab_insights = st.tabs(["📂 Defect Tracker", "📊 Performance Insights"])

with tab_tracker:
    c_btn, _ = st.columns([0.2, 0.8])
    with c_btn:
        if st.button("➕ ADD NEW DEFECT", use_container_width=True):
            create_defect_dialog()

    st.subheader("Defect Table")
    search = st.text_input("🔍 Quick Filter", placeholder="Search by ID, Summary, Module, or Agent...")
    
    st.info("💡 **Instruction:** Click any **ID number** to modify the record or assign an agent.")

    disp_df = df
    if search:
        disp_df = df[df.apply(lambda r: search.lower() in r.astype(str).str.lower().values, axis=1)]
    
    if not disp_df.empty:
        # worksheet view without timestamps
        event = st.dataframe(
            disp_df[['id', 'defect_title', 'module', 'priority', 'assigned_to', 'status']], 
            use_container_width=True, 
            hide_index=True, 
            on_select="rerun", 
            selection_mode="single-row",
            column_config={"id": st.column_config.LinkColumn("ID (Edit)")}
        )

        if event and event.selection.rows:
            st.session_state.editing_id = disp_df.iloc[event.selection.rows[0]]['id']

        if st.session_state.editing_id:
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
