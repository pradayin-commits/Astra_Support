import os
import datetime as dt
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text
import plotly.express as px

# ==========================================
# 1. APPLE-INSPIRED DESIGN (CSS)
# ==========================================
st.set_page_config(page_title="Astra", page_icon="🛡️", layout="wide")

st.markdown("""
    <style>
    /* Clean Apple-like Background & Typography */
    .stApp { background-color: #ffffff; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
    
    /* Subtle Glassmorphism KPI Cards */
    .metric-card {
        border-radius: 16px; padding: 24px; color: #1d1d1f; margin-bottom: 10px;
        background: #f5f5f7; border: 1px solid #d2d2d7;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        transition: transform 0.2s ease;
    }
    .metric-card:hover { transform: translateY(-2px); }
    .metric-card h3 { margin: 0; font-size: 14px; font-weight: 500; color: #86868b; }
    .metric-card h1 { margin: 10px 0 0 0; font-size: 36px; font-weight: 600; }

    /* Green Primary Button (Apple Green) */
    div[data-testid="stButton"] > button {
        background-color: #34c759 !important;
        color: white !important;
        border-radius: 12px !important;
        border: none !important;
        padding: 10px 24px !important;
        font-weight: 600 !important;
        width: 100%;
    }
    
    /* Clean Tabs */
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { font-weight: 600; color: #86868b; }
    .stTabs [aria-selected="true"] { color: #0071e3 !important; border-bottom-color: #0071e3 !important; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. DATABASE & CONSTANTS
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

# ==========================================
# 3. CREATE MODAL
# ==========================================
@st.dialog("➕ New Defect")
def create_defect_dialog():
    with st.form("new_form", clear_on_submit=True):
        t = st.text_input("Defect Title")
        c1, c2 = st.columns(2)
        m = c1.selectbox("Module", MODULES)
        p = c2.selectbox("Priority", PRIORITIES)
        rep = st.text_input("Reported By")
        if st.form_submit_button("Commit to Astra"):
            new_record = {"t": t, "m": m, "p": p, "r": rep, "s": "New", "now": dt.datetime.now()}
            with get_engine().begin() as conn:
                conn.execute(text("INSERT INTO public.defects (defect_title, module, priority, reported_by, status, created_at) VALUES (:t, :m, :p, :r, :s, :now)"), new_record)
            st.rerun()

# ==========================================
# 4. MAIN APP EXECUTION
# ==========================================
df = load_data()

# --- HEADER & KPI ---
st.title("🛡️ Astra")
if not df.empty:
    k1, k2, k3 = st.columns(3)
    k1.markdown(f'<div class="metric-card"><h3>Global Defects</h3><h1>{len(df)}</h1></div>', unsafe_allow_html=True)
    k2.markdown(f'<div class="metric-card"><h3>Active</h3><h1>{len(df[~df["status"].isin(["Resolved", "Closed"])])}</h1></div>', unsafe_allow_html=True)
    k3.markdown(f'<div class="metric-card"><h3>Resolved</h3><h1>{len(df[df["status"].isin(["Resolved", "Closed"])])}</h1></div>', unsafe_allow_html=True)

# --- CREATE BUTTON POSITIONED ABOVE TABS ---
st.write("")
_, btn_col = st.columns([0.8, 0.2])
with btn_col:
    if st.button("➕ CREATE NEW DEFECT"):
        create_defect_dialog()

# --- TABBED CONTENT ---
tab_insights, tab_explorer = st.tabs(["📊 Performance Insights", "📂 Workspace Explorer"])

with tab_insights:
    if not df.empty:
        st.subheader("Dynamic Analytics")
        # --- DRILL DOWN DROPDOWNS ---
        c1, c2 = st.columns(2)
        
        # 1. Select Column
        analysis_col = c1.selectbox("Analyze By (Column Name)", 
                                     options=["module", "priority", "status", "reported_by"], 
                                     format_func=lambda x: x.replace("_", " ").title())
        
        # 2. Select Dynamic Value
        unique_vals = sorted(df[analysis_col].unique().tolist())
        selected_val = c2.selectbox(f"Select Specific {analysis_col.title()}", options=["All"] + unique_vals)
        
        # Filter data for chart based on selections
        chart_df = df if selected_val == "All" else df[df[analysis_col] == selected_val]
        
        # --- CHARTS ---
        g1, g2 = st.columns(2)
        with g1:
            fig_pie = px.pie(chart_df, names='status', hole=0.6, title="Status Breakdown",
                             color_discrete_sequence=px.colors.qualitative.Prism)
            fig_pie.update_layout(margin=dict(t=40, b=0, l=0, r=0))
            st.plotly_chart(fig_pie, use_container_width=True)
        
        with g2:
            # Dynamic Bar Chart based on the analysis column
            bar_data = chart_df.groupby(analysis_col).size().reset_index(name='Count')
            fig_bar = px.bar(bar_data, x=analysis_col, y='Count', title=f"Volume by {analysis_col.title()}",
                             color_discrete_sequence=['#0071e3'])
            fig_bar.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.info("Awaiting data...")

with tab_explorer:
    st.subheader("Interactive Workspace")
    st.caption("Apple Experience: Edit values directly in the table below. Changes will sync to the cloud.")
    
    # --- APPLE-LIKE INLINE EDITING ---
    # We use st.data_editor to allow direct editing
    edited_df = st.data_editor(
        df,
        key="main_editor",
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic", # Allows adding/deleting rows directly
        column_config={
            "status": st.column_config.SelectboxColumn("Status", options=STATUSES, required=True),
            "priority": st.column_config.SelectboxColumn("Priority", options=PRIORITIES, required=True),
            "module": st.column_config.SelectboxColumn("Module", options=MODULES, required=True),
            "created_at": st.column_config.DatetimeColumn("Created At", disabled=True),
        }
    )

    # Logic to sync edited data back to Supabase
    if st.button("🚀 Sync Changes to Cloud"):
        with get_engine().begin() as conn:
            # In a production environment, you would compare dataframes to update only changed rows.
            # For simplicity here, we replace the table data.
            edited_df.to_sql("defects", conn, if_exists="replace", index=False, schema="public")
        st.success("Cloud Synchronization Complete.")
        st.rerun()
