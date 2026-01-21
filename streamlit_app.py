import os
import datetime as dt
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text
import plotly.express as px

# ==========================================
# 1. BRANDING & VIBRANT DESIGN
# ==========================================
APP_NAME = "Astra Defect Tracker"
st.set_page_config(page_title=APP_NAME, page_icon="🛡️", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #f0f2f6; }
    
    /* Vibrant KPI Cards */
    .metric-card {
        border-radius: 12px; padding: 20px; color: white; margin-bottom: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.15);
    }
    .global-bucket { background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%); }
    .open-bucket { background: linear-gradient(135deg, #ea580c 0%, #fb923c 100%); }
    .resolved-bucket { background: linear-gradient(135deg, #166534 0%, #22c55e 100%); }
    
    .metric-card h3 { margin: 0; font-size: 14px; opacity: 0.8; text-transform: uppercase; }
    .metric-card h1 { margin: 5px 0 0 0; font-size: 32px; font-weight: 800; }

    /* Dark Green Left-Aligned Button Style */
    div[data-testid="stButton"] > button {
        background-color: #064e3b !important;
        color: #ffffff !important;
        border-radius: 6px !important;
        border: none !important;
        padding: 0.5rem 2rem !important;
        font-weight: 600 !important;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. DATABASE CONFIGURATION
# ==========================================
MODULES = ["PLM", "PP", "FI", "SD", "MM", "QM", "ABAP", "BASIS", "OTHER"]
PRIORITIES = ["P1 - Critical", "P2 - High", "P3 - Medium", "P4 - Low"]
STATUSES = ["New", "In Progress", "Blocked", "Resolved", "Closed", "Reopened"]

@st.cache_resource
def get_engine():
    db_url = st.secrets.get("SUPABASE_DATABASE_URL") or os.getenv("SUPABASE_DATABASE_URL")
    if not db_url:
        st.error("Missing Database Connection String.")
        st.stop()
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
    return create_engine(db_url, pool_pre_ping=True)

def load_data():
    try:
        with get_engine().connect() as conn:
            return pd.read_sql(text("SELECT * FROM public.defects ORDER BY created_at DESC"), conn)
    except Exception:
        return pd.DataFrame()

# ==========================================
# 3. MODALS (CREATE & EDIT DIALOGS)
# ==========================================

@st.dialog("➕ Register New Defect")
def create_defect_dialog():
    with st.form("create_form", clear_on_submit=True):
        st.markdown("### Defect Details")
        title = st.text_input("Summary *")
        col1, col2 = st.columns(2)
        mod = col1.selectbox("Module", MODULES)
        pri = col2.selectbox("Priority", PRIORITIES)
        rep = st.text_input("Reported By *")
        desc = st.text_area("Detailed Description")
        
        if st.form_submit_button("Submit to Astra", use_container_width=True):
            if not title or not rep:
                st.error("Fields marked * are mandatory.")
            else:
                new_rec = {"t": title, "m": mod, "p": pri, "r": rep, "d": desc, "s": "New", "now": dt.datetime.now()}
                with get_engine().begin() as conn:
                    conn.execute(text("""
                        INSERT INTO public.defects (defect_title, module, priority, reported_by, description, status, created_at) 
                        VALUES (:t, :m, :p, :r, :d, :s, :now)
                    """), new_rec)
                st.success("Synchronized!")
                st.rerun()

@st.dialog("✏️ Edit Defect Record")
def edit_defect_dialog(record):
    with st.form("edit_form"):
        st.markdown(f"**Modifying Record ID: {record['id']}**")
        new_title = st.text_input("Summary", value=record['defect_title'])
        c1, c2 = st.columns(2)
        new_status = c1.selectbox("Status", STATUSES, index=STATUSES.index(record['status']))
        new_pri = c2.selectbox("Priority", PRIORITIES, index=PRIORITIES.index(record['priority']))
        new_desc = st.text_area("Description", value=record['description'])
        
        st.write("")
        col_save, col_cancel = st.columns(2)
        
        if col_save.form_submit_button("💾 Save Changes", use_container_width=True):
            with get_engine().begin() as conn:
                conn.execute(text("""
                    UPDATE public.defects 
                    SET defect_title=:t, status=:s, priority=:p, description=:d 
                    WHERE id=:id
                """), {"t": new_title, "s": new_status, "p": new_pri, "d": new_desc, "id": record['id']})
            st.rerun()
            
        if col_cancel.form_submit_button("✖️ Cancel", use_container_width=True):
            st.rerun()

# ==========================================
# 4. MAIN INTERFACE EXECUTION
# ==========================================
df = load_data()

# --- HEADER & KPI SECTION ---
st.title(f"🛡️ {APP_NAME}")

if not df.empty:
    k1, k2, k3 = st.columns(3)
    k1.markdown(f'<div class="metric-card global-bucket"><h3>Global Defects</h3><h1>{len(df)}</h1></div>', unsafe_allow_html=True)
    k2.markdown(f'<div class="metric-card open-bucket"><h3>Active Items</h3><h1>{len(df[~df["status"].isin(["Resolved", "Closed"])])}</h1></div>', unsafe_allow_html=True)
    k3.markdown(f'<div class="metric-card resolved-bucket"><h3>Resolved Total</h3><h1>{len(df[df["status"].isin(["Resolved", "Closed"])])}</h1></div>', unsafe_allow_html=True)

# --- CREATE BUTTON ROW ---
btn_col, _ = st.columns([0.2, 0.8])
with btn_col:
    if st.button("➕ CREATE NEW DEFECT"):
        create_defect_dialog()

st.write("")

# --- MAIN TABS ---
tab_insights, tab_explorer = st.tabs(["📊 Performance Insights", "📂 Workspace Explorer"])

with tab_insights:
    if not df.empty:
        st.subheader("Multi-Tier Analytical Drill Down")
        d1, d2, d3 = st.columns(3)
        
        # Tier 1: Primary Category
        cat_1 = d1.selectbox("1. Filter Category", ["module", "priority", "status", "reported_by"])
        
        # Tier 2: Specific Value (Dynamic based on Category)
        unique_vals = sorted(df[cat_1].unique().tolist())
        val_1 = d2.selectbox(f"2. Select {cat_1.title()} Value", ["All Data"] + unique_vals)
        
        # Tier 3: Secondary Pivot (The chart dimension)
        cat_2 = d3.selectbox("3. Pivot Analytics By", [c for c in ["status", "priority", "module"] if c != cat_1])
        
        # Filter Logic for Charts
        chart_df = df if val_1 == "All Data" else df[df[cat_1] == val_1]
        
        # --- CHARTS ---
        g1, g2 = st.columns(2)
        with g1:
            fig_pie = px.pie(chart_df, names=cat_2, hole=0.4, 
                             title=f"Distribution of {cat_2.title()} ({val_1})",
                             color_discrete_sequence=px.colors.qualitative.Dark24)
            st.plotly_chart(fig_pie, use_container_width=True)
        with g2:
            bar_data = chart_df.groupby([cat_2]).size().reset_index(name='Count')
            fig_bar = px.bar(bar_data, x=cat_2, y='Count', 
                             title=f"Volume Count by {cat_2.title()}",
                             color=cat_2, color_discrete_sequence=px.colors.qualitative.Bold)
            st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.info("Synchronizing with Supabase... Please ensure data exists in the 'public.defects' table.")

with tab_explorer:
    st.subheader("Defect Registry")
    st.caption("Double-click or click a row to open the Edit Pop-up Dialog.")
    
    # Global Search Feature
    search = st.text_input("🔍 Quick Search", placeholder="Search Titles, Reporters, or IDs...")
    disp_df = df
    if search:
        disp_df = df[df.apply(lambda r: search.lower() in r.astype(str).str.lower().values, axis=1)]

    # Main Workspace Table with Selection
    event = st.dataframe(
        disp_df, 
        use_container_width=True, 
        hide_index=True, 
        on_select="rerun", 
        selection_mode="single"
    )

    # POP-UP TRIGGER: Check for selection event
    if len(event.selection.rows) > 0:
        selected_index = event.selection.rows[0]
        selected_record = disp_df.iloc[selected_index]
        edit_defect_dialog(selected_record)
