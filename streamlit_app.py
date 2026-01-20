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
    
    /* Pull app to the very top */
    .block-container {
        padding-top: 0.5rem !important;
        margin-top: -3rem !important;
    }

    /* KPI Card Styling */
    div[data-testid="stMetric"] {
        background-color: white;
        border: 1px solid #d2d2d7;
        border-radius: 12px;
        padding: 15px !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.01);
    }
    
    /* Tiny Export Button Styling */
    .stDownloadButton button {
        padding: 0.2rem 0.5rem !important;
        font-size: 12px !important;
        height: auto !important;
        min-height: 0px !important;
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
# 3. INTERACTIVE MODALS
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
            load_data.clear()
            st.rerun()

# ==========================================
# 4. MAIN UI
# ==========================================
df = load_data()

# --- HEADER WITH LOGO ---
header_col1, header_col2 = st.columns([1, 10])
with header_col1:
    # Try multiple common logo names just in case
    logo_file = "logo.png" if os.path.exists("logo.png") else None
    if logo_file:
        st.image(logo_file, width=80)
    else:
        st.write("🍏") # Fallback icon if logo file is missing from root
with header_col2:
    st.title(APP_NAME)

# --- KPI BUCKETS ---
if not df.empty:
    k1, k2, k3, k4 = st.columns([1, 1, 1, 1])
    k1.metric("Global Defects", len(df))
    k2.metric("Open Defects", len(df[~df['status'].isin(["Resolved", "Closed"])]))
    k3.metric("Resolved", len(df[df['status'].isin(["Resolved", "Closed"])]))

st.divider()

tab_explore, tab_register, tab_insights = st.tabs(["📂 Explorer", "➕ Register", "📊 Insights"])

with tab_explore:
    # Search Box & Tiny Export Row
    search_col, export_col = st.columns([9, 1])
    with search_col:
        search_query = st.text_input("🔍 Search Defects...", placeholder="Type to filter by ID, Title, or Reporter...")
    with export_col:
        st.write("") # Spacer
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 CSV", data=csv, file_name="astra.csv")

    # Filter data based on search
    if not df.empty:
        if search_query:
            display_df = df[df.astype(str).apply(lambda x: x.str.contains(search_query, case=False)).any(axis=1)]
        else:
            display_df = df

        st.caption("Excel-style: Click headers to sort. Select a row to edit.")
        selection = st.dataframe(display_df, use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row")
        
        rows = selection.get("selection", {}).get("rows", [])
        if rows:
            edit_modal(display_df.iloc[rows[0]])

with tab_register:
    with st.form("reg_form", clear_on_submit=True):
        st.subheader("New Defect Entry")
        c1, c2 = st.columns(2)
        comp = c1.selectbox("Company", ["4310", "8410"])
        mod = c2.selectbox("Module", ["PLM", "PP", "FI", "SD", "MM", "QM", "ABAP"])
        title = st.text_input("Summary *")
        pri = st.selectbox("Priority", ["P1 - Critical", "P2 - High", "P3 - Medium", "P4 - Low"], index=2)
        rep = st.text_input("Reporter *")
        if st.form_submit_button("Commit to Database", type="primary"):
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
        st.subheader("📊 Comparative Analysis")
        all_cols = df.columns.tolist()
        
        # Two Inputs for comparison
        col_input1, col_input2 = st.columns(2)
        choice1 = col_input1.selectbox("Primary View (Pie)", all_cols, index=all_cols.index("priority") if "priority" in all_cols else 0)
        choice2 = col_input2.selectbox("Secondary View (Bar)", all_cols, index=all_cols.index("status") if "status" in all_cols else 0)
        
        c1, c2 = st.columns(2)
        with c1:
            st.write(f"**{choice1.title()} Distribution**")
            fig_pie = px.pie(df, names=choice1, hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig_pie, use_container_width=True)
        with c2:
            st.write(f"**{choice2.title()} Volume**")
            # Grouping to ensure bar chart is clean
            bar_data = df[choice2].value_counts().reset_index()
            bar_data.columns = [choice2, 'Count']
            fig_bar = px.bar(bar_data, x=choice2, y='Count', color=choice2, color_discrete_sequence=px.colors.qualitative.Safe)
            st.plotly_chart(fig_bar, use_container_width=True)
