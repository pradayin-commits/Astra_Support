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
    
    /* Remove top white space and pull app up */
    .block-container {
        padding-top: 0.5rem !important;
        margin-top: -3.5rem !important;
    }

    /* KPI Buckets Styling */
    div[data-testid="stMetric"] {
        background-color: white;
        border: 1px solid #d2d2d7;
        border-radius: 12px;
        padding: 15px !important;
    }

    /* Small Export Button */
    .stDownloadButton button {
        padding: 0.1rem 0.5rem !important;
        font-size: 12px !important;
        height: 28px !important;
        border-radius: 8px !important;
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

def generate_id(module, code):
    try:
        with get_engine().begin() as conn:
            val = conn.execute(text("select nextval('public.defect_seq')")).scalar_one()
        return f"{module.upper()}-{code}-{(int(val)):03d}"
    except:
        return f"{module.upper()}-{code}-{dt.datetime.now().strftime('%S%f')[:3]}"

# ==========================================
# 3. EDIT MODAL
# ==========================================
@st.dialog("✏️ Edit Defect")
def edit_modal(row):
    with st.form("edit_form", border=False):
        c1, c2 = st.columns(2)
        new_title = c1.text_input("Title", value=row["defect_title"])
        status_opts = ["New", "In Progress", "Blocked", "Resolved", "Closed"]
        new_status = c2.selectbox("Status", status_opts, index=status_opts.index(row["status"]) if row["status"] in status_opts else 0)
        
        pri_opts = ["P1 - Critical", "P2 - High", "P3 - Medium", "P4 - Low"]
        new_pri = c1.selectbox("Priority", pri_opts, index=pri_opts.index(row["priority"]) if row["priority"] in pri_opts else 2)
        new_resp = c2.text_input("Responsible", value=row.get("responsible", ""))
        
        if st.form_submit_button("Update Astra", type="primary", use_container_width=True):
            with get_engine().begin() as conn:
                conn.execute(text("""
                    UPDATE public.defects SET defect_title=:t, status=:s, priority=:p, responsible=:r, updated_at=NOW() 
                    WHERE defect_id=:id
                """), {"t": new_title, "s": new_status, "p": new_pri, "r": new_resp, "id": row["defect_id"]})
            st.rerun()

# ==========================================
# 4. MAIN UI
# ==========================================
df = load_data()

# --- HEADER (Logo + Text) ---
h_col1, h_col2 = st.columns([0.8, 10])
with h_col1:
    if os.path.exists("logo.png"):
        st.image("logo.png", width=80)
    else:
        st.write("🍏")
with h_col2:
    st.title(APP_NAME)

# --- KPI BUCKETS ---
if not df.empty:
    k1, k2, k3, k_space = st.columns([1, 1, 1, 1])
    k1.metric("Global Defects", len(df))
    k2.metric("Open Defects", len(df[~df['status'].isin(["Resolved", "Closed"])]))
    k3.metric("Resolved", len(df[df['status'].isin(["Resolved", "Closed"])]))

st.divider()

tab_explore, tab_register, tab_insights = st.tabs(["📂 Explorer", "➕ Register", "📊 Insights"])

with tab_explore:
    search_col, export_col = st.columns([10, 1])
    with search_col:
        search_query = st.text_input("🔍 Search Defects...", placeholder="Search IDs, titles, or modules...")
    with export_col:
        st.write(" ") # Padding
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 CSV", data=csv, file_name="astra.csv")

    if not df.empty:
        # Search Filtering
        display_df = df[df.astype(str).apply(lambda x: x.str.contains(search_query, case=False)).any(axis=1)] if search_query else df
        
        selection = st.dataframe(display_df, use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row")
        
        rows = selection.get("selection", {}).get("rows", [])
        if rows:
            edit_modal(display_df.iloc[rows[0]])

with tab_register:
    with st.form("reg_form", clear_on_submit=True):
        st.subheader("Register New Defect")
        c1, c2 = st.columns(2)
        comp = c1.selectbox("Company", ["4310", "8410"])
        mod = c2.selectbox("Module", ["PLM", "PP", "FI", "SD", "MM", "QM", "ABAP"])
        title = st.text_input("Summary *")
        pri = st.selectbox("Priority", ["P1 - Critical", "P2 - High", "P3 - Medium", "P4 - Low"], index=2)
        rep = st.text_input("Reporter *")
        if st.form_submit_button("Submit", type="primary"):
            if title and rep:
                new_id = generate_id(mod, comp)
                with get_engine().begin() as conn:
                    conn.execute(text("""
                        INSERT INTO public.defects (defect_id, company_code, module, defect_title, priority, status, reported_by, open_date)
                        VALUES (:id, :c, :m, :t, :p, 'New', :r, :d)
                    """), {"id": new_id, "c": comp, "m": mod, "t": title, "p": pri, "r": rep, "d": dt.date.today()})
                st.rerun()

with tab_insights:
    if not df.empty:
        st.subheader("📊 Performance Analysis")
        
        # 1. Filter out excluded columns for the FIRST dropdown
        excluded = ["defect_id", "description", "comments", "created_at", "updated_at", "defect_title"]
        available_cols = [c for c in df.columns if c not in excluded]
        
        # 2. Cascading Selectors
        sel_c1, sel_c2 = st.columns(2)
        category = sel_c1.selectbox("Select Category (X-Axis)", available_cols, index=available_cols.index("module") if "module" in available_cols else 0)
        
        # 3. Dynamic Second Dropdown (Sub-values)
        sub_values = df[category].unique().tolist()
        selected_sub = sel_c2.multiselect(f"Filter specific {category} values", sub_values, default=sub_values)
        
        # Filter data based on second dropdown
        chart_df = df[df[category].isin(selected_sub)]
        
        # 4. Charts
        chart_c1, chart_c2 = st.columns(2)
        if not chart_df.empty:
            with chart_c1:
                st.write(f"**{category.title()} Distribution**")
                fig_pie = px.pie(chart_df, names=category, hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
                st.plotly_chart(fig_pie, use_container_width=True)
            with chart_c2:
                st.write(f"**Count by {category.title()}**")
                bar_data = chart_df[category].value_counts().reset_index()
                bar_data.columns = [category, 'Count']
                fig_bar = px.bar(bar_data, x=category, y='Count', color=category, color_discrete_sequence=px.colors.qualitative.Safe)
                st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.warning("No data matches the selected filters.")
