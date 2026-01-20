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
    
    /* ADDED BUFFER AT THE TOP - STOPPING CUT-OFF */
    .block-container {
        padding-top: 2rem !important; 
        margin-top: 0rem !important;
    }

    /* KPI Buckets - Clean & Compact */
    div[data-testid="stMetric"] {
        background-color: white;
        border: 1px solid #d2d2d7;
        border-radius: 10px;
        padding: 10px !important;
        height: 90px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
    }
    
    div[data-testid="stMetricValue"] {
        font-size: 24px !important;
    }

    /* Small Export Button */
    .stDownloadButton button {
        padding: 0.1rem 0.5rem !important;
        font-size: 11px !important;
        height: 26px !important;
    }

    /* Header Alignment Logic */
    .main-header {
        display: flex;
        align-items: center;
        margin-bottom: 20px;
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

# --- HEADER (Fixed Logo & Text Visibility) ---
h_col1, h_col2 = st.columns([0.8, 10])
with h_col1:
    if os.path.exists("logo.png"):
        st.image("logo.png", width=75)
    else:
        st.title("🍏") 
with h_col2:
    st.markdown(f"<h1 style='margin:0; padding-top:10px;'>{APP_NAME}</h1>", unsafe_allow_html=True)

# --- KPI BUCKETS ---
if not df.empty:
    k1, k2, k3, k4 = st.columns([1, 1, 1, 2.5]) # Metrics on left, space on right
    k1.metric("Global", len(df))
    k2.metric("Open", len(df[~df['status'].isin(["Resolved", "Closed"])]))
    k3.metric("Resolved", len(df[df['status'].isin(["Resolved", "Closed"])]))

st.divider()

# PERSISTENT TABS
tabs = st.tabs(["📂 Explorer", "➕ Register", "📊 Insights"])

with tabs[0]:
    search_col, export_col = st.columns([11, 1])
    with search_col:
        search_query = st.text_input("🔍 Search", placeholder="Filter table...", label_visibility="collapsed")
    with export_col:
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 CSV", data=csv, file_name="astra.csv")

    if not df.empty:
        display_df = df[df.astype(str).apply(lambda x: x.str.contains(search_query, case=False)).any(axis=1)] if search_query else df
        selection = st.dataframe(display_df, use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row")
        rows = selection.get("selection", {}).get("rows", [])
        if rows:
            edit_modal(display_df.iloc[rows[0]])

with tabs[1]:
    with st.form("reg_form", clear_on_submit=True):
        st.subheader("New Entry")
        c1, c2 = st.columns(2)
        comp = c1.selectbox("Company", ["4310", "8410"])
        mod = c2.selectbox("Module", ["PLM", "PP", "FI", "SD", "MM", "QM"])
        title = st.text_input("Summary *")
        pri = st.selectbox("Priority", ["P1 - Critical", "P2 - High", "P3 - Medium", "P4 - Low"], index=2)
        rep = st.text_input("Reporter *")
        if st.form_submit_button("Submit", type="primary"):
            st.success("Synchronizing with Database...")
            st.rerun()

with tabs[2]:
    if not df.empty:
        # PROGRESS BAR
        total = len(df)
        resolved = len(df[df['status'].isin(["Resolved", "Closed"])])
        progress = resolved / total
        st.write(f"**Resolution Progress: {resolved}/{total} ({int(progress*100)}%)**")
        st.progress(progress)

        # CASCADING SELECTORS
        excluded = ["defect_id", "description", "comments", "created_at", "updated_at", "defect_title"]
        available_cols = [c for c in df.columns if c not in excluded]
        
        sel_c1, sel_c2 = st.columns(2)
        category = sel_c1.selectbox("Analyze Category", available_cols, key="insight_cat")
        
        with st.spinner("Refining charts..."):
            sub_values = df[category].unique().tolist()
            selected_sub = sel_c2.multiselect(f"Filter {category}", sub_values, default=sub_values, key="insight_sub")
            
            chart_df = df[df[category].isin(selected_sub)]
            
            if not chart_df.empty:
                c1, c2 = st.columns(2)
                with c1:
                    st.plotly_chart(px.pie(chart_df, names=category, hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel), use_container_width=True)
                with c2:
                    bar_data = chart_df[category].value_counts().reset_index()
                    bar_data.columns = [category, 'Count']
                    st.plotly_chart(px.bar(bar_data, x=category, y='Count', color=category, color_discrete_sequence=px.colors.qualitative.Safe), use_container_width=True)
