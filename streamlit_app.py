import os
import datetime as dt
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text
import plotly.express as px

# ==========================================
# 1. DESIGN & BRANDING
# ==========================================
APP_NAME = "Astra Defect Tracker"
st.set_page_config(page_title=APP_NAME, page_icon="🍏", layout="wide")

# Custom CSS for layout fixes
st.markdown("""
    <style>
    [data-testid="stSidebar"] { display: none; }
    .stApp { background-color: #f5f5f7; }
    
    /* Remove top white space */
    .block-container {
        padding-top: 0rem !important;
        margin-top: -3.5rem !important;
    }

    /* KPI Buckets Styling */
    div[data-testid="stMetric"] {
        background-color: white;
        border: 1px solid #d2d2d7;
        border-radius: 12px;
        padding: 15px !important;
    }
    
    /* Aligning Logo and Title */
    .title-wrapper {
        display: flex;
        align-items: center;
        gap: 20px;
        padding: 10px 0;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. DATABASE & DATA LOADING
# ==========================================
@st.cache_resource
def get_engine():
    db_url = st.secrets.get("SUPABASE_DATABASE_URL") or os.getenv("SUPABASE_DATABASE_URL")
    if not db_url:
        st.error("Missing database URL.")
        st.stop()
    db_url = db_url.strip().replace("postgres://", "postgresql+psycopg2://", 1)
    return create_engine(db_url, pool_pre_ping=True)

@st.cache_data(ttl=2)
def load_data():
    q = text("SELECT * FROM public.defects ORDER BY created_at DESC")
    try:
        with get_engine().connect() as conn:
            df = pd.read_sql(q, conn)
            if not df.empty:
                df["open_date"] = pd.to_datetime(df["open_date"]).dt.date
                df["resolved_date"] = pd.to_datetime(df["resolved_date"], errors="coerce").dt.date
            return df
    except:
        return pd.DataFrame()

def generate_id(module, code):
    try:
        with get_engine().begin() as conn:
            val = conn.execute(text("select nextval('public.defect_seq')")).scalar_one()
        return f"{module.upper()}-{code}-{(int(val)):03d}"
    except:
        return f"{module.upper()}-{code}-{dt.datetime.now().strftime('%S%f')[:3]}"

# ==========================================
# 3. INTERACTIVE MODALS
# ==========================================
@st.dialog("✏️ Edit Defect")
def edit_modal(row):
    with st.form("edit_form", border=False):
        c1, c2 = st.columns(2)
        new_title = c1.text_input("Title", value=row["defect_title"])
        new_status = c2.selectbox("Status", ["New", "In Progress", "Blocked", "Resolved", "Closed"], 
                                 index=["New", "In Progress", "Blocked", "Resolved", "Closed"].index(row["status"]))
        
        new_pri = c1.selectbox("Priority", ["P1 - Critical", "P2 - High", "P3 - Medium", "P4 - Low"],
                               index=["P1 - Critical", "P2 - High", "P3 - Medium", "P4 - Low"].index(row["priority"]))
        new_resp = c2.text_input("Responsible", value=row.get("responsible", ""))
        
        if st.form_submit_button("Update Astra", type="primary", use_container_width=True):
            with get_engine().begin() as conn:
                conn.execute(text("""
                    UPDATE public.defects SET defect_title=:t, status=:s, priority=:p, responsible=:r, updated_at=NOW() 
                    WHERE defect_id=:id
                """), {"t": new_title, "s": new_status, "p": new_pri, "r": new_resp, "id": row["defect_id"]})
            load_data.clear()
            st.rerun()

# ==========================================
# 4. MAIN UI
# ==========================================
df = load_data()

# Logo + Header Row
head_col1, head_col2 = st.columns([1, 8])
with head_col1:
    if os.path.exists("logo.png"):
        st.image("logo.png", width=100)
with head_col2:
    st.markdown(f"## {APP_NAME}")

# Metric Buckets
m1, m2, m3 = st.columns(3)
if not df.empty:
    m1.metric("Global Defects", len(df))
    m2.metric("Open Defects", len(df[~df['status'].isin(["Resolved", "Closed"])]))
    m3.metric("Resolved", len(df[df['status'].isin(["Resolved", "Closed"])]))

st.divider()

tab_explore, tab_register, tab_insights = st.tabs(["📂 Explorer", "➕ Register", "📊 Insights"])

with tab_explore:
    if df.empty:
        st.info("No data found.")
    else:
        # EXCEL EXPORT - Extreme Right Position
        top_c1, top_c2 = st.columns([9, 1])
        with top_c2:
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Export", data=csv, file_name="astra.csv", use_container_width=True)
        
        # EXCEL-STYLE TABLE WITH FILTERING
        # Use the global search and column sorting for the Excel feel
        selection = st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            column_config={
                "defect_id": st.column_config.TextColumn("ID", width="small"),
                "status": st.column_config.SelectboxColumn("Status", options=["New", "In Progress", "Blocked", "Resolved", "Closed"])
            }
        )
        
        rows = selection.get("selection", {}).get("rows", [])
        if rows:
            edit_modal(df.iloc[rows[0]])

with tab_register:
    with st.form("reg_form"):
        c1, c2 = st.columns(2)
        comp = c1.selectbox("Company", ["4310", "8410"])
        mod = c2.selectbox("Module", ["PLM", "PP", "FI", "SD", "MM", "QM", "ABAP"])
        title = st.text_input("Summary *")
        pri = st.selectbox("Priority", ["P1 - Critical", "P2 - High", "P3 - Medium", "P4 - Low"], index=2)
        rep = st.text_input("Reporter *")
        if st.form_submit_button("Submit to Database", type="primary"):
            if title and rep:
                new_id = generate_id(mod, comp)
                with get_engine().begin() as conn:
                    conn.execute(text("""
                        INSERT INTO public.defects (defect_id, company_code, module, defect_title, priority, status, reported_by, open_date)
                        VALUES (:id, :c, :m, :t, :p, 'New', :r, :d)
                    """), {"id": new_id, "c": comp, "m": mod, "t": title, "p": pri, "r": rep, "d": dt.date.today()})
                load_data.clear()
                st.rerun()

with tab_insights:
    if not df.empty:
        choice = st.selectbox("Analyze By:", ["priority", "status", "module"])
        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(px.pie(df, names=choice, hole=0.4), use_container_width=True)
        with c2:
            st.plotly_chart(px.bar(df[choice].value_counts().reset_index(), x='index', y=choice), use_container_width=True)
