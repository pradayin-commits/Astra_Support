import os
import datetime as dt
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text
import plotly.express as px

# ==========================================
# 1. BRANDING & VIBRANT DESIGN
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
    .metric-card h3 { margin: 0; font-size: 14px; opacity: 0.8; text-transform: uppercase; }
    .metric-card h1 { margin: 5px 0 0 0; font-size: 32px; font-weight: 800; }
    div[data-testid="stButton"] > button {
        background-color: #064e3b !important;
        color: #ffffff !important;
        border-radius: 6px !important;
        border: none !important;
        padding: 0.5rem 2rem !important;
        font-weight: 600 !important;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. DATABASE CONFIGURATION
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
            return pd.read_sql(text("SELECT * FROM public.defects ORDER BY created_at DESC"), conn)
    except:
        return pd.DataFrame()

def load_one_defect(record_id):
    try:
        with get_engine().connect() as conn:
            res = pd.read_sql(text("SELECT * FROM public.defects WHERE id = :id"), conn, params={"id": int(record_id)})
            return res.iloc[0].to_dict() if not res.empty else None
    except:
        return None

# ==========================================
# 3. MODALS
# ==========================================
@st.dialog("➕ Register New Defect")
def create_defect_dialog():
    with st.form("create_form", clear_on_submit=True):
        title = st.text_input("Summary *")
        col1, col2 = st.columns(2)
        mod = col1.selectbox("Module", MODULES)
        pri = col2.selectbox("Priority", PRIORITIES)
        rep = st.text_input("Reported By *")
        desc = st.text_area("Detailed Description")
        
        if st.form_submit_button("Submit to Astra", use_container_width=True):
            if not title or not rep:
                st.error("Summary and Reported By are required.")
            else:
                # NOTICE: We do NOT send an 'id' here. Postgres assigns it.
                new_rec = {"t": title, "m": mod, "p": pri, "r": rep, "d": desc, "s": "New", "now": dt.datetime.now()}
                with get_engine().begin() as conn:
                    conn.execute(text("""
                        INSERT INTO public.defects (defect_title, module, priority, reported_by, description, status, created_at, updated_at) 
                        VALUES (:t, :m, :p, :r, :d, :s, :now, :now)
                    """), new_rec)
                st.cache_data.clear()
                st.rerun()

@st.dialog("✏️ Edit Defect")
def edit_defect_dialog(record):
    with st.form("edit_form"):
        st.markdown(f"**Editing ID: {record['id']}**")
        new_title = st.text_input("Summary", value=record['defect_title'])
        c1, c2 = st.columns(2)
        new_status = c1.selectbox("Status", STATUSES, index=STATUSES.index(record['status']))
        new_pri = c2.selectbox("Priority", PRIORITIES, index=PRIORITIES.index(record['priority']))
        new_desc = st.text_area("Description", value=record['description'])
        
        if st.form_submit_button("Save Changes", use_container_width=True):
            with get_engine().begin() as conn:
                conn.execute(text("""
                    UPDATE public.defects 
                    SET defect_title=:t, status=:s, priority=:p, description=:d, updated_at=:u 
                    WHERE id=:id
                """), {"t": new_title, "s": new_status, "p": new_pri, "d": new_desc, "u": dt.datetime.now(), "id": record['id']})
            st.cache_data.clear()
            st.rerun()

# ==========================================
# 4. MAIN UI
# ==========================================
df = load_data()

st.title(f"🛡️ {APP_NAME}")

if not df.empty:
    k1, k2, k3 = st.columns(3)
    k1.markdown(f'<div class="metric-card global-bucket"><h3>Global</h3><h1>{len(df)}</h1></div>', unsafe_allow_html=True)
    k2.markdown(f'<div class="metric-card open-bucket"><h3>Active</h3><h1>{len(df[~df["status"].isin(["Resolved", "Closed"])])}</h1></div>', unsafe_allow_html=True)
    k3.markdown(f'<div class="metric-card resolved-bucket"><h3>Resolved</h3><h1>{len(df[df["status"].isin(["Resolved", "Closed"])])}</h1></div>', unsafe_allow_html=True)

btn_col, _ = st.columns([0.2, 0.8])
with btn_col:
    if st.button("➕ CREATE NEW DEFECT"):
        create_defect_dialog()

tab_insights, tab_explorer = st.tabs(["📊 Performance Insights", "📂 Workspace Explorer"])

with tab_insights:
    if not df.empty:
        d1, d2, d3 = st.columns(3)
        cat_1 = d1.selectbox("1. Category", ["module", "priority", "status", "reported_by"])
        val_1 = d2.selectbox(f"2. {cat_1.title()} Value", ["All Data"] + sorted(df[cat_1].unique().tolist()))
        cat_2 = d3.selectbox("3. Pivot By", [c for c in ["status", "priority", "module"] if c != cat_1])
        
        c_df = df if val_1 == "All Data" else df[df[cat_1] == val_1]
        g1, g2 = st.columns(2)
        g1.plotly_chart(px.pie(c_df, names=cat_2, hole=0.4, title=f"{cat_2.title()} Dist."), use_container_width=True)
        g2.plotly_chart(px.bar(c_df.groupby(cat_2).size().reset_index(name='Cnt'), x=cat_2, y='Cnt', color=cat_2, title="Volume"), use_container_width=True)

with tab_explorer:
    st.subheader("Defect Registry")
    search = st.text_input("🔍 Quick Search")
    disp_df = df
    if search:
        disp_df = df[df.apply(lambda r: search.lower() in r.astype(str).str.lower().values, axis=1)]

    # Use selection to trigger the pop-up
    event = st.dataframe(disp_df, use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row")

    if event and event.selection.rows:
        sel_row = event.selection.rows[0]
        rec_id = disp_df.iloc[sel_row]['id']
        record = load_one_defect(rec_id)
        if record:
            edit_defect_dialog(record)
