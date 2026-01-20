import os
import datetime as dt
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text
import plotly.express as px

# ==========================================
# 1. DESIGN & BRANDING (HIGH-FIDELITY MOCKUP)
# ==========================================
APP_NAME = "Astra Defect Tracker"
st.set_page_config(page_title=APP_NAME, page_icon="🛡️", layout="wide")

st.markdown("""
    <style>
    /* Main Background */
    .stApp { background-color: #f8f9fa; }
    
    /* Buffer at the top to prevent cut-off */
    .block-container {
        padding-top: 2.5rem !important;
    }

    /* KPI Bucket Styling - Vibrant Cards */
    .metric-card {
        border-radius: 12px;
        padding: 20px;
        color: white;
        margin-bottom: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .global-bucket { background: linear-gradient(135deg, #1e5799 0%, #2989d8 100%); }
    .open-bucket { background: linear-gradient(135deg, #e67e22 0%, #d35400 100%); }
    .resolved-bucket { background: linear-gradient(135deg, #27ae60 0%, #2ecc71 100%); }
    
    .metric-card h3 { margin: 0; font-size: 16px; opacity: 0.9; }
    .metric-card h1 { margin: 0; font-size: 32px; font-weight: 700; }

    /* Heading Alignment */
    .header-row { display: flex; align-items: center; gap: 20px; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. DATABASE ENGINE
# ==========================================
@st.cache_resource
def get_engine():
    db_url = st.secrets.get("SUPABASE_DATABASE_URL") or os.getenv("SUPABASE_DATABASE_URL")
    if not db_url:
        st.error("Missing Database URL")
        st.stop()
    db_url = db_url.strip().replace("postgres://", "postgresql+psycopg2://", 1)
    return create_engine(db_url, pool_pre_ping=True, connect_args={"sslmode": "require"})

@st.cache_data(ttl=2)
def load_data():
    q = text("SELECT * FROM public.defects ORDER BY created_at DESC")
    try:
        with get_engine().connect() as conn:
            return pd.read_sql(q, conn)
    except:
        return pd.DataFrame()

# ==========================================
# 3. MAIN UI EXECUTION
# ==========================================
df = load_data()

# --- SIDEBAR FILTERS (PREVENTS JUMPING) ---
with st.sidebar:
    st.markdown("## 🛡️ Astra Control")
    if not df.empty:
        # Filtering dropdowns that contain all column values
        available_modules = sorted(df['module'].unique().tolist())
        sel_module = st.multiselect("Select Modules", available_modules, default=available_modules)
        
        available_priorities = sorted(df['priority'].unique().tolist())
        sel_priority = st.multiselect("Select Priorities", available_priorities, default=available_priorities)
        
        # Filtering logic
        filtered_df = df[(df['module'].isin(sel_module)) & (df['priority'].isin(sel_priority))]
    else:
        filtered_df = df

    st.divider()
    csv = filtered_df.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Export CSV", data=csv, file_name="astra_data.csv", use_container_width=True)

# --- HEADER WITH LOGO ---
header_col1, header_col2 = st.columns([0.8, 10])
with header_col1:
    if os.path.exists("logo.png"):
        st.image("logo.png", width=80)
    else:
        st.title("🛡️")
with header_col2:
    st.markdown(f"<h1 style='margin-top:10px;'>{APP_NAME}</h1>", unsafe_allow_html=True)

# --- VIBRANT KPI BUCKETS ---
if not df.empty:
    k1, k2, k3 = st.columns(3)
    with k1:
        st.markdown(f'<div class="metric-card global-bucket"><h3>Global Defects</h3><h1>{len(df)}</h1></div>', unsafe_allow_html=True)
    with k2:
        open_count = len(df[~df['status'].isin(["Resolved", "Closed"])])
        st.markdown(f'<div class="metric-card open-bucket"><h3>Open Defects</h3><h1>{open_count}</h1></div>', unsafe_allow_html=True)
    with k3:
        res_count = len(df[df['status'].isin(["Resolved", "Closed"])])
        st.markdown(f'<div class="metric-card resolved-bucket"><h3>Resolved</h3><h1>{res_count}</h1></div>', unsafe_allow_html=True)

st.divider()

# --- TABS ---
tab_explorer, tab_insights, tab_register = st.tabs(["📂 Workspace Explorer", "📊 Performance Insights", "➕ Register Defect"])

with tab_explorer:
    st.write("### Data Explorer")
    st.caption("Use the sidebar to filter. Click headers to sort like Excel.")
    st.dataframe(filtered_df, use_container_width=True, hide_index=True)

with tab_insights:
    if not filtered_df.empty:
        st.write("### Analytical Overview")
        c1, c2 = st.columns(2)
        
        with c1:
            # FIXED PIE CHART
            fig_pie = px.pie(filtered_df, names='status', hole=0.4, title="Defects by Status",
                             color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig_pie, use_container_width=True)
            
        with c2:
            # FIXED BAR CHART (VALUEERROR FIX)
            bar_data = filtered_df['priority'].value_counts().reset_index()
            bar_data.columns = ['Priority', 'Count'] # Explicitly naming columns
            fig_bar = px.bar(bar_data, x='Priority', y='Count', title="Priority Volume",
                             color='Priority', color_discrete_sequence=px.colors.qualitative.Safe)
            st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.info("Adjust filters in the sidebar to populate insights.")

with tab_register:
    st.subheader("Register New Defect")
    with st.form("new_defect"):
        title = st.text_input("Defect Summary *")
        mod = st.selectbox("Module", ["PLM", "PP", "FI", "SD", "MM", "QM"])
        pri = st.selectbox("Priority", ["P1 - Critical", "P2 - High", "P3 - Medium", "P4 - Low"])
        if st.form_submit_button("Commit to Astra"):
            st.success("Synchronizing with Database...")
