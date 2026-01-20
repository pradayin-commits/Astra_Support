import os
import datetime as dt
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text
import plotly.express as px

# ==========================================
# 1. DESIGN & BRANDING (APPLE AESTHETIC)
# ==========================================
APP_NAME = "Astra Defect Tracker"
st.set_page_config(page_title=APP_NAME, page_icon="🍏", layout="wide")

# Custom CSS for layout, logo alignment, and removing top white space
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
        box-shadow: 0 4px 6px rgba(0,0,0,0.02);
    }
    
    /* Horizontal Header Alignment */
    .header-box {
        display: flex;
        align-items: center;
        gap: 15px;
        margin-bottom: 10px;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. DATABASE ENGINE & UTILITIES
# ==========================================
@st.cache_resource
def get_engine():
    db_url = st.secrets.get("SUPABASE_DATABASE_URL") or os.getenv("SUPABASE_DATABASE_URL")
    if not db_url:
        st.error("Missing SUPABASE_DATABASE_URL in secrets.")
        st.stop()
    
    # Clean URL and inject correct driver
    db_url = db_url.strip()
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif db_url.startswith("postgresql://") and "+psycopg2" not in db_url:
        db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)
        
    return create_engine(db_url, pool_pre_ping=True, connect_args={"sslmode": "require"})

@st.cache_data(show_spinner=False, ttl=2)
def load_data():
    q = text("SELECT * FROM public.defects ORDER BY created_at DESC")
    try:
        with get_engine().connect() as conn:
            df = pd.read_sql(q, conn)
            if not df.empty:
                df["open_date"] = pd.to_datetime(df["open_date"]).dt.date
                df["resolved_date"] = pd.to_datetime(df["resolved_date"], errors="coerce").dt.date
                
                # Logic for "Time to Resolve" (Lead Time)
                def calc_lead_time(row):
                    if pd.notnull(row["resolved_date"]):
                        return (row["resolved_date"] - row["open_date"]).days
                    return (dt.date.today() - row["open_date"]).days
                
                df["Lead Time (Days)"] = df.apply(calc_lead_time, axis=1)
            return df
    except Exception as e:
        st.error(f"Engine connection failed: {e}")
        return pd.DataFrame()

def generate_id(module, code):
    try:
        with get_engine().begin() as conn:
            val = conn.execute(text("select nextval('public.defect_seq')")).scalar_one()
        return f"{module.upper()}-{code}-{(int(val)):03d}"
    except:
        return f"{module.upper()}-{code}-{dt.datetime.now().strftime('%S%f')[:3]}"

# ==========================================
# 3. INTERACTIVE MODALS (EDIT & DELETE)
# ==========================================
@st.dialog("✏️ Refine Defect")
def edit_modal(row):
    st.write(f"Editing Record: **{row['defect_id']}**")
    
    with st.form("edit_form", border=False):
        col1, col2 = st.columns(2)
        new_title = col1.text_input("Title", value=row["defect_title"])
        
        status_opts = ["New", "In Progress", "Blocked", "Resolved", "Closed"]
        s_idx = status_opts.index(row["status"]) if row["status"] in status_opts else 0
        new_status = col2.selectbox("Status", status_opts, index=s_idx)
        
        pri_opts = ["P1 - Critical", "P2 - High", "P3 - Medium", "P4 - Low"]
        p_idx = pri_opts.index(row["priority"]) if row["priority"] in pri_opts else 1
        new_pri = col1.selectbox("Priority", pri_opts, index=p_idx)
        
        new_resp = col2.text_input("Responsible Party", value=row.get("responsible", ""))
        new_desc = st.text_area("Detailed Notes", value=row.get("description", ""))
        
        res_date = row["resolved_date"]
        if new_status in ["Resolved", "Closed"]:
            res_date = st.date_input("Resolution Date", value=row["resolved_date"] or dt.date.today())

        if st.form_submit_button("Update Astra System", type="primary", use_container_width=True):
            with get_engine().begin() as conn:
                conn.execute(text("""
                    UPDATE public.defects SET 
                    defect_title=:title, status=:status, priority=:priority, 
                    responsible=:resp, description=:desc, resolved_date=:res, updated_at=NOW()
                    WHERE defect_id=:target_id
                """), {
                    "title": new_title, "status": new_status, "priority": new_pri, 
                    "resp": new_resp, "desc": new_desc, "res": res_date, "target_id": row["defect_id"]
                })
            st.success("Synchronized successfully.")
            load_data.clear()
            st.rerun()

    st.divider()
    if st.button("🗑️ Permanent Deletion", type="secondary", use_container_width=True):
        confirm_delete_modal(row["defect_id"])

@st.dialog("⚠️ Safety Check")
def confirm_delete_modal(defect_id):
    st.error(f"Are you sure? Deleting **{defect_id}** cannot be reversed.")
    if st.button("Confirm Deletion", type="primary", use_container_width=True):
        with get_engine().begin() as conn:
            conn.execute(text("DELETE FROM public.defects WHERE defect_id = :id"), {"id": defect_id})
        st.success("Record removed.")
        load_data.clear()
        st.rerun()

# ==========================================
# 4. MAIN DASHBOARD UI
# ==========================================
df = load_data()

# Logo + Header Row (Horizontal Alignment)
h_col1, h_col2 = st.columns([0.8, 9])
with h_col1:
    if os.path.exists("logo.png"):
        st.image("logo.png", width=90)
with h_col2:
    st.markdown(f"## {APP_NAME}")
    st.caption("Engineering & Quality Assurance Dashboard")

# Metric Buckets (The KPIs)
if not df.empty:
    m1, m2, m3, m4 = st.columns([1, 1, 1, 1])
    m1.metric("Global Defects", len(df))
    
    open_count = len(df[~df['status'].isin(["Resolved", "Closed"])])
    m2.metric("Open Defects", open_count)
    
    resolved_count = len(df[df['status'].isin(["Resolved", "Closed"])])
    m3.metric("Resolved Defects", resolved_count)
    # m4 kept empty to balance the top row

st.divider()

# Workspace Tabs
tab_explore, tab_register, tab_insights = st.tabs([
    "📂 Workspace Explorer", 
    "➕ Register Defect", 
    "📊 Performance Insights"
])

with tab_explore:
    if df.empty:
        st.info("The Astra database is currently empty.")
    else:
        # EXCEL EXPORT - Extreme Right Position
        top_c1, top_c2 = st.columns([10, 1.2])
        with top_c2:
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Export CSV", data=csv, file_name="astra_export.csv", use_container_width=True)
        
        st.write("Click a row to manage record details. Use column headers to sort/filter.")
        selection = st.dataframe(
            df, 
            use_container_width=True, 
            hide_index=True, 
            on_select="rerun", 
            selection_mode="single-row"
        )
        
        rows = selection.get("selection", {}).get("rows", [])
        if rows:
            edit_modal(df.iloc[rows[0]])

with tab_register:
    st.subheader("New Defect Entry")
    with st.form("new_entry_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        comp = c1.selectbox("Company Entity", ["4310", "8410"])
        mod = c2.selectbox("Core Module", ["PLM", "PP", "FI", "SD", "MM", "QM", "ABAP", "BASIS"])
        
        title = st.text_input("Summary *")
        
        c3, c4 = st.columns(2)
        pri = c3.selectbox("Severity", ["P1 - Critical", "P2 - High", "P3 - Medium", "P4 - Low"], index=2)
        rep = c4.text_input("Logged By *")
        
        desc = st.text_area("Observations / Steps to Reproduce")
        
        if st.form_submit_button("Commit to Database", type="primary"):
            if not title or not rep:
                st.warning("Required fields (*) are missing.")
            else:
                new_id = generate_id(mod, comp)
                with get_engine().begin() as conn:
                    conn.execute(text("""
                        INSERT INTO public.defects (defect_id, company_code, module, defect_title, priority, status, reported_by, description, open_date)
                        VALUES (:id, :comp, :mod, :title, :pri, 'New', :rep, :desc, :date)
                    """), {"id": new_id, "comp": comp, "mod": mod, "title": title, "pri": pri, "rep": rep, "desc": desc, "date": dt.date.today()})
                st.success(f"Successfully Registered: {new_id}")
                load_data.clear()
                st.rerun()

with tab_insights:
    if not df.empty:
        st.subheader("📊 Dynamic Chart Analysis")
        # Dynamic Column Selection for Charts
        choice = st.selectbox("Analyze Distribution By:", ["priority", "status", "module", "company_code"])
        
        # Prepare chart data (Fixed for ValueErrors)
        chart_data = df[choice].value_counts().reset_index()
        chart_data.columns = [choice, 'Count']
        
        c1, c2 = st.columns(2)
        with c1:
            st.write(f"**{choice.title()} Percentage (Pie)**")
            fig_pie = px.pie(chart_data, names=choice, values='Count', hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig_pie, use_container_width=True)
            
        with c2:
            st.write(f"**{choice.title()} Volume (Bar)**")
            fig_bar = px.bar(chart_data, x=choice, y='Count', color=choice, color_discrete_sequence=px.colors.qualitative.Safe)
            st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.info("Awaiting data for performance visualization.")
