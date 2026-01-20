import os
import datetime as dt
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text
import plotly.express as px

# ==========================================
# 1. DESIGN & BRANDING (CENTERED & LEAN)
# ==========================================
APP_NAME = "Astra Defect Tracker"
st.set_page_config(page_title=APP_NAME, page_icon="🍏", layout="wide")

# Custom CSS to remove sidebar, center header, and pull app up
st.markdown("""
    <style>
    /* Remove sidebar space */
    [data-testid="stSidebar"] { display: none; }
    
    .stApp { background-color: #f5f5f7; }
    
    /* Pull app to the very top */
    .block-container {
        padding-top: 0.5rem !important;
        margin-top: -3.5rem !important;
    }

    /* Centered Header */
    .header-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        text-align: center;
        padding-bottom: 10px;
    }

    /* KPI Buckets Styling */
    div[data-testid="stMetric"] {
        background-color: white;
        border: 1px solid #d2d2d7;
        border-radius: 16px;
        padding: 15px !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.02);
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. DATABASE ENGINE
# ==========================================
@st.cache_resource
def get_engine():
    db_url = st.secrets.get("SUPABASE_DATABASE_URL") or os.getenv("SUPABASE_DATABASE_URL")
    if not db_url:
        st.error("Missing SUPABASE_DATABASE_URL.")
        st.stop()
    # Ensure URL is clean for SQLAlchemy
    db_url = db_url.strip().replace("postgres://", "postgresql+psycopg2://", 1)
    return create_engine(db_url, pool_pre_ping=True, connect_args={"sslmode": "require"})

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
@st.dialog("✏️ Refine Defect")
def edit_modal(row):
    st.write(f"Editing Record: **{row['defect_id']}**")
    with st.form("edit_form", border=False):
        col1, col2 = st.columns(2)
        new_title = col1.text_input("Title", value=row["defect_title"])
        
        status_opts = ["New", "In Progress", "Blocked", "Resolved", "Closed"]
        curr_status_idx = status_opts.index(row["status"]) if row["status"] in status_opts else 0
        new_status = col2.selectbox("Status", status_opts, index=curr_status_idx)
        
        pri_opts = ["P1 - Critical", "P2 - High", "P3 - Medium", "P4 - Low"]
        curr_pri_idx = pri_opts.index(row["priority"]) if row["priority"] in pri_opts else 1
        new_pri = col1.selectbox("Priority", pri_opts, index=curr_pri_idx)
        
        new_resp = col2.text_input("Responsible Party", value=row.get("responsible", ""))
        new_desc = st.text_area("Detailed Notes", value=row.get("description", ""))
        
        res_date = row["resolved_date"]
        if new_status in ["Resolved", "Closed"]:
            res_date = st.date_input("Resolution Date", value=row["resolved_date"] or dt.date.today())

        if st.form_submit_button("Update System", type="primary", use_container_width=True):
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
            st.success("Synchronized.")
            load_data.clear()
            st.rerun()

    if st.button("🗑️ Delete Record", type="secondary", use_container_width=True):
        confirm_delete(row["defect_id"])

@st.dialog("⚠️ Safety Check")
def confirm_delete(defect_id):
    st.error("Permanent Deletion?")
    if st.button("Confirm", type="primary", use_container_width=True):
        with get_engine().begin() as conn:
            conn.execute(text("DELETE FROM public.defects WHERE defect_id = :id"), {"id": defect_id})
        load_data.clear()
        st.rerun()

# ==========================================
# 4. MAIN UI EXECUTION
# ==========================================
df = load_data()

# --- HEADER & LOGO ---
st.markdown('<div class="header-container">', unsafe_allow_html=True)
if os.path.exists("logo.png"):
    st.image("logo.png", width=120)
else:
    st.title("🍏 ASTRA")
st.title(f"{APP_NAME}")
st.markdown('</div>', unsafe_allow_html=True)

# --- KPI BUCKETS ---
if not df.empty:
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Global Defects", len(df))
    m2.metric("Open Defects", len(df[~df['status'].isin(["Resolved", "Closed"])]))
    m3.metric("Resolved", len(df[df['status'].isin(["Resolved", "Closed"])]))
    
    csv = df.to_csv(index=False).encode('utf-8')
    m4.download_button("📥 Export CSV", data=csv, file_name="astra_export.csv", use_container_width=True)

st.divider()

# --- WORKSPACE TABS ---
tab_explore, tab_register, tab_insights = st.tabs(["📂 Explorer", "➕ Register", "📊 Dynamic Insights"])

with tab_explore:
    if df.empty:
        st.info("Database Empty.")
    else:
        st.caption("Excel-style: Click headers to sort or use the search icon in the top right of the table.")
        selection = st.dataframe(df, use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row")
        
        rows = selection.get("selection", {}).get("rows", [])
        if rows:
            edit_modal(df.iloc[rows[0]])

with tab_register:
    st.subheader("Add New Defect")
    with st.form("new_entry_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        comp = c1.selectbox("Company", ["4310", "8410"])
        mod = c2.selectbox("Module", ["PLM", "PP", "FI", "SD", "MM", "QM", "ABAP", "BASIS"])
        title = st.text_input("Summary *")
        c3, c4 = st.columns(2)
        pri = c3.selectbox("Priority", ["P1 - Critical", "P2 - High", "P3 - Medium", "P4 - Low"], index=2)
        rep = c4.text_input("Reporter *")
        desc = st.text_area("Details")
        
        if st.form_submit_button("Commit to Astra", type="primary"):
            if title and rep:
                new_id = generate_id(mod, comp)
                with get_engine().begin() as conn:
                    conn.execute(text("""
                        INSERT INTO public.defects (defect_id, company_code, module, defect_title, priority, status, reported_by, description, open_date)
                        VALUES (:id, :comp, :mod, :title, :pri, 'New', :rep, :desc, :date)
                    """), {"id": new_id, "comp": comp, "mod": mod, "title": title, "pri": pri, "rep": rep, "desc": desc, "date": dt.date.today()})
                st.success(f"Registered: {new_id}")
                load_data.clear()
                st.rerun()

with tab_insights:
    if not df.empty:
        st.subheader("📊 Dynamic Chart Analysis")
        # Select the column to slice the data by
        chart_col = st.selectbox("Select Column to Analyze", ["priority", "status", "module", "company_code"], index=0)
        
        c1, c2 = st.columns(2)
        with c1:
            st.write(f"**{chart_col.title()} Distribution (Pie)**")
            fig_pie = px.pie(df, names=chart_col, hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig_pie, use_container_width=True)
            
        with c2:
            st.write(f"**{chart_col.title()} Count (Bar)**")
            counts = df[chart_col].value_counts().reset_index()
            # Handle column name differences in pandas versions
            counts.columns = [chart_col, 'count']
            fig_bar = px.bar(counts, x=chart_col, y='count', color=chart_col, color_discrete_sequence=px.colors.qualitative.Safe)
            st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.info("No data for insights.")
