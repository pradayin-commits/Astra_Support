import os
import datetime as dt
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text
import plotly.express as px

# ==========================================
# 1. DESIGN & BRANDING (MATCHING MOCKUP)
# ==========================================
APP_NAME = "Astra Defect Tracker"
st.set_page_config(page_title=APP_NAME, page_icon="🛡️", layout="wide")

st.markdown("""
    <style>
    /* Main Background */
    .stApp { background-color: #f8f9fa; }
    
    /* Top Buffer Fix */
    .block-container {
        padding-top: 2rem !important;
    }

    /* KPI Bucket Styling - Matching the Image */
    .metric-card {
        border-radius: 12px;
        padding: 20px;
        color: white;
        margin-bottom: 10px;
    }
    .global-bucket { background: linear-gradient(135deg, #1e5799 0%, #2989d8 100%); }
    .open-bucket { background: linear-gradient(135deg, #e67e22 0%, #d35400 100%); }
    .resolved-bucket { background: linear-gradient(135deg, #27ae60 0%, #2ecc71 100%); }

    /* Heading Styling */
    h1 { color: #2c3e50; font-weight: 700; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. DATABASE ENGINE
# ==========================================
@st.cache_resource
def get_engine():
    db_url = st.secrets.get("SUPABASE_DATABASE_URL") or os.getenv("SUPABASE_DATABASE_URL")
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

# --- SIDEBAR FILTERS (STOP REFRESH JUMPING) ---
with st.sidebar:
    st.title("🛡️ Astra")
    st.subheader("Dashboard Filters")
    
    if not df.empty:
        sel_module = st.multiselect("Module", df['module'].unique(), default=df['module'].unique())
        sel_priority = st.multiselect("Priority", df['priority'].unique(), default=df['priority'].unique())
        
        # Apply filters immediately to the dataframe
        filtered_df = df[(df['module'].isin(sel_module)) & (df['priority'].isin(sel_priority))]
    else:
        filtered_df = df

    st.divider()
    csv = filtered_df.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Export CSV", data=csv, file_name="astra_data.csv", use_container_width=True)

# --- HEADER ---
st.title(APP_NAME)

# --- KPI BUCKETS (COLORED CARDS) ---
if not df.empty:
    k1, k2, k3 = st.columns(3)
    
    with k1:
        st.markdown(f'<div class="metric-card global-bucket"><h3>Global Defects</h3><h1>{len(df)}</h1></div>', unsafe_allow_html=True)
    with k2:
        open_num = len(df[~df['status'].isin(["Resolved", "Closed"])])
        st.markdown(f'<div class="metric-card open-bucket"><h3>Open Defects</h3><h1>{open_num}</h1></div>', unsafe_allow_html=True)
    with k3:
        res_num = len(df[df['status'].isin(["Resolved", "Closed"])])
        st.markdown(f'<div class="metric-card resolved-bucket"><h3>Resolved</h3><h1>{res_num}</h1></div>', unsafe_allow_html=True)

st.divider()

# --- MAIN CONTENT AREA ---
tab_explorer, tab_insights, tab_register = st.tabs(["📂 Workspace Explorer", "📊 Performance Insights", "➕ Register Defect"])

with tab_explorer:
    st.write("### All Defects")
    st.caption("Use the Sidebar to filter results. Select a row to manage record details.")
    
    # Selection logic
    selection = st.dataframe(
        filtered_df, 
        use_container_width=True, 
        hide_index=True, 
        on_select="rerun", 
        selection_mode="single-row"
    )

with tab_insights:
    if not filtered_df.empty:
        st.write("### Data Distribution")
        c1, c2 = st.columns(2)
        with c1:
            fig_pie = px.pie(filtered_df, names='status', hole=0.4, title="Status Breakdown",
                             color_discrete_sequence=px.colors.qualitative.Bold)
            st.plotly_chart(fig_pie, use_container_width=True)
        with c2:
            fig_bar = px.bar(filtered_df['priority'].value_counts().reset_index(), 
                             x='index', y='priority', title="Priority Volume",
                             labels={'index': 'Priority', 'priority': 'Count'})
            st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.info("Adjust filters to view insights.")

with tab_register:
    with st.form("new_reg"):
        st.subheader("Log New Defect")
        reg_c1, reg_c2 = st.columns(2)
        new_title = reg_c1.text_input("Summary *")
        new_mod = reg_c2.selectbox("Module", ["PLM", "PP", "FI", "SD", "MM", "QM"])
        new_pri = reg_c1.selectbox("Priority", ["P1", "P2", "P3", "P4"])
        if st.form_submit_button("Submit to Astra"):
            st.success("Synchronizing...")
