# streamlit_app.py
# A Streamlit defect tracker that mirrors your sheet — customized per your pointers.
# Storage: SQLite (defects.db) in the same folder as this app.

import sqlite3
import datetime as dt
from typing import Optional, Dict, Any, List

import pandas as pd
import streamlit as st
import altair as alt


# =========================
# App config + Branding
# =========================
APP_NAME = "Asterisk Defector Hacker"
st.set_page_config(page_title=APP_NAME, page_icon="🎫", layout="wide")

st.title(f"🎫 {APP_NAME}")
st.caption("Create defects at the top. Edit existing defects in the table below (Excel-like).")


# =========================
# Constants (your rules)
# =========================
DB_PATH = "defects.db"
TABLE_NAME = "defects"

COMPANY_CODES = ["4310", "8410"]  # Only these two (your requirement)

# You said "Model is fantastic" — I’m keeping Module options editable here.
MODULES = ["PLM", "PP", "FI", "SD", "MM", "QM", "ABAP", "BASIS", "OTHER"]

DEFECT_TYPES = ["Functional", "Data Migration", "Test Data", "EDI set up", "Configuration", "Security/Authorization", "Performance", "Other"]
PRIORITIES = ["P1 - Critical", "P2 - High", "P3 - Medium", "P4 - Low"]

# You want initial status = New, and later you can move it along.
STATUSES = ["New", "In Progress", "Blocked", "Resolved", "Closed", "Reopened"]

# You said to keep only these environments (some text was a bit mixed),
# so I’m including the 3 common ones plus Q2C that you mentioned.
ENVIRONMENTS = ["P1S", "Q1S", "Q2S", "Q2C"]

OPEN_WITH = ["SDS", "SNP", "Client", "Other"]


# =========================
# Date helpers
# =========================
def today_date() -> dt.date:
    return dt.date.today()


def parse_any_date(x) -> Optional[dt.date]:
    if x is None:
        return None
    if isinstance(x, dt.date) and not isinstance(x, dt.datetime):
        return x
    if isinstance(x, dt.datetime):
        return x.date()
    s = str(x).strip()
    if not s or s.lower() in {"nan", "none", "null"}:
        return None
    try:
        d = pd.to_datetime(s, dayfirst=True, errors="raise")
        return d.date()
    except Exception:
        return None


def date_to_str(d: Optional[dt.date]) -> Optional[str]:
    return d.isoformat() if isinstance(d, dt.date) else None


def compute_age_days(open_date: Optional[dt.date], resolved_date: Optional[dt.date], status: str) -> Optional[int]:
    if not open_date:
        return None
    end = resolved_date if (status in {"Resolved", "Closed"} and resolved_date) else today_date()
    try:
        return max(0, (end - open_date).days)
    except Exception:
        return None


# =========================
# SQLite helpers + migration
# =========================
def get_conn() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db_and_migrate() -> None:
    """
    Creates table if needed and migrates older versions by adding missing columns.
    """
    desired_cols = {
        "defect_id": "TEXT PRIMARY KEY",
        "company_code": "TEXT",
        "open_date": "TEXT",
        "module": "TEXT",
        "defect_title": "TEXT",
        "defect_type": "TEXT",
        "priority": "TEXT",
        "status": "TEXT",
        "resolved_date": "TEXT",
        "open_with": "TEXT",
        "reported_by": "TEXT",
        "responsible": "TEXT",
        "environment": "TEXT",
        "linked_test_id": "TEXT",
        "description": "TEXT",
        "description_steps": "TEXT",
        # Audit / ownership (your key requirement)
        "created_by": "TEXT",
        "created_at": "TEXT",
        "last_updated_by": "TEXT",
        "last_updated_at": "TEXT",
    }

    with get_conn() as conn:
        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                defect_id TEXT PRIMARY KEY,
                company_code TEXT,
                open_date TEXT,
                module TEXT,
                defect_title TEXT,
                defect_type TEXT,
                priority TEXT,
                status TEXT,
                resolved_date TEXT,
                open_with TEXT,
                reported_by TEXT,
                responsible TEXT,
                environment TEXT,
                linked_test_id TEXT,
                description TEXT,
                description_steps TEXT,
                created_by TEXT,
                created_at TEXT,
                last_updated_by TEXT,
                last_updated_at TEXT
            )
            """
        )

        # Migration: add missing columns if table already exists in older format
        existing = conn.execute(f"PRAGMA table_info({TABLE_NAME})").fetchall()
        existing_names = {row[1] for row in existing}

        for col_name, col_type in desired_cols.items():
            if col_name not in existing_names:
                conn.execute(f"ALTER TABLE {TABLE_NAME} ADD COLUMN {col_name} {col_type}")

        conn.commit()


def load_defects_df() -> pd.DataFrame:
    init_db_and_migrate()
    with get_conn() as conn:
        df = pd.read_sql_query(f"SELECT * FROM {TABLE_NAME}", conn)

    # Empty -> return sheet-like frame
    if df.empty:
        return pd.DataFrame(
            columns=[
                "Company Code",
                "Open Date",
                "Module",
                "Defect ID",
                "Defect Title",
                "Defect Type",
                "Priority",
                "Status",
                "Resolved Date",
                "Open with",
                "Reported By",
                "Responsible",
                "Environment",
                "Linked Test ID",
                "Description",
                "Description / Steps",
                "Age (days)",
                "Created By",
                "Created At",
                "Last Updated By",
                "Last Updated At",
            ]
        )

    # DB -> sheet-like
    out = pd.DataFrame(
        {
            "Company Code": df.get("company_code", "").fillna("").astype(str),
            "Open Date": df.get("open_date", "").apply(parse_any_date),
            "Module": df.get("module", "").fillna("").astype(str),
            "Defect ID": df.get("defect_id", "").fillna("").astype(str),
            "Defect Title": df.get("defect_title", "").fillna("").astype(str),
            "Defect Type": df.get("defect_type", "").fillna("").astype(str),
            "Priority": df.get("priority", "").fillna("").astype(str),
            "Status": df.get("status", "").fillna("").astype(str),
            "Resolved Date": df.get("resolved_date", "").apply(parse_any_date),
            "Open with": df.get("open_with", "").fillna("").astype(str),
            "Reported By": df.get("reported_by", "").fillna("").astype(str),
            "Responsible": df.get("responsible", "").fillna("").astype(str),
            "Environment": df.get("environment", "").fillna("").astype(str),
            "Linked Test ID": df.get("linked_test_id", "").fillna("").astype(str),
            "Description": df.get("description", "").fillna("").astype(str),
            "Description / Steps": df.get("description_steps", "").fillna("").astype(str),
            "Created By": df.get("created_by", "").fillna("").astype(str),
            "Created At": df.get("created_at", "").fillna("").astype(str),
            "Last Updated By": df.get("last_updated_by", "").fillna("").astype(str),
            "Last Updated At": df.get("last_updated_at", "").fillna("").astype(str),
        }
    )

    out["Age (days)"] = out.apply(
        lambda r: compute_age_days(r["Open Date"], r["Resolved Date"], str(r["Status"])),
        axis=1,
    )

    # Order like a tracker sheet
    out = out[
        [
            "Company Code",
            "Open Date",
            "Module",
            "Defect ID",
            "Defect Title",
            "Defect Type",
            "Priority",
            "Status",
            "Resolved Date",
            "Open with",
            "Reported By",
            "Responsible",
            "Environment",
            "Linked Test ID",
            "Description",
            "Description / Steps",
            "Age (days)",
            "Created By",
            "Created At",
            "Last Updated By",
            "Last Updated At",
        ]
    ]
    return out


def upsert_defect(row: Dict[str, Any], updated_by: str, is_create: bool) -> None:
    """
    Save a defect. If creating, it sets created_* fields.
    If editing, it updates last_updated_* fields.
    """
    init_db_and_migrate()
    now = dt.datetime.now().isoformat(timespec="seconds")

    defect_id = str(row.get("Defect ID", "")).strip()
    if not defect_id:
        raise ValueError("Defect ID is required (auto-generated, but must exist).")

    open_date = parse_any_date(row.get("Open Date"))
    resolved_date = parse_any_date(row.get("Resolved Date"))

    payload = {
        "defect_id": defect_id,
        "company_code": str(row.get("Company Code", "")).strip(),
        "open_date": date_to_str(open_date),
        "module": str(row.get("Module", "")).strip(),
        "defect_title": str(row.get("Defect Title", "")).strip(),
        "defect_type": str(row.get("Defect Type", "")).strip(),
        "priority": str(row.get("Priority", "")).strip(),
        "status": str(row.get("Status", "")).strip(),
        "resolved_date": date_to_str(resolved_date),
        "open_with": str(row.get("Open with", "")).strip(),
        "reported_by": str(row.get("Reported By", "")).strip(),
        "responsible": str(row.get("Responsible", "")).strip(),
        "environment": str(row.get("Environment", "")).strip(),
        "linked_test_id": str(row.get("Linked Test ID", "")).strip(),
        "description": str(row.get("Description", "")).strip(),
        "description_steps": str(row.get("Description / Steps", "")).strip(),
        "created_by": str(row.get("Created By", "")).strip(),
        "created_at": str(row.get("Created At", "")).strip(),
        "last_updated_by": updated_by.strip(),
        "last_updated_at": now,
    }

    if is_create:
        payload["created_by"] = updated_by.strip()
        payload["created_at"] = now

    with get_conn() as conn:
        conn.execute(
            f"""
            INSERT INTO {TABLE_NAME} (
                defect_id, company_code, open_date, module, defect_title,
                defect_type, priority, status, resolved_date, open_with,
                reported_by, responsible, environment, linked_test_id,
                description, description_steps,
                created_by, created_at, last_updated_by, last_updated_at
            )
            VALUES (
                :defect_id, :company_code, :open_date, :module, :defect_title,
                :defect_type, :priority, :status, :resolved_date, :open_with,
                :reported_by, :responsible, :environment, :linked_test_id,
                :description, :description_steps,
                :created_by, :created_at, :last_updated_by, :last_updated_at
            )
            ON CONFLICT(defect_id) DO UPDATE SET
                company_code=excluded.company_code,
                open_date=excluded.open_date,
                module=excluded.module,
                defect_title=excluded.defect_title,
                defect_type=excluded.defect_type,
                priority=excluded.priority,
                status=excluded.status,
                resolved_date=excluded.resolved_date,
                open_with=excluded.open_with,
                reported_by=excluded.reported_by,
                responsible=excluded.responsible,
                environment=excluded.environment,
                linked_test_id=excluded.linked_test_id,
                description=excluded.description,
                description_steps=excluded.description_steps,
                last_updated_by=excluded.last_updated_by,
                last_updated_at=excluded.last_updated_at
            """,
            payload,
        )
        conn.commit()


def delete_defect(defect_id: str) -> None:
    init_db_and_migrate()
    with get_conn() as conn:
        conn.execute(f"DELETE FROM {TABLE_NAME} WHERE defect_id = ?", (defect_id,))
        conn.commit()


# =========================
# Defect ID auto-generation
# Pattern: <MODULE>-<CompanyIndex>-<NNN>
# Example: ND-1-001
# Here we use:
#   CompanyIndex: 1 for 4310, 2 for 8410 (editable)
#   NNN increments per (module + company index)
# =========================
COMPANY_INDEX = {"4310": "1", "8410": "2"}


def next_defect_id(module: str, company_code: str) -> str:
    init_db_and_migrate()

    mod = (module or "OTHER").strip().upper()
    comp_idx = COMPANY_INDEX.get(company_code, "0")
    prefix = f"{mod}-{comp_idx}-"

    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT defect_id FROM {TABLE_NAME} WHERE defect_id LIKE ? ORDER BY defect_id DESC LIMIT 1",
            (prefix + "%",),
        ).fetchall()

    if not rows:
        return f"{prefix}001"

    last_id = rows[0][0]  # e.g., PLM-1-009
    try:
        last_num = int(last_id.split("-")[-1])
        return f"{prefix}{last_num + 1:03d}"
    except Exception:
        # fallback if some older ID format exists
        return f"{prefix}001"


# =========================
# Session: Username (required)
# =========================
st.sidebar.header("User")
username = st.sidebar.text_input("Your username / name (required)", value=st.session_state.get("username", ""))
username = username.strip()
st.session_state.username = username

if not username:
    st.warning("Please enter your username in the sidebar to create or update defects.")


# =========================
# Load data
# =========================
if "df" not in st.session_state:
    st.session_state.df = load_defects_df()

df_all = st.session_state.df.copy()


# =========================
# Create new defect (top)
# =========================
st.subheader("➕ Create New Defect")

with st.form("create_defect_form", clear_on_submit=True):
    c1, c2, c3, c4 = st.columns([1, 1, 1, 1])

    company_code = c1.selectbox("Company Code *", options=COMPANY_CODES, index=0)
    open_date = c2.date_input("Open Date *", value=today_date())  # calendar
    module = c3.selectbox("Module *", options=MODULES, index=0)
    auto_id = next_defect_id(module, company_code)
    c4.text_input("Defect ID (auto-generated)", value=auto_id, disabled=True)

    c5, c6, c7, c8 = st.columns([2, 1, 1, 1])
    defect_title = c5.text_input("Defect Title *", placeholder="Short title")
    defect_type = c6.selectbox("Defect Type", options=DEFECT_TYPES, index=0)
    priority = c7.selectbox("Priority", options=PRIORITIES, index=1)
    status = c8.selectbox("Status", options=STATUSES, index=0)  # default New

    # Do NOT show Resolved Date at the beginning (your requirement)
    resolved_date = None
    if status in {"Resolved", "Closed"}:
        resolved_date = st.date_input("Resolved Date", value=today_date())

    c9, c10, c11, c12 = st.columns([1, 1, 1, 1])
    open_with = c9.selectbox("Open with", options=OPEN_WITH, index=0)
    reported_by = c10.text_input("Reported By *", placeholder="Name (who raised it)")
    responsible = c11.text_input("Responsible (Owner)", placeholder="Who is working now?")
    environment = c12.selectbox("Environment", options=ENVIRONMENTS, index=0)

    linked_test_id = st.text_input("Linked Test ID (optional)")

    description = st.text_area("Description", height=90)
    description_steps = st.text_area("Description / Steps", height=120)

    submitted = st.form_submit_button("Create / Save")

if submitted:
    if not username:
        st.error("Username is required (sidebar).")
    elif not defect_title.strip():
        st.error("Defect Title is required.")
    elif not reported_by.strip():
        st.error("Reported By is required.")
    else:
        row = {
            "Company Code": company_code,
            "Open Date": open_date,
            "Module": module,
            "Defect ID": auto_id,
            "Defect Title": defect_title.strip(),
            "Defect Type": defect_type,
            "Priority": priority,
            "Status": status,
            "Resolved Date": resolved_date,
            "Open with": open_with,
            "Reported By": reported_by.strip(),
            "Responsible": responsible.strip(),
            "Environment": environment,
            "Linked Test ID": linked_test_id.strip(),
            "Description": description.strip(),
            "Description / Steps": description_steps.strip(),
            # audit fields (filled automatically on create)
            "Created By": username,
            "Created At": "",
            "Last Updated By": username,
            "Last Updated At": "",
        }

        try:
            upsert_defect(row, updated_by=username, is_create=True)
            st.success(f"Created defect **{auto_id}** (Created by: {username})")
            st.session_state.df = load_defects_df()
            st.rerun()
        except Exception as e:
            st.error(f"Failed to create defect: {e}")


st.divider()


# =========================
# Filters + Editable table (bottom)
# =========================
st.subheader("📋 Defects (Edit below)")

st.info(
    "Double-click a cell to edit. Then click **Save changes**. "
    "Age (days) is auto-calculated. Created/Updated info captures the username.",
    icon="✍️",
)

# Filters (simple + useful)
f1, f2, f3, f4, f5 = st.columns([1, 1, 1, 1, 2])

company_filter = f1.multiselect("Company Code", options=COMPANY_CODES, default=COMPANY_CODES)
module_filter = f2.multiselect("Module", options=MODULES, default=MODULES)
status_filter = f3.multiselect("Status", options=STATUSES, default=STATUSES)
priority_filter = f4.multiselect("Priority", options=PRIORITIES, default=PRIORITIES)
search = f5.text_input("Search (ID / Title / Responsible / Reported By)", value="").strip().lower()

filtered = df_all.copy()
if company_filter:
    filtered = filtered[filtered["Company Code"].isin(company_filter)]
if module_filter:
    filtered = filtered[filtered["Module"].isin(module_filter)]
if status_filter:
    filtered = filtered[filtered["Status"].isin(status_filter)]
if priority_filter:
    filtered = filtered[filtered["Priority"].isin(priority_filter)]
if search:
    def _hit(r) -> bool:
        s = " ".join(
            [
                str(r.get("Defect ID", "")),
                str(r.get("Defect Title", "")),
                str(r.get("Responsible", "")),
                str(r.get("Reported By", "")),
            ]
        ).lower()
        return search in s

    filtered = filtered[filtered.apply(_hit, axis=1)]

st.write(f"Showing **{len(filtered)}** defects (filtered) • Total: **{len(df_all)}**")

# Editor config
column_config = {
    "Open Date": st.column_config.DateColumn("Open Date"),
    "Resolved Date": st.column_config.DateColumn("Resolved Date"),
    "Company Code": st.column_config.SelectboxColumn("Company Code", options=COMPANY_CODES, required=True),
    "Module": st.column_config.SelectboxColumn("Module", options=MODULES, required=True),
    "Defect Type": st.column_config.SelectboxColumn("Defect Type", options=DEFECT_TYPES),
    "Priority": st.column_config.SelectboxColumn("Priority", options=PRIORITIES, required=True),
    "Status": st.column_config.SelectboxColumn("Status", options=STATUSES, required=True),
    "Open with": st.column_config.SelectboxColumn("Open with", options=OPEN_WITH),
    "Environment": st.column_config.SelectboxColumn("Environment", options=ENVIRONMENTS),
    "Age (days)": st.column_config.NumberColumn("Age (days)"),
    "Description": st.column_config.TextColumn("Description", width="large"),
    "Description / Steps": st.column_config.TextColumn("Description / Steps", width="large"),
}

# Recompute Age (days) before showing editor
tmp = filtered.copy()
tmp["Open Date"] = tmp["Open Date"].apply(parse_any_date)
tmp["Resolved Date"] = tmp["Resolved Date"].apply(parse_any_date)
tmp["Age (days)"] = tmp.apply(lambda r: compute_age_days(r["Open Date"], r["Resolved Date"], str(r["Status"])), axis=1)

edited_df = st.data_editor(
    tmp,
    use_container_width=True,
    hide_index=True,
    column_config=column_config,
    disabled=["Defect ID", "Age (days)", "Created By", "Created At", "Last Updated By", "Last Updated At"],
    num_rows="dynamic",
    key="editor_defects",
)

c_save, c_delete = st.columns([1, 1])

with c_save:
    if st.button("💾 Save changes", type="primary"):
        if not username:
            st.error("Username is required (sidebar) to save changes.")
        else:
            try:
                # Validate: Closed/Resolved must have Resolved Date
                df_to_save = edited_df.copy()
                df_to_save["Open Date"] = df_to_save["Open Date"].apply(parse_any_date)
                df_to_save["Resolved Date"] = df_to_save["Resolved Date"].apply(parse_any_date)

                bad = df_to_save[
                    (df_to_save["Status"].isin(["Resolved", "Closed"])) & (df_to_save["Resolved Date"].isna())
                ]
                if len(bad) > 0:
                    st.warning("Some rows are Resolved/Closed but missing Resolved Date. Please fill Resolved Date for those.")
                # Save all rows shown in editor
                for _, r in df_to_save.iterrows():
                    row = r.to_dict()
                    upsert_defect(row, updated_by=username, is_create=False)

                st.success(f"Saved changes (Updated by: {username})")
                st.session_state.df = load_defects_df()
                st.rerun()
            except Exception as e:
                st.error(f"Save failed: {e}")

with c_delete:
    with st.expander("🗑️ Delete a defect"):
        del_id = st.text_input("Defect ID to delete", placeholder="e.g., PLM-1-003")
        if st.button("Delete", type="secondary"):
            if not username:
                st.error("Username is required (sidebar) to delete.")
            elif del_id.strip():
                delete_defect(del_id.strip())
                st.success(f"Deleted {del_id.strip()}")
                st.session_state.df = load_defects_df()
                st.rerun()
            else:
                st.warning("Enter a Defect ID.")


# =========================
# (Optional) Simple stats (kept, but lightweight)
# =========================
st.divider()
st.subheader("📊 Quick Stats")

df_stats = st.session_state.df.copy()
if len(df_stats) == 0:
    st.info("No defects yet.")
else:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("New", int((df_stats["Status"] == "New").sum()))
    col2.metric("In Progress", int((df_stats["Status"] == "In Progress").sum()))
    col3.metric("Closed", int((df_stats["Status"] == "Closed").sum()))
    col4.metric("P1 not closed", int(((df_stats["Priority"] == "P1 - Critical") & (~df_stats["Status"].isin(["Closed"]))).sum()))

    left, right = st.columns(2)

    with left:
        st.markdown("##### Open items by Module")
        open_df = df_stats[~df_stats["Status"].isin(["Closed"])].copy()
        if len(open_df) == 0:
            st.info("No open defects.")
        else:
            chart = (
                alt.Chart(open_df)
                .mark_bar()
                .encode(
                    x=alt.X("Module:N", sort="-y"),
                    y=alt.Y("count():Q"),
                    color=alt.Color("Status:N"),
                    tooltip=["Module:N", "Status:N", "count():Q"],
                )
            )
            st.altair_chart(chart, use_container_width=True, theme="streamlit")

    with right:
        st.markdown("##### Open items by Priority")
        open_df = df_stats[~df_stats["Status"].isin(["Closed"])].copy()
        if len(open_df) == 0:
            st.info("No open defects.")
        else:
            chart = (
                alt.Chart(open_df)
                .mark_bar()
                .encode(
                    x=alt.X("Priority:N", sort=PRIORITIES),
                    y=alt.Y("count():Q"),
                    tooltip=["Priority:N", "count():Q"],
                )
            )
            st.altair_chart(chart, use_container_width=True, theme="streamlit")


# =========================
# Export (CSV)
# =========================
st.subheader("⬇️ Export")
export_df = st.session_state.df.copy()
export_df["Open Date"] = export_df["Open Date"].apply(lambda d: d.isoformat() if isinstance(d, dt.date) else "")
export_df["Resolved Date"] = export_df["Resolved Date"].apply(lambda d: d.isoformat() if isinstance(d, dt.date) else "")
csv_bytes = export_df.to_csv(index=False).encode("utf-8")
st.download_button("Download CSV", data=csv_bytes, file_name="defects_export.csv", mime="text/csv")
