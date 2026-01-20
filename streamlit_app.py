import os
import datetime as dt
from typing import Optional

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

# ======================
# App config
# ======================
APP_NAME = "Astra"
st.set_page_config(page_title=APP_NAME, page_icon="🎫", layout="wide")

st.title("🎫 Astra")
st.caption("Create a defect at the top. Select a defect below and edit it using a clean form.")

# ======================
# Constants
# ======================
COMPANY_CODES = ["4310", "8410"]
COMPANY_INDEX = {"4310": "1", "8410": "2"}

MODULES = ["PLM", "PP", "FI", "SD", "MM", "QM", "ABAP", "BASIS", "OTHER"]
DEFECT_TYPES = [
    "Functional", "Data Migration", "Test Data", "EDI set up",
    "Configuration", "Security/Authorization", "Performance", "Other",
]
PRIORITIES = ["P1 - Critical", "P2 - High", "P3 - Medium", "P4 - Low"]
STATUSES = ["New", "In Progress", "Blocked", "Resolved", "Closed", "Reopened"]
ENVIRONMENTS = ["P1S", "Q1S", "Q2S", "Q2C"]
OPEN_WITH = ["SDS", "SNP", "Client", "Other"]

# ======================
# Helpers
# ======================
def today() -> dt.date:
    return dt.date.today()

def compute_age(open_date: Optional[dt.date], resolved_date: Optional[dt.date], status: str) -> Optional[int]:
    if not open_date:
        return None
    end = resolved_date if status in {"Resolved", "Closed"} and resolved_date else today()
    return max(0, (end - open_date).days)

# ======================
# DB Engine
# ======================
@st.cache_resource
def get_engine():
    # Looks in Streamlit Secrets first, then Environment Variables
    db_url = st.secrets.get("SUPABASE_DATABASE_URL") or os.getenv("SUPABASE_DATABASE_URL")
    
    if not db_url:
        st.error("❌ SUPABASE_DATABASE_URL is missing.")
        st.stop()

    # URL Cleaning & Driver Injection
    db_url = db_url.strip()
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif db_url.startswith("postgresql://") and "+psycopg2" not in db_url:
        db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)

    return create_engine(
        db_url,
        pool_pre_ping=True,
        connect_args={"sslmode": "require"},
    )

@st.cache_data(show_spinner=False, ttl=2)
def load_defects() -> pd.DataFrame:
    # Query updated to exclude seq_id to prevent column errors
    q = text("""
        select 
          company_code as "Company Code",
          open_date as "Open Date",
          module as "Module",
          defect_id as "Defect ID",
          defect_title as "Defect Title",
          coalesce(defect_type,'') as "Defect Type",
          coalesce(priority,'') as "Priority",
          status as "Status",
          resolved_date as "Resolved Date",
          coalesce(open_with,'') as "Open with",
          reported_by as "Reported By",
          coalesce(responsible,'') as "Responsible",
          coalesce(environment,'') as "Environment",
          coalesce(linked_test_id,'') as "Linked Test ID",
          coalesce(description,'') as "Description",
          coalesce(steps,'') as "Description / Steps",
          created_at as "Created At",
          updated_at as "Updated At"
        from public.defects
        order by created_at desc
    """)
    try:
        with get_engine().connect() as conn:
            df = pd.read_sql(q, conn)
    except Exception as e:
        st.error(f"Failed to query database: {e}")
        return pd.DataFrame()

    if df.empty:
        return df

    df["Open Date"] = pd.to_datetime(df["Open Date"]).dt.date
    df["Resolved Date"] = pd.to_datetime(df["Resolved Date"], errors="coerce").dt.date
    df["Age (days)"] = df.apply(
        lambda r: compute_age(r["Open Date"], r["Resolved Date"], str(r["Status"])),
        axis=1,
    )
    return df

def generate_defect_id(module: str, company_code: str) -> str:
    mod = (module or "OTHER").strip().upper()
    comp = COMPANY_INDEX.get(company_code, "0")
    
    try:
        with get_engine().begin() as conn:
            seq_val = conn.execute(text("select nextval('public.defect_seq')")).scalar_one()
    except Exception:
        # Fail-safe: if sequence isn't in DB, use a timestamp-based fallback or default
        st.warning("Sequence 'defect_seq' not found in Supabase. Using fallback ID.")
        seq_val = dt.datetime.now().strftime("%S%f")[:3] 

    return f"{mod}-{comp}-{int(seq_val):03d}"

def insert_defect(payload: dict) -> None:
    q = text("""
        insert into public.defects (
          defect_id, company_code, open_date, module,
          defect_title, defect_type, priority, status,
          resolved_date, open_with, reported_by, responsible,
          environment, linked_test_id, description, steps
        ) values (
          :defect_id, :company_code, :open_date, :module,
          :defect_title, :defect_type, :priority, :status,
          :resolved_date, :open_with, :reported_by, :responsible,
          :environment, :linked_test_id, :description, :steps
        )
    """)
    with get_engine().begin() as conn:
        conn.execute(q, payload)
    load_defects.clear()

def update_defect(defect_id: str, payload: dict) -> None:
    payload = dict(payload)
    payload["defect_id"] = defect_id
    q = text("""
        update public.defects set
          company_code=:company_code,
          open_date=:open_date,
          module=:module,
          defect_title=:defect_title,
          defect_type=:defect_type,
          priority=:priority,
          status=:status,
          resolved_date=:resolved_date,
          open_with=:open_with,
          reported_by=:reported_by,
          responsible=:responsible,
          environment=:environment,
          linked_test_id=:linked_test_id,
          description=:description,
          steps=:steps
        where defect_id=:defect_id
    """)
    with get_engine().begin() as conn:
        conn.execute(q, payload)
    load_defects.clear()

# ======================
# Sidebar Filters
# ======================
st.sidebar.header("Filters")
company_f = st.sidebar.selectbox("Company Code", ["All"] + COMPANY_CODES)
module_f = st.sidebar.selectbox("Module", ["All"] + MODULES)
status_f = st.sidebar.selectbox("Status", ["All"] + STATUSES)
priority_f = st.sidebar.selectbox("Priority", ["All"] + PRIORITIES)
search = st.sidebar.text_input("Search (ID / Title / Responsible / Reported By)").lower().strip()

# ======================
# Create Defect
# ======================
st.subheader("➕ Create Defect")

with st.form("create_form", clear_on_submit=True):
    c1, c2, c3, c4 = st.columns(4)
    company_code = c1.selectbox("Company Code", COMPANY_CODES)
    open_date = c2.date_input("Open Date", today())
    module = c3.selectbox("Module", MODULES)
    defect_id_preview = f"{module}-{COMPANY_INDEX[company_code]}-###"
    c4.text_input("Defect ID (auto)", defect_id_preview, disabled=True)

    defect_title = st.text_input("Defect Title *")

    c5, c6, c7, c8 = st.columns(4)
    defect_type = c5.selectbox("Defect Type", DEFECT_TYPES, index=0)
    priority = c6.selectbox("Priority", PRIORITIES, index=1)
    status = c7.selectbox("Status", STATUSES, index=0)
    environment = c8.selectbox("Environment", ENVIRONMENTS, index=0)

    c9, c10, c11 = st.columns(3)
    open_with = c9.selectbox("Open with", OPEN_WITH, index=0)
    reported_by = c10.text_input("Reported By *")
    responsible = c11.text_input("Responsible")

    resolved_date = None
    if status in {"Resolved", "Closed"}:
        resolved_date = st.date_input("Resolved Date", today())

    linked_test_id = st.text_input("Linked Test ID")
    description = st.text_area("Description")
    steps = st.text_area("Description / Steps")

    submit = st.form_submit_button("Create")

if submit:
    if not defect_title.strip():
        st.error("Defect Title is required.")
    elif not reported_by.strip():
        st.error("Reported By is required.")
    else:
        real_defect_id = generate_defect_id(module, company_code)
        with st.spinner("Saving defect..."):
            insert_defect({
                "defect_id": real_defect_id,
                "company_code": company_code,
                "open_date": open_date,
                "module": module,
                "defect_title": defect_title.strip(),
                "defect_type": defect_type,
                "priority": priority,
                "status": status,
                "resolved_date": resolved_date,
                "open_with": open_with,
                "reported_by": reported_by.strip(),
                "responsible": responsible.strip(),
                "environment": environment,
                "linked_test_id": linked_test_id.strip(),
                "description": description.strip(),
                "steps": steps.strip(),
            })
        st.success(f"Defect created: {real_defect_id}")
        st.rerun()

# ======================
# List + Edit
# ======================
st.divider()
st.subheader("📋 Defects")

df = load_defects()

if df.empty:
    st.info("No defects found in the database.")
    st.stop()

view = df.copy()

# Filter logic
if company_f != "All":
    view = view[view["Company Code"] == company_f]
if module_f != "All":
    view = view[view["Module"] == module_f]
if status_f != "All":
    view = view[view["Status"] == status_f]
if priority_f != "All":
    view = view[view["Priority"] == priority_f]
if search:
    view = view[
        view[["Defect ID", "Defect Title", "Reported By", "Responsible"]]
        .astype(str)
        .agg(" ".join, axis=1)
        .str.lower()
        .str.contains(search, na=False)
    ]

show_cols = [
    "Company Code", "Open Date", "Module", "Defect ID", 
    "Defect Title", "Defect Type", "Priority", "Status", 
    "Resolved Date", "Open with", "Reported By", "Responsible", "Age (days)"
]

st.dataframe(view[show_cols], width="stretch", hide_index=True)

st.markdown("### ✏️ Edit Defect")
if not view.empty:
    selected_id = st.selectbox("Select Defect ID to Edit", view["Defect ID"].tolist())
    row = df[df["Defect ID"] == selected_id].iloc[0]

    with st.form("edit_form"):
        c1, c2, c3 = st.columns(3)
        company_code_e = c1.selectbox("Company Code", COMPANY_CODES, index=COMPANY_CODES.index(row["Company Code"]))
        open_date_e = c2.date_input("Open Date", row["Open Date"])
        module_e = c3.selectbox("Module", MODULES, index=MODULES.index(row["Module"]))

        defect_title_e = st.text_input("Defect Title *", row["Defect Title"])

        c4, c5, c6, c7 = st.columns(4)
        defect_type_e = c4.selectbox("Defect Type", DEFECT_TYPES, 
                                     index=DEFECT_TYPES.index(row["Defect Type"]) if row["Defect Type"] in DEFECT_TYPES else 0)
        priority_e = c5.selectbox("Priority", PRIORITIES, 
                                   index=PRIORITIES.index(row["Priority"]) if row["Priority"] in PRIORITIES else 1)
        status_e = c6.selectbox("Status", STATUSES, 
                                 index=STATUSES.index(row["Status"]) if row["Status"] in STATUSES else 0)
        environment_e = c7.selectbox("Environment", ENVIRONMENTS, 
                                      index=ENVIRONMENTS.index(row["Environment"]) if row["Environment"] in ENVIRONMENTS else 0)

        c8, c9, c10 = st.columns(3)
        open_with_e = c8.selectbox("Open with", OPEN_WITH, 
                                    index=OPEN_WITH.index(row["Open with"]) if row["Open with"] in OPEN_WITH else 0)
        reported_by_e = c9.text_input("Reported By *", row["Reported By"])
        responsible_e = c10.text_input("Responsible", row["Responsible"])

        resolved_date_e = row["Resolved Date"]
        if status_e in {"Resolved", "Closed"}:
            resolved_date_e = st.date_input("Resolved Date", resolved_date_e or today())
        else:
            resolved_date_e = None

        linked_test_id_e = st.text_input("Linked Test ID", row["Linked Test ID"])
        description_e = st.text_area("Description", row["Description"])
        steps_e = st.text_area("Description / Steps", row["Description / Steps"])

        save = st.form_submit_button("Save Changes")

    if save:
        if not defect_title_e.strip():
            st.error("Defect Title is required.")
        elif not reported_by_e.strip():
            st.error("Reported By is required.")
        else:
            with st.spinner("Saving changes..."):
                update_defect(selected_id, {
                    "company_code": company_code_e,
                    "open_date": open_date_e,
                    "module": module_e,
                    "defect_title": defect_title_e.strip(),
                    "defect_type": defect_type_e,
                    "priority": priority_e,
                    "status": status_e,
                    "resolved_date": resolved_date_e,
                    "open_with": open_with_e,
                    "reported_by": reported_by_e.strip(),
                    "responsible": responsible_e.strip(),
                    "environment": environment_e,
                    "linked_test_id": linked_test_id_e.strip(),
                    "description": description_e.strip(),
                    "steps": steps_e.strip(),
                })
            st.success("Defect updated.")
            st.rerun()
