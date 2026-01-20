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

st.markdown("""
    <style>
    [data-testid="stSidebar"] { display: none; }
    .stApp { background-color: #f5f5f7; }
    
    /* Remove top white space */
    .block-container {
        padding-top: 0.2rem !important;
        margin-top: -3.8rem !important;
    }

    /* Small & Sleek KPI Buckets */
    div[data-testid="stMetric"] {
        background-color: white;
        border: 1px solid #d2d2d7;
        border-radius: 8px;
        padding: 5px 10px !important;
        height: 85px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
    }
    
    div[data-testid="stMetricValue"] {
        font-size: 22px !important;
        font-weight: 600 !important;
    }

    /* Small Export Button */
    .stDownloadButton button {
        padding: 0.1rem 0.4rem !important;
        font-size: 11px !important;
        height: 24px !important;
        border-radius: 4px !important;
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
        st.error("Missing Database URL")
        st.stop()
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

# ==========================================
# 3. MODALS
# ==========================================
@st.dialog("✏️ Edit Defect")
def edit_modal(row):
    with st.form("edit_form", border=False):
        c1, c2 = st.columns(2)
        new_title = c1.text_input("Title", value=row["defect_title"])
        status_opts = ["New", "In Progress", "Blocked", "Resolved", "Closed"]
        new_status = c2.selectbox("Status", status_opts, index=status_opts.index(row["status"]) if row["status"] in status_opts else 0)
        new_pri = c1.selectbox("Priority", ["P1 - Critical", "P2 - High", "P3 - Medium", "P4 - Low"], index=1)
        new_resp = c2.text_input("Responsible", value=row.get("responsible", ""))
        
        if st.form_submit_button("Update Astra", type="primary", use_container_width=True):
            with get_engine().begin() as conn:
                conn.execute(text("UPDATE public.defects SET defect_title=:t, status=:s, priority=:p, responsible=:r WHERE defect_id=:id"),
                             {"t": new_title, "s": new_status, "p": new_pri, "r": new_resp, "id": row["defect_id"]})
            st.rerun()

# ==========================================
# 4. MAIN UI
# ==========================================
df = load_data()

# --- HEADER (Centered Alignment) ---
h_col1, h_col2 = st.columns([0.5, 10])
with h_col1:
    if os.path.exists("logo.png"):
        st.image("logo.png", width=60)
    else:
        st.write("🍏")
with h_col2:
    st.markdown(f"<h2 style='margin:0;'>{APP_NAME}</h2>", unsafe_allow_html=True)

# --- COMPACT KPI BUCKETS ---
if not df.empty:
    k1, k2, k3, k4, k_space = st.columns([1, 1, 1, 1, 3])
    k1.metric("Global", len(df))
    k2.metric("Open", len(df[~df['status'].isin(["Resolved", "Closed"])]))
    k3.metric("Resolved", len(df[df['status'].isin(["Resolved", "Closed"])]))

st.divider()

# TAB PERSISTENCE: 'key' prevents the reset to Tab 1 on every interaction
selected_tab = st.tabs(["📂 Explorer", "➕ Register", "📊 Insights"])

with selected_tab[0]:
    search_col, export_col = st.columns([11, 1])
    with search_col:
        search_query = st.text_input("🔍 Search", placeholder="Filter by any value...", label_visibility="collapsed")
    with export_col:
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 CSV", data=csv, file_name="astra.csv")

    if not df.empty:
        display_df = df[df.astype(str).apply(lambda x: x.str.contains(search_query, case=False)).any(axis=1)] if search_query else df
        selection = st.dataframe(display_df, use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row")
        rows = selection.get("selection", {}).get("rows", [])
        if rows:
            edit_modal(display_df.iloc[rows[0]])

with selected_tab[1]:
    with st.form("reg_form", clear_on_submit=True):
        st.subheader("Register New Defect")
        c1, c2 = st.columns(2)
        comp = c1.selectbox("Company", ["4310", "8410"])
        mod = c2.selectbox("Module", ["PLM", "PP", "FI", "SD", "MM", "QM"])
        title = st.text_input("Summary *")
        pri = st.selectbox("Priority", ["P1 - Critical", "P2 - High", "P3 - Medium", "P4 - Low"], index=2)
        rep = st.text_input("Reporter *")
        if st.form_submit_button("Submit", type="primary"):
            # Insertion logic would go here
            st.success("Entry queued for processing...")
            st.rerun()

with selected_tab[2]:
    if not df.empty:
        st.subheader("📊 Dynamic Analysis")
        
        # COLUMN FILTERING (Exclude meta-data)
        excluded = ["defect_id", "description", "comments", "created_at", "updated_at", "defect_title"]
        available_cols = [c for c in df.columns if c not in excluded]
        
        # CASCADING SELECTORS
        sel_c1, sel_c2 = st.columns(2)
        category = sel_c1.selectbox("Step 1: Select Category", available_cols, key="dynamic_cat_select")
        
        # UPDATING CIRCLE (Spinner)
        with st.spinner("Updating charts..."):
            sub_values = df[category].unique().tolist()
            selected_sub = sel_c2.multiselect(f"Step 2: Filter {category}", sub_values, default=sub_values, key="dynamic_sub_select")
            
            chart_df = df[df[category].isin(selected_sub)]
            
            if not chart_df.empty:
                c1, c2 = st.columns(2)
                with c1:
                    st.write(f"**{category.title()} Distribution**")
                    fig_pie = px.pie(chart_df, names=category, hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
                    st.plotly_chart(fig_pie, use_container_width=True)
                with c2:
                    st.write(f"**Count by {category.title()}**")
                    bar_data = chart_df[category].value_counts().reset_index()
                    bar_data.columns = [category, 'Count']
                    fig_bar = px.bar(bar_data, x=category, y='Count', color=category, color_discrete_sequence=px.colors.qualitative.Safe)
                    st.plotly_chart(fig_bar, use_container_width=True)
            else:
                st.warning("No data matches the selected filters.")
