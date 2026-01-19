# streamlit_app.py
# A Streamlit defect tracker that mirrors your Excel sheet structure.
# Storage: SQLite (defects.db) in the same folder as this app.

import sqlite3
import datetime as dt
from typing import Optional, List, Dict, Any

import numpy as np
import pandas as pd
import streamlit as st
import altair as alt


# -----------------------------
# App config
# -----------------------------
st.set_page_config(page_title="Defect Tracker", page_icon="🎫", layout="wide")
st.title("🎫 Defect Tracker (Excel Mirror)")
st.caption("Consultants can create and update defects; data is stored in SQLite (defects.db).")


# -----------------------------
# Constants (edit these to match your org)
# -----------------------------
DB_PATH = "defects.db"
TABLE_NAME = "defects"

MODULES = ["PLM", "PP", "FI", "SD", "MM", "QM", "WM", "EWM", "BW", "BASIS", "ABAP", "OTHER"]
DEFECT_TYPES = ["Functional", "Data Migration", "Test Data", "EDI set up", "Configuration", "Security/Authorization", "Performance", "Other"]
PRIORITIES = ["P1 - Critical", "P2 - High", "P3 - Medium", "P4 - Low"]
STATUSES = ["Open", "In Progress", "Closed"]
ENVIRONMENTS = ["D1S", "Q1S", "P1S", "DEV", "QA", "UAT", "PRD", "Other"]
OPEN_WITH = ["SDS", "SNP", "Client", "Other"]
SEVERITIES = ["Critical", "High", "Medium", "Low", ""]  # optional


# -----------------------------
# Helpers
# -----------------------------
def today_date() -> dt.date:
    return dt.date.today()


def parse_any_date(x) -> Optional[dt.date]:
    """Parse common date formats found in sheets (08-Dec-25, 04.12.2025, 17/12/2025, etc.)."""
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return None
    if isinstance(x, dt.date) and not isinstance(x, dt.datetime):
        return x
    if isinstance(x, dt.datetime):
        return x.date()
    s = str(x).strip()
    if not s or s.lower() in {"nan", "none", "null"}:
        return None

    # Try pandas robust parser
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
    end = resolved_date if (status == "Closed" and resolved_date) else today_date()
    try:
        return max(0, (end - open_date).days)
    except Exception:
        return None


def get_conn() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db() -> None:
    """Create table if not exists."""
    with get_conn() as conn:
        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                defect_id TEXT PRIMARY KEY,
                company_code TEXT,
                open_date TEXT,
                module TEXT,
                defect_title TEXT,
                defect_short TEXT,
                description TEXT,
                defect_type TEXT,
                resolution_process TEXT,
                priority TEXT,
                status TEXT,
                resolved_date TEXT,
                open_with TEXT,
                reported_by TEXT,
                responsible TEXT,
                comments TEXT,
                severity TEXT,
                environment TEXT,
                linked_test_id TEXT,
                build_no TEXT,
                description_steps TEXT,
                updated_at TEXT
            )
            """
        )
        conn.commit()


def load_defects_df() -> pd.DataFrame:
    init_db()
    with get_conn() as conn:
        df = pd.read_sql_query(f"SELECT * FROM {TABLE_NAME}", conn)

    if df.empty:
        # Create an empty dataframe with proper columns (mirrors sheet)
        df = pd.DataFrame(
            columns=[
                "Company Code",
                "Open Date",
                "Module",
                "Defect ID",
                "Defect",
                "Description",
                "Defect Type",
                "Resolution process",
                "Priority",
                "Status",
                "Resolved Date",
                "Open with",
                "Reported By",
                "Responsible",
                "Comments",
                "Age (days)",
                "Severity",
                "Environment",
                "Linked Test ID",
                "Build #",
                "Description / Steps",
            ]
        )
        return df

    # Map DB columns -> sheet-like columns
    df_sheet = pd.DataFrame(
        {
            "Company Code": df["company_code"],
            "Open Date": df["open_date"].apply(parse_any_date),
            "Module": df["module"],
            "Defect ID": df["defect_id"],
            "Defect": df["defect_title"].fillna(""),
            "Description": df["description"].fillna(""),
            "Defect Type": df["defect_type"].fillna(""),
            "Resolution process": df["resolution_process"].fillna(""),
            "Priority": df["priority"].fillna(""),
            "Status": df["status"].fillna(""),
            "Resolved Date": df["resolved_date"].apply(parse_any_date),
            "Open with": df["open_with"].fillna(""),
            "Reported By": df["reported_by"].fillna(""),
            "Responsible": df["responsible"].fillna(""),
            "Comments": df["comments"].fillna(""),
            "Severity": df["severity"].fillna(""),
            "Environment": df["environment"].fillna(""),
            "Linked Test ID": df["linked_test_id"].fillna(""),
            "Build #": df["build_no"].fillna(""),
            "Description / Steps": df["description_steps"].fillna(""),
        }
    )

    # Compute Age (days)
    df_sheet["Age (days)"] = df_sheet.apply(
        lambda r: compute_age_days(r["Open Date"], r["Resolved Date"], str(r["Status"])),
        axis=1,
    )

    # Order columns like the sheet
    df_sheet = df_sheet[
        [
            "Company Code",
            "Open Date",
            "Module",
            "Defect ID",
            "Defect",
            "Description",
            "Defect Type",
            "Resolution process",
            "Priority",
            "Status",
            "Resolved Date",
            "Open with",
            "Reported By",
            "Responsible",
            "Comments",
            "Age (days)",
            "Severity",
            "Environment",
            "Linked Test ID",
            "Build #",
            "Description / Steps",
        ]
    ]

    return df_sheet


def upsert_row(row: Dict[str, Any]) -> None:
    """Insert or update a defect row in SQLite."""
    init_db()
    now = dt.datetime.now().isoformat(timespec="seconds")

    defect_id = str(row.get("Defect ID", "")).strip()
    if not defect_id:
        raise ValueError("Defect ID is required.")

    open_date = parse_any_date(row.get("Open Date"))
    resolved_date = parse_any_date(row.get("Resolved Date"))

    payload = {
        "defect_id": defect_id,
        "company_code": str(row.get("Company Code", "")).strip(),
        "open_date": date_to_str(open_date),
        "module": str(row.get("Module", "")).strip(),
        "defect_title": str(row.get("Defect", "")).strip(),
        "defect_short": str(row.get("Defect", "")).strip(),
        "description": str(row.get("Description", "")).strip(),
        "defect_type": str(row.get("Defect Type", "")).strip(),
        "resolution_process": str(row.get("Resolution process", "")).strip(),
        "priority": str(row.get("Priority", "")).strip(),
        "status": str(row.get("Status", "")).strip(),
        "resolved_date": date_to_str(resolved_date),
        "open_with": str(row.get("Open with", "")).strip(),
        "reported_by": str(row.get("Reported By", "")).strip(),
        "responsible": str(row.get("Responsible", "")).strip(),
        "comments": str(row.get("Comments", "")).strip(),
        "severity": str(row.get("Severity", "")).strip(),
        "environment": str(row.get("Environment", "")).strip(),
        "linked_test_id": str(row.get("Linked Test ID", "")).strip(),
        "build_no": str(row.get("Build #", "")).strip(),
        "description_steps": str(row.get("Description / Steps", "")).strip(),
        "updated_at": now,
    }

    with get_conn() as conn:
        conn.execute(
            f"""
            INSERT INTO {TABLE_NAME} (
                defect_id, company_code, open_date, module, defect_title, defect_short,
                description, defect_type, resolution_process, priority, status,
                resolved_date, open_with, reported_by, responsible, comments,
                severity, environment, linked_test_id, build_no, description_steps, updated_at
            )
            VALUES (
                :defect_id, :company_code, :open_date, :module, :defect_title, :defect_short,
                :description, :defect_type, :resolution_process, :priority, :status,
                :resolved_date, :open_with, :reported_by, :responsible, :comments,
                :severity, :environment, :linked_test_id, :build_no, :description_steps, :updated_at
            )
            ON CONFLICT(defect_id) DO UPDATE SET
                company_code=excluded.company_code,
                open_date=excluded.open_date,
                module=excluded.module,
                defect_title=excluded.defect_title,
                defect_short=excluded.defect_short,
                description=excluded.description,
                defect_type=excluded.defect_type,
                resolution_process=excluded.resolution_process,
                priority=excluded.priority,
                status=excluded.status,
                resolved_date=excluded.resolved_date,
                open_with=excluded.open_with,
                reported_by=excluded.reported_by,
                responsible=excluded.responsible,
                comments=excluded.comments,
                severity=excluded.severity,
                environment=excluded.environment,
                linked_test_id=excluded.linked_test_id,
                build_no=excluded.build_no,
                description_steps=excluded.description_steps,
                updated_at=excluded.updated_at
            """,
            payload,
        )
        conn.commit()


def delete_defect(defect_id: str) -> None:
    init_db()
    with get_conn() as conn:
        conn.execute(f"DELETE FROM {TABLE_NAME} WHERE defect_id = ?", (defect_id,))
        conn.commit()


def normalize_df_for_editor(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure consistent dtypes for editor + charts."""
    out = df.copy()

    # Dates as datetime.date (Streamlit date editor likes these)
    out["Open Date"] = out["Open Date"].apply(parse_any_date)
    out["Resolved Date"] = out["Resolved Date"].apply(parse_any_date)

    # Compute Age (days)
    out["Age (days)"] = out.apply(
        lambda r: compute_age_days(r["Open Date"], r["Resolved Date"], str(r["Status"])),
        axis=1,
    )

    # Empty -> ''
    for c in [
        "Company Code",
        "Module",
        "Defect ID",
        "Defect",
        "Description",
        "Defect Type",
        "Resolution process",
        "Priority",
        "Status",
        "Open with",
        "Reported By",
        "Responsible",
        "Comments",
        "Severity",
        "Environment",
        "Linked Test ID",
        "Build #",
        "Description / Steps",
    ]:
        if c in out.columns:
            out[c] = out[c].fillna("").astype(str)

    return out


# -----------------------------
# Load data
# -----------------------------
if "df" not in st.session_state:
    st.session_state.df = normalize_df_for_editor(load_defects_df())

df_all = st.session_state.df


# -----------------------------
# Sidebar: filters
# -----------------------------
st.sidebar.header("Filters")

def multiselect_all(label: str, options: List[str], series: pd.Series):
    present = sorted([x for x in series.dropna().astype(str).unique().tolist() if x != ""])
    opts = [o for o in options if o in present] + [o for o in present if o not in options]
    chosen = st.sidebar.multiselect(label, options=opts, default=opts)
    return chosen

company_vals = sorted([x for x in df_all["Company Code"].unique().tolist() if str(x).strip() != ""])
module_sel = multiselect_all("Module", MODULES, df_all["Module"])
status_sel = multiselect_all("Status", STATUSES, df_all["Status"])
priority_sel = multiselect_all("Priority", PRIORITIES, df_all["Priority"])

responsible_vals = sorted([x for x in df_all["Responsible"].unique().tolist() if str(x).strip() != ""])
responsible_sel = st.sidebar.multiselect("Responsible", options=responsible_vals, default=responsible_vals)

company_sel = st.sidebar.multiselect("Company Code", options=company_vals, default=company_vals)

date_min = df_all["Open Date"].dropna().min()
date_max = df_all["Open Date"].dropna().max()
if pd.isna(date_min) or pd.isna(date_max):
    date_range = None
else:
    date_range = st.sidebar.date_input("Open Date range", value=(date_min, date_max))

filtered = df_all.copy()
if company_sel:
    filtered = filtered[filtered["Company Code"].isin(company_sel)]
filtered = filtered[filtered["Module"].isin(module_sel)]
filtered = filtered[filtered["Status"].isin(status_sel)]
filtered = filtered[filtered["Priority"].isin(priority_sel)]
if responsible_sel:
    filtered = filtered[filtered["Responsible"].isin(responsible_sel)]
if date_range and isinstance(date_range, tuple) and len(date_range) == 2:
    start, end = date_range
    filtered = filtered[
        filtered["Open Date"].apply(lambda d: d is not None and start <= d <= end)
    ]

st.write(f"Rows: **{len(filtered)}** (filtered) • Total: **{len(df_all)}**")


# -----------------------------
# Add new defect (Consultant entry form)
# -----------------------------
with st.expander("➕ Create new defect", expanded=True):
    with st.form("create_defect_form", clear_on_submit=False):
        c1, c2, c3, c4 = st.columns([1, 1, 1, 1])

        company_code = c1.text_input("Company Code *", placeholder="e.g., 4310")
        open_date = c2.date_input("Open Date *", value=today_date())
        module = c3.selectbox("Module *", MODULES, index=0)
        defect_id = c4.text_input("Defect ID *", placeholder="e.g., DF-SD003 / PLM-DF002")

        c5, c6, c7, c8 = st.columns([1, 1, 1, 1])
        defect_title = c5.text_input("Defect (Title) *", placeholder="Short title")
        defect_type = c6.selectbox("Defect Type", DEFECT_TYPES, index=0)
        priority = c7.selectbox("Priority", PRIORITIES, index=1)
        status = c8.selectbox("Status", STATUSES, index=0)

        c9, c10, c11, c12 = st.columns([1, 1, 1, 1])
        resolved_date = c9.date_input("Resolved Date (if Closed)", value=None)
        open_with = c10.selectbox("Open with", OPEN_WITH, index=0)
        reported_by = c11.text_input("Reported By", placeholder="Name")
        responsible = c12.text_input("Responsible", placeholder="Owner")

        c13, c14, c15 = st.columns([1, 1, 1])
        severity = c13.selectbox("Severity (optional)", SEVERITIES, index=len(SEVERITIES) - 1)
        environment = c14.selectbox("Environment", ENVIRONMENTS, index=0)
        build_no = c15.text_input("Build #", placeholder="Transport/Build ref")

        linked_test_id = st.text_input("Linked Test ID", placeholder="Optional")

        description = st.text_area("Description", height=100)
        description_steps = st.text_area("Description / Steps", height=120)
        resolution_process = st.text_area("Resolution process", height=120)
        comments = st.text_area("Comments", height=100)

        submitted = st.form_submit_button("Create / Save defect")

    if submitted:
        if not company_code.strip() or not defect_id.strip() or not defect_title.strip():
            st.error("Please fill required fields: Company Code, Defect ID, Defect (Title).")
        else:
            # If status is Closed, resolved_date should be set
            if status == "Closed" and not resolved_date:
                st.warning("Status is Closed but Resolved Date is empty. Please add Resolved Date.")
            row = {
                "Company Code": company_code.strip(),
                "Open Date": open_date,
                "Module": module,
                "Defect ID": defect_id.strip(),
                "Defect": defect_title.strip(),
                "Description": description.strip(),
                "Defect Type": defect_type,
                "Resolution process": resolution_process.strip(),
                "Priority": priority,
                "Status": status,
                "Resolved Date": resolved_date,
                "Open with": open_with,
                "Reported By": reported_by.strip(),
                "Responsible": responsible.strip(),
                "Comments": comments.strip(),
                "Severity": severity,
                "Environment": environment,
                "Linked Test ID": linked_test_id.strip(),
                "Build #": build_no.strip(),
                "Description / Steps": description_steps.strip(),
            }
            try:
                upsert_row(row)
                st.success(f"Saved defect: {defect_id.strip()}")
                st.session_state.df = normalize_df_for_editor(load_defects_df())
                st.rerun()
            except Exception as e:
                st.error(f"Failed to save: {e}")


# -----------------------------
# Editable table (Excel-like)
# -----------------------------
st.subheader("📋 Defects (editable, like the sheet)")

st.info(
    "Double-click a cell to edit. Then click **Save changes** below. "
    "Age (days) is calculated automatically and cannot be edited.",
    icon="✍️",
)

column_config = {
    "Open Date": st.column_config.DateColumn("Open Date", help="When defect was raised"),
    "Resolved Date": st.column_config.DateColumn("Resolved Date", help="When defect was closed"),
    "Module": st.column_config.SelectboxColumn("Module", options=MODULES, required=True),
    "Defect Type": st.column_config.SelectboxColumn("Defect Type", options=DEFECT_TYPES),
    "Priority": st.column_config.SelectboxColumn("Priority", options=PRIORITIES, required=True),
    "Status": st.column_config.SelectboxColumn("Status", options=STATUSES, required=True),
    "Environment": st.column_config.SelectboxColumn("Environment", options=ENVIRONMENTS),
    "Open with": st.column_config.SelectboxColumn("Open with", options=OPEN_WITH),
    "Severity": st.column_config.SelectboxColumn("Severity", options=SEVERITIES),
    "Age (days)": st.column_config.NumberColumn("Age (days)", help="Auto-calculated"),
    "Description": st.column_config.TextColumn("Description", width="large"),
    "Resolution process": st.column_config.TextColumn("Resolution process", width="large"),
    "Description / Steps": st.column_config.TextColumn("Description / Steps", width="large"),
    "Comments": st.column_config.TextColumn("Comments", width="large"),
}

edited_df = st.data_editor(
    filtered,
    use_container_width=True,
    hide_index=True,
    column_config=column_config,
    disabled=["Age (days)"],  # always computed
    num_rows="dynamic",
    key="editor",
)

c_save, c_delete = st.columns([1, 1])

with c_save:
    if st.button("💾 Save changes", type="primary"):
        try:
            # Save every row currently visible in editor.
            # (If you want "save only modified rows", we can add diffing later.)
            save_df = normalize_df_for_editor(edited_df)

            # Validate essentials
            missing_ids = save_df["Defect ID"].str.strip() == ""
            if missing_ids.any():
                st.error("Some rows are missing Defect ID. Please fill Defect ID for all rows before saving.")
            else:
                for _, r in save_df.iterrows():
                    row = r.to_dict()
                    # If closed, allow resolved date empty but warn
                    if str(row.get("Status", "")).strip() == "Closed" and not parse_any_date(row.get("Resolved Date")):
                        # keep saving but warn
                        pass
                    upsert_row(row)

                st.success("Saved changes to database.")
                st.session_state.df = normalize_df_for_editor(load_defects_df())
                st.rerun()
        except Exception as e:
            st.error(f"Save failed: {e}")

with c_delete:
    with st.expander("🗑️ Delete a defect"):
        del_id = st.text_input("Enter Defect ID to delete", placeholder="e.g., DF-SD003")
        if st.button("Delete", type="secondary"):
            if del_id.strip():
                delete_defect(del_id.strip())
                st.success(f"Deleted: {del_id.strip()}")
                st.session_state.df = normalize_df_for_editor(load_defects_df())
                st.rerun()
            else:
                st.warning("Please enter a Defect ID.")


# -----------------------------
# Statistics (management view)
# -----------------------------
st.subheader("📊 Statistics")

df_stats = normalize_df_for_editor(load_defects_df())
df_stats = df_stats.copy()

# Quick metrics
col1, col2, col3, col4 = st.columns(4)
open_count = int((df_stats["Status"] == "Open").sum())
inprog_count = int((df_stats["Status"] == "In Progress").sum())
closed_count = int((df_stats["Status"] == "Closed").sum())
p1_open = int(((df_stats["Priority"] == "P1 - Critical") & (df_stats["Status"] != "Closed")).sum())

col1.metric("Open", open_count)
col2.metric("In Progress", inprog_count)
col3.metric("Closed", closed_count)
col4.metric("P1 not closed", p1_open)

st.write("")

# Aging buckets
def aging_bucket(age: Optional[int]) -> str:
    if age is None:
        return "Unknown"
    if age <= 2:
        return "0–2"
    if age <= 7:
        return "3–7"
    if age <= 14:
        return "8–14"
    return "15+"

df_stats["Aging Bucket"] = df_stats["Age (days)"].apply(aging_bucket)

c1, c2 = st.columns(2)

with c1:
    st.markdown("##### Open defects by Module")
    plot_df = df_stats[df_stats["Status"] != "Closed"].copy()
    if len(plot_df) == 0:
        st.info("No open defects.")
    else:
        chart = (
            alt.Chart(plot_df)
            .mark_bar()
            .encode(
                x=alt.X("Module:N", sort="-y"),
                y=alt.Y("count():Q"),
                color=alt.Color("Status:N"),
                tooltip=["Module:N", "Status:N", "count():Q"],
            )
        )
        st.altair_chart(chart, use_container_width=True, theme="streamlit")

with c2:
    st.markdown("##### Aging distribution (not closed)")
    plot_df = df_stats[df_stats["Status"] != "Closed"].copy()
    if len(plot_df) == 0:
        st.info("No open defects.")
    else:
        chart = (
            alt.Chart(plot_df)
            .mark_bar()
            .encode(
                x=alt.X("Aging Bucket:N", sort=["0–2", "3–7", "8–14", "15+", "Unknown"]),
                y=alt.Y("count():Q"),
                color=alt.Color("Priority:N"),
                tooltip=["Aging Bucket:N", "Priority:N", "count():Q"],
            )
        )
        st.altair_chart(chart, use_container_width=True, theme="streamlit")


# -----------------------------
# Export
# -----------------------------
st.subheader("⬇️ Export")
export_df = normalize_df_for_editor(load_defects_df()).copy()
# Make dates export-friendly
export_df["Open Date"] = export_df["Open Date"].apply(lambda d: d.isoformat() if isinstance(d, dt.date) else "")
export_df["Resolved Date"] = export_df["Resolved Date"].apply(lambda d: d.isoformat() if isinstance(d, dt.date) else "")

csv_bytes = export_df.to_csv(index=False).encode("utf-8")
st.download_button("Download CSV", data=csv_bytes, file_name="defects_export.csv", mime="text/csv")

st.caption("Tip: If you want import from Excel or multi-user locking, tell me — we can add it next.")
