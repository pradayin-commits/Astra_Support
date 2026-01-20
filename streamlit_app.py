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
st.caption("Create defects at the top. Select a defect below and edit it in a clean form.")


# ======================
# Constants
# ======================
COMPANY_CODES = ["4310", "8410"]
COMPANY_INDEX = {"4310": "1", "8410": "2"}

MODULES = ["PLM", "PP", "FI", "SD", "MM", "QM", "ABAP", "BASIS", "OTHER"]
DEFECT_TYPES = [
    "Functional",
    "Data Migration",
    "Test Data",
    "EDI set up",
    "Configuration",
    "Security/Authorization",
    "Performance",
    "Other",
]
PRIORITIES = ["P1 - Critical", "P2 - High", "P3 - Medium", "P4 - Low"]
STATUSES = ["New", "In Progress", "Blocked", "Resolved", "Closed", "Reopened"]
ENVIRONMENTS = ["P1S", "Q1S", "Q2S", "Q2C"]
OPEN_WITH = ["SDS", "SNP", "Client", "Other"]


# ======================
# DB Engine
# ======================
@st.cache_resource
def get_engine():
    db_url = os.getenv("SUPABASE_DATABASE_URL", "").strip()
    if not db_url:
        raise RuntimeError("SUPABASE_DATABASE_URL is missing (set Codespaces secret and restart)")
    return create_engine(
        db_url,
        pool_pre_ping=True,
        connect_args={"sslmode": "require"},
    )


def today() -> dt.date:
    return dt.date.today()


def compute_age(open_date: Optional[dt.date], resolved_date: Optional[dt.date], status: str) -> Optional[int]:
    if not open_date:
        return None
    end = resolved_date if status in {"Resolved", "Closed"} and resolved_date else today()
    return max(0, (end - open_date).days)


# ======================
# Data access
# ======================
@st.cache_data(show_spinner=False, ttl=2)
def load_defects() -> pd.DataFrame:
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
          updated_at as "Updated At",
          seq_id as "_seq_id"
        from public.defects
        order by created_at desc
    """)
    with get_engine().connect() as conn:
        df = pd.read_sql(q, conn)

    if df.empty:
        return df

    # Ensure date dtype -> python date for age calc
    df["Open Date"] = pd.to_datetime(df["Open Date"]).dt.date
    df["Resolved Date"] = pd.to_datetime(df["Resolved Date"], errors="coerce").dt.date
    df["Age (days)"] = df.apply(lambda r: compute_age(r["Open Date"], r["Resolved Date"], str(r["Status"])), axis=1)
    return df


def generate_defect_id(module: str, company_code: str) -> str:
    """
    Collision-safe: uses DB sequence. Format: <MODULE>-<CompanyIndex>-<SEQ:03+>
    Example: PLM-1-001, PLM-1-002 ... (sequence is global, but still readable)
    """
    mod = (module or "OTHER").strip().upper()
    comp = COMPANY_INDEX.get(company_code, "0")

    with get_engine().begin() as conn:
        seq_val = conn.execute(text("select nextval('public.defect_seq')")).scalar_one()

    # keep last 3 digits for display; still unique because seq_val is stored in table too
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
# Sidebar filters
# ======================
st.sidebar.header("Filters")
company_f = st.sidebar.selectbox("Company Code", ["All"] + COMPANY_CODES)
module_f = st.sidebar.selectbox("Module", ["All"] + MODULES)
status_f = st.sidebar.selectbox("Status", ["All"] + STATUSES)
priority_f = st.sidebar.selectbox("Priority", ["All"] + PRIORITIES)
search = st.sidebar.text_input("Search").lower().strip()


# ======================
# Create defect
# ======================
st.subheader("➕ Create Defect")

with st.form("create_form"):
    c1, c2, c3, c4 = st.columns(4)
    company_code = c1.selectbox("Company Code", COMPANY_CODES)
    open_date = c2.date_input("Open Date", today())
    module = c3.selectbox("Module", MODULES)

    defect_id_preview = f"{module}-{COMPANY_INDEX[company_code]}-###"
    c4.text_input("Defect ID (auto)", defect_id_preview, disabled=True)

    defect_title = st.text_input("Defect Title *")
    defect_type = st.selectbox("Defect Type", DEFECT_TYPES)
    priority = st.selectbox("Priority", PRIORITIES, index=1)
    status = st.selectbox("Status", STATUSES, index=0)

    resolved_date = None
    if status in {"Resolved", "Closed"}:
        resolved_date = st.date_input("Resolved Date", today())

    open_with = st.selectbox("Open with", OPEN_WITH)
    reported_by = st.text_input("Reported By *")
    responsible = st.text_input("Responsible")
    environment = st.selectbox("Environment", ENVIRONMENTS)

    linked_test_id = st.text_input("Linked Test ID")
    description = st.text_area("Description")
    steps = st.text_area("Description / Steps")

    submit = st.form_submit_button("Create")

if submit:
    if not defect_title.strip() or not reported_by.strip():
        st.error("Defect Title and Reported By are required.")
    else:
        real_defect_id = generate_defect_id(module, company_code)
        with st.spinner("Saving defect..."):
            insert_defect(
                {
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
                }
            )
        st.success(f"Defect {real_defect_id} created.")
        st.rerun()


# ======================
# List + Edit
# ======================
st.divider()
st.subheader("📋 Defects")

try:
    df = load_defects()
except Exception as e:
    st.error("Database connection failed. Check SUPABASE_DATABASE_URL secret and restart Codespace.")
    st.exception(e)
    st.stop()

if df.empty:
    st.info("No defects yet.")
else:
    view = df.copy()

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

    # Hide internal seq_id column
    show_cols = [c for c in view.columns if c != "_seq_id"]

    st.dataframe(view[show_cols], width="stretch", hide_index=True)

    st.markdown("### ✏️ Edit Defect")
    selected_id = st.selectbox("Select Defect ID", view["Defect ID"].tolist())

    row = df[df["Defect ID"] == selected_id].iloc[0]

    with st.form("edit_form"):
        company_code_e = st.selectbox("Company Code", COMPANY_CODES, index=COMPANY_CODES.index(row["Company Code"]))
        open_date_e = st.date_input("Open Date", row["Open Date"])
        module_e = st.selectbox("Module", MODULES, index=MODULES.index(row["Module"]))

        defect_title_e = st.text_input("Defect Title *", row["Defect Title"])
        defect_type_e = st.selectbox("Defect Type", DEFECT_TYPES, index=DEFECT_TYPES.index(row["Defect Type"]) if row["Defect Type"] in DEFECT_TYPES else 0)
        priority_e = st.selectbox("Priority", PRIORITIES, index=PRIORITIES.index(row["Priority"]) if row["Priority"] in PRIORITIES else 1)
        status_e = st.selectbox("Status", STATUSES, index=STATUSES.index(row["Status"]) if row["Status"] in STATUSES else 0)

        resolved_date_e = row["Resolved Date"]
        if status_e in {"Resolved", "Closed"}:
            resolved_date_e = st.date_input("Resolved Date", resolved_date_e or today())
        else:
            resolved_date_e = None

        open_with_e = st.selectbox("Open with", OPEN_WITH, index=OPEN_WITH.index(row["Open with"]) if row["Open with"] in OPEN_WITH else 0)
        reported_by_e = st.text_input("Reported By *", row["Reported By"])
        responsible_e = st.text_input("Responsible", row["Responsible"])
        environment_e = st.selectbox("Environment", ENVIRONMENTS, index=ENVIRONMENTS.index(row["Environment"]) if row["Environment"] in ENVIRONMENTS else 0)

        linked_test_id_e = st.text_input("Linked Test ID", row["Linked Test ID"])
        description_e = st.text_area("Description", row["Description"])
        steps_e = st.text_area("Description / Steps", row["Description / Steps"])

        save = st.form_submit_button("Save Changes")

    if save:
        if not defect_title_e.strip() or not reported_by_e.strip():
            st.error("Defect Title and Reported By are required.")
        else:
            with st.spinner("Saving changes..."):
                update_defect(
                    selected_id,
                    {
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
                    },
                )
            st.success("Defect updated.")
            st.rerun()
