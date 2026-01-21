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
st.set_page_config(page_title=APP_NAME, page_icon="🛡️", layout="wide")

st.markdown("""
    <style>
    /* Overall Background */
    .stApp { background-color: #f8f9fa; }
    
    /* Metric Card Styling */
    .metric-card {
        border-radius: 12px; padding: 20px; color: white; margin-bottom: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .global-bucket { background: linear-gradient(135deg, #1e5799 0%, #2989d8 100%); }
    .open-bucket { background: linear-gradient(135deg, #e67e22 0%, #d35400 100%); }
    .resolved-bucket { background: linear-gradient(135deg, #27ae60 0%, #2ecc71 100%); }
    
    /* Aligning the Create Button */
    div[data-testid="stColumn"] > div > div > div > button {
        margin-top: 25px;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. DATABASE CONNECTION
# ==========================================
@st.cache_resource
def get_engine():
    # Looks for connection string in Streamlit Secrets or Environment Variables
    db_url = st.secrets.get("SUPABASE_DATABASE_URL") or os.getenv("SUPABASE_DATABASE_URL")
    if not db_url:
        st.error("Missing SUPABASE_DATABASE_URL. Please check your secrets.")
        st.stop()
    # Fix for SQLAlchemy 2.0+ and Supabase Postgres strings
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
    return create_engine(db_url, pool_pre_ping=True)

def load_data():
    q = text("SELECT * FROM public.defects ORDER BY created_at DESC")
    try:
        with get_engine().connect() as conn:
            return pd.read_sql(q, conn)
    except Exception as e:
        st.error(f"Database connection error: {e}")
        return pd.DataFrame()

# ==========================================
# 3. MODALS (CREATE DEFECT)
# ==========================================
@st.dialog("➕ Register New Defect")
def create_defect_dialog():
    with st.form("new_defect_form", clear_on_submit=True):
        title = st.text_input("Defect Summary *")
        col1, col2 = st.columns(2)
        mod = col1.selectbox("Module", ["PLM", "PP", "FI", "SD", "MM", "QM", "ABAP", "BASIS"])
        pri = col2.selectbox("Priority", ["P1 - Critical", "P2 - High", "P3 - Medium", "P4 - Low"])
        desc = st.text_area("Steps to Reproduce / Description")
        
        if st.form_submit_button("Submit to Database", use_container_width=True):
            if not title:
                st.error("Title is required.")
            else:
                new_data = {
                    "defect_title": title, "module": mod, "priority": pri,
                    "description": desc, "status": "New", "created_at": dt.datetime.now()
                }
                with get_engine().begin() as conn:
                    conn.execute(text("""
                        INSERT INTO public.defects (defect_title, module, priority, description, status, created_at)
                        VALUES (:defect_title, :module, :priority, :description, :status, :created_at)
                    """), new_data)
                st.success("Synchronized successfully!")
                st.rerun()

# ==========================================
# 4. MAIN APP LOGIC
# ==========================================
df = load_data()

# --- HEADER SECTION ---
col_title, col_btn = st.columns([0.8, 0.2])
with col_title:
    st.title(f"🛡️ {APP_NAME}")
    st.caption("Centralized Defect Management & Performance Tracking")

with col_btn:
    if st.button("➕ Create New", type="primary", use_container_width=True):
        create_defect_dialog()

# --- SIDEBAR SEARCH & FILTERS ---
with st.sidebar:
    st.markdown("### 🔍 Search & Filter")
    search_query = st.text_input("Global Search", placeholder="Search by title, desc...")
    
    if not df.empty:
        available_mods = sorted(df['module'].unique())
        sel_module = st.multiselect("Filter Modules", available_mods, default=available_mods)
        
        available_stats = sorted(df['status'].unique())
        sel_status = st.multiselect("Filter Status", available_stats, default=available_stats)
        
        # Filtering logic
        filtered_df = df[
            (df['module'].isin(sel_module)) & 
            (df['status'].isin(sel_status))
        ]
        
        if search_query:
            filtered_df = filtered_df[
                filtered_df.apply(lambda row: search_query.lower() in row.astype(str).str.lower().values, axis=1)
            ]
    else:
        filtered_df = df

# --- KPI METRICS ---
if not df.empty:
    k1, k2, k3 = st.columns(3)
    k1.markdown(f'<div class="metric-card global-bucket"><h3>Total Defects</h3><h1>{len(df)}</h1></div>', unsafe_allow_html=True)
    
    active_count = len(df[~df["status"].isin(["Resolved", "Closed"])])
    k2.markdown(f'<div class="metric-card open-bucket"><h3>Active Items</h3><h1>{active_count}</h1></div>', unsafe_allow_html=True)
    
    resolved_count = len(df[df["status"].isin(["Resolved", "Closed"])])
    k3.markdown(f'<div class="metric-card resolved-bucket"><h3>Resolved</h3><h1>{resolved_count}</h1></div>', unsafe_allow_html=True)

# --- TABBED CONTENT ---
tab_insights, tab_explorer = st.tabs(["📊 Performance Insights", "📂 Workspace Explorer"])

with tab_insights:
    if not filtered_df.empty:
        st.write("### Analytical Overview")
        c1, c2 = st.columns(2)
        
        with c1:
            # Status Pie Chart
            fig_pie = px.pie(filtered_df, names='status', hole=0.4, title="Status Distribution",
                             color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig_pie, use_container_width=True)
            
        with c2:
            # Priority Bar Chart
            # Grouping correctly to avoid the ValueError from before
            bar_data = filtered_df.groupby('priority').size().reset_index(name='Count')
            fig_bar = px.bar(bar_data, x='priority', y='Count', title="Priority Volume",
                             color='priority', color_discrete_sequence=px.colors.qualitative.Safe)
            st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.info("No data found for the current filters.")

with tab_explorer:
    st.write("### Data Explorer")
    st.dataframe(filtered_df, use_container_width=True, hide_index=True)
    
    # --- UPDATE SECTION ---
    if not filtered_df.empty:
        st.divider()
        st.write("### ✏️ Edit or Remove Defect")
        
        # User selects which defect to act on
        edit_target = st.selectbox("Select Defect Summary to modify:", filtered_df['defect_title'].tolist())
        target_row = filtered_df[filtered_df['defect_title'] == edit_target].iloc[0]
        
        with st.expander(f"Modify Record: {edit_target}"):
            col_u1, col_u2 = st.columns(2)
            
            new_status = col_u1.selectbox(
                "Change Status", 
                ["New", "In Progress", "Blocked", "Resolved", "Closed"],
                index=["New", "In Progress", "Blocked", "Resolved", "Closed"].index(target_row['status'])
            )
            
            new_priority = col_u2.selectbox(
                "Change Priority", 
                ["P1 - Critical", "P2 - High", "P3 - Medium", "P4 - Low"],
                index=["P1 - Critical", "P2 - High", "P3 - Medium", "P4 - Low"].index(target_row['priority'])
            )
            
            # Action Buttons
            btn_col1, btn_col2 = st.columns([0.2, 0.8])
            
            if btn_col1.button("Save Changes"):
                with get_engine().begin() as conn:
                    conn.execute(text("""
                        UPDATE public.defects 
                        SET status = :status, priority = :priority 
                        WHERE id = :id
                    """), {"status": new_status, "priority": new_priority, "id": target_row['id']})
                st.success("Updated!")
                st.rerun()
            
            if btn_col2.button("🗑️ Delete Defect", type="secondary"):
                # Simple deletion (consider adding a confirmation checkbox for production)
                with get_engine().begin() as conn:
                    conn.execute(text("DELETE FROM public.defects WHERE id = :id"), {"id": target_row['id']})
                st.warning("Defect deleted from database.")
                st.rerun()
