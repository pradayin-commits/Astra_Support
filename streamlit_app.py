import os
import datetime as dt
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text
import plotly.express as px

# ==========================================
# 1. BRANDING & BOSCH-STYLE UI
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
    
    /* ADD NEW DEFECT BUTTON STYLE */
    div[data-testid="stButton"] > button {
        background-color: #064e3b !important;
        color: white !important;
        font-weight: 700 !important;
        height: 3.5rem !important;
        width: 100% !important;
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
    except: return pd.DataFrame()

def load_status_history(defect_id):
    try:
        with get_engine().connect() as conn:
            df = pd.read_sql(text("SELECT * FROM public.defect_history WHERE defect_id = :id ORDER BY changed_at DESC"),
                            conn, params={"id": int(defect_id)})
            return df
    except: return pd.DataFrame()

# ==========================================
# 3. INTERACTIVE DIALOGS
# ==========================================
@st.dialog("➕ Create New Defect")
def create_defect_dialog():
    with st.form("create_form", clear_on_submit=True):
        st.write("### 📝 New Registration")
        title = st.text_input("Summary *")
        c1, c2 = st.columns(2)
        mod = c1.selectbox("Module", MODULES)
        pri = c2.selectbox("Priority", PRIORITIES)
        rep = st.text_input("Reported By *")
        desc = st.text_area("Description")
        
        if st.form_submit_button("Submit to Astra"):
            if not title or not rep:
                st.error("Missing mandatory fields.")
            else:
                with get_engine().begin() as conn:
                    conn.execute(text("""
                        INSERT INTO public.defects (defect_title, module, priority, reported_by, description, status) 
                        VALUES (:t, :m, :p, :r, :d, 'New')
                    """), {"t": title, "m": mod, "p": pri, "r": rep, "d": desc})
                st.cache_data.clear()
                st.rerun()

@st.dialog("✏️ Modify Defect")
def edit_defect_dialog(record):
    with st.form("edit_form"):
        st.markdown(f"### 📑 Record ID: {record['id']}")
        new_title = st.text_input("Summary", value=record.get('defect_title', ''))
        c1, c2 = st.columns(2)
        
        old_status = record.get('status', 'New')
        new_status = c1.selectbox("Status", STATUSES, index=STATUSES.index(old_status) if old_status in STATUSES else 0)
        new_pri = c2.selectbox("Priority", PRIORITIES, index=PRIORITIES.index(record.get('priority', 'P3 - Medium')))
        new_desc = st.text_area("Description", value=record.get('description', ''))
        
        col_s, col_c = st.columns(2)
        if col_s.form_submit_button("💾 Save Changes", use_container_width=True):
            with get_engine().begin() as conn:
                conn.execute(text("UPDATE public.defects SET defect_title=:t, status=:s, priority=:p, description=:d WHERE id=:id"),
                            {"t": new_title, "s": new_status, "p": new_pri, "d": new_desc, "id": record['id']})
                if new_status != old_status:
                    conn.execute(text("INSERT INTO public.defect_history (defect_id, old_status, new_status, changed_by) VALUES (:id, :o, :n, :u)"),
                                {"id": record['id'], "o": old_status, "n": new_status, "u": record.get('reported_by')})
            st.cache_data.clear()
            st.session_state.editing_id = None
            st.rerun()
        if col_c.form_submit_button("✖️ Cancel", use_container_width=True):
            st.session_state.editing_id = None
            st.rerun()

    st.divider()
    st.write("#### 🕒 Status History")
    hist = load_status_history(record['id'])
    if not hist.empty:
        st.dataframe(hist[['old_status', 'new_status', 'changed_at']], use_container_width=True, hide_index=True)
    else:
        st.caption("No history available.")

# ==========================================
# 4. MAIN UI
# ==========================================
df = load_data()
if 'editing_id' not in st.session_state: st.session_state.editing_id = None

st.title(f"🛡️ {APP_NAME}")

# --- KPI BUCKETS ---
if not df.empty:
    k1, k2, k3 = st.columns(3)
    k1.markdown(f'<div class="metric-card global-bucket"><h3>Global</h3><h1>{len(df)}</h1></div>', unsafe_allow_html=True)
    k2.markdown(f'<div class="metric-card open-bucket"><h3>Active</h3><h1>{len(df[~df["status"].isin(["Resolved", "Closed"])])}</h1></div>', unsafe_allow_html=True)
    k3.markdown(f'<div class="metric-card resolved-bucket"><h3>Resolved</h3><h1>{len(df[df["status"].isin(["Resolved", "Closed"])])}</h1></div>', unsafe_allow_html=True)

# --- ACCESSIBLE CREATE BUTTON ---
c_btn, _ = st.columns([0.25, 0.75])
with c_btn:
    if st.button("➕ ADD NEW DEFECT"):
        create_defect_dialog()

st.divider()

tab_insights, tab_tracker = st.tabs(["📊 Performance Insights", "📂 Defect Tracker"])

with tab_insights:
    if not df.empty:
        st.subheader("Analytical Drill-Down")
        d1, d2, d3 = st.columns(3)
        cat_1 = d1.selectbox("Filter By", ["module", "priority", "status"])
        val_1 = d2.selectbox("Value", ["All Data"] + sorted(df[cat_1].unique().tolist()))
        cat_2 = d3.selectbox("Pivot By", [c for c in ["status", "priority", "module"] if c != cat_1])
        c_df = df if val_1 == "All Data" else df[df[cat_1] == val_1]
        g1, g2 = st.columns(2)
        g1.plotly_chart(px.pie(c_df, names=cat_2, hole=0.4, title="Distribution"), use_container_width=True)
        g2.plotly_chart(px.bar(c_df.groupby(cat_2).size().reset_index(name='Cnt'), x=cat_2, y='Cnt', color=cat_2, title="Volume"), use_container_width=True)

with tab_tracker:
    st.subheader("Defect Table")
    st.write("🔍 **Search Guidance:** Use the box below to filter the table by **ID, Summary, or Module**.")
    search = st.text_input("Quick Search", placeholder="Filter registry...")
    
    st.info("💡 **How to Edit:** Click the checkbox on the left of a row to open the **Modify** window.")

    disp_df = df
    if search:
        disp_df = df[df.apply(lambda r: search.lower() in r.astype(str).str.lower().values, axis=1)]
    disp_df = disp_df.reset_index(drop=True)

    event = st.dataframe(disp_df, use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row")

    if event and event.selection.rows:
        st.session_state.editing_id = disp_df.at[event.selection.rows[0], 'id']

    if st.session_state.editing_id:
        rec = next((r for r in disp_df.to_dict('records') if r['id'] == st.session_state.editing_id), None)
        if rec: edit_defect_dialog(rec)
