# streamlit_app.py
# Bosch-level premium Streamlit defect tracker (Excel-mirror, clean UI)
# Storage: SQLite (defects.db) in the same folder as this app.

import sqlite3
import datetime as dt
from typing import Optional, Dict, Any, List

import pandas as pd
import streamlit as st
import altair as alt


# =========================
# Branding / Page
# =========================
APP_NAME = "Asterisk Defector Hacker"
DB_PATH = "defects.db"
TABLE_NAME = "defects"

st.set_page_config(page_title=APP_NAME, page_icon="🎫", layout="wide")

# Premium CSS (keeps it clean, reduces Streamlit "toy" look)
st.markdown(
    """
<style>
/* General spacing */
.block-container { padding-top: 1.2rem; padding-bottom: 2.2rem; }

/* Headings */
h1 { letter-spacing: -0.02em; }
[data-testid="stCaptionContainer"] { opacity: 0.8; }

/* Buttons */
.stButton button { border-radius: 12px; padding: 0.55rem 0.9rem; }

/* Inputs */
[data-testid="stTextInput"] input, [data-testid="stTextArea"] textarea,
[data-testid="stSelectbox"] div, [data-testid="stDateInput"] input {
  border-radius: 12px !important;
}

/* Remove “empty feel” by styling expanders */
details { border-radius: 16px; overflow: hidden; }
summary { font-weight: 600; }

/* Data editor look */
[data-testid="stDataEditor"] { border-radius: 16px; overflow: hidden; }

/* Info box polish */
[data-testid="stAlert"] { border-radius: 16px; }
</style>
""",
    unsafe_allow_html=True,
)

st.title(f"🎫 {APP_NAME}")
st.caption("Create defects fast. Track ownership, status, aging. Edit in a clean, Excel-like table.")


# =========================
# Controlled vocab (your rules)
# =========================
COMPANY_CODES = ["4310", "8410"]  # only these two
COMPANY_INDEX = {"4310": "1", "8410": "2"}  # used in ID generation

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

# You asked default should be "New"
STATUSES = ["New", "In Progress", "Blocked", "Resolved", "Closed", "Reopened"]

# You wanted these environments (keeping exactly these)
ENVIRONMENTS = ["P1S", "Q1S", "Q2S", "Q2C"]

OPEN_WITH = ["SDS", "SNP", "Client", "Other"]


# =========================
# Helpers
# =========================
def today_date() -> dt.date:
    return dt.date.today()


def parse_any_date(x) -> Optional[dt.date]:
    if x is None:
        return None
    if isinstance(x, dt.datetime):
        return x.date()
    if isinstance(x, dt.date):
        return x
    s = str(x).strip()
    if not s or s.lower() in {"nan", "none", "null"}:
        return None
    try:
        # dayfirst handles 04.12.2025 and 17/12/2025
        return pd.to_datetime(s, dayfirst=True, errors="raise").date()
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


def get_conn() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db_and_migrate() -> None:
    """
    Premium, stable schema.
    Includes audit + ownership so you always know who created/updated and who's working.
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
        "current_owner": "TEXT",  # who is working now (editable)
        "environment": "TEXT",
        "linked_test_id": "TEXT",
        "description": "TEXT",
        "steps": "TEXT",
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
                current_owner TEXT,
                environment TEXT,
                linked_test_id TEXT,
                description TEXT,
                steps TEXT,
                created_by TEXT,
                created_at TEXT,
                last_updated_by TEXT,
                last_updated_at TEXT
            )
            """
        )

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

    cols = [
        "Company Code",
        "Open Date",
        "Module",
        "Defect ID",
        "Defect Title",
        "Defect Type",
        "Priority",
        "Status",
        "Current Owner",
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

    if df.empty:
        return pd.DataFrame(columns=cols)

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
            "Current Owner": df.get("current_owner", "").fillna("").astype(str),
            "Resolved Date": df.get("resolved_date", "").apply(parse_any_date),
            "Open with": df.get("open_with", "").fillna("").astype(str),
            "Reported By": df.get("reported_by", "").fillna("").astype(str),
            "Responsible": df.get("responsible", "").fillna("").astype(str),
            "Environment": df.get("environment", "").fillna("").astype(str),
            "Linked Test ID": df.get("linked_test_id", "").fillna("").astype(str),
            "Description": df.get("description", "").fillna("").astype(str),
            "Description / Steps": df.get("steps", "").fillna("").astype(str),
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

    return out[cols]


def upsert_defect(row: Dict[str, Any], actor: str, is_create: bool) -> None:
    init_db_and_migrate()
    now = dt.datetime.now().isoformat(timespec="seconds")

    defect_id = str(row.get("Defect ID", "")).strip()
    if not defect_id:
        raise ValueError("Defect ID missing.")

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
        "current_owner": str(row.get("Current Owner", "")).strip(),
        "environment": str(row.get("Environment", "")).strip(),
        "linked_test_id": str(row.get("Linked Test ID", "")).strip(),
        "description": str(row.get("Description", "")).strip(),
        "steps": str(row.get("Description / Steps", "")).strip(),
        "created_by": str(row.get("Created By", "")).strip(),
        "created_at": str(row.get("Created At", "")).strip(),
        "last_updated_by": actor.strip(),
        "last_updated_at": now,
    }

    if is_create:
        payload["created_by"] = actor.strip()
        payload["created_at"] = now
        payload["last_updated_by"] = actor.strip()
        payload["last_updated_at"] = now

    with get_conn() as conn:
        conn.execute(
            f"""
            INSERT INTO {TABLE_NAME} (
                defect_id, company_code, open_date, module, defect_title, defect_type,
                priority, status, resolved_date, open_with, reported_by, responsible,
                current_owner, environment, linked_test_id, description, steps,
                created_by, created_at, last_updated_by, last_updated_at
            ) VALUES (
                :defect_id, :company_code, :open_date, :module, :defect_title, :defect_type,
                :priority, :status, :resolved_date, :open_with, :reported_by, :responsible,
                :current_owner, :environment, :linked_test_id, :description, :steps,
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
                current_owner=excluded.current_owner,
                environment=excluded.environment,
                linked_test_id=excluded.linked_test_id,
                description=excluded.description,
                steps=excluded.steps,
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
# Defect ID generation
# Pattern: <MODULE>-<CompanyIndex>-<NNN>
# Example: ND-1-001 (if module is ND)
# =========================
def next_defect_id(module: str, company_code: str) -> str:
    init_db_and_migrate()

    mod = (module or "OTHER").strip().upper()
    comp_idx = COMPANY_INDEX.get(company_code, "0")
    prefix = f"{mod}-{comp_idx}-"

    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT defect_id FROM {TABLE_NAME} WHERE defect_id LIKE ?",
            (prefix + "%",),
        ).fetchall()

    max_num = 0
    for (did,) in rows:
        try:
            n = int(str(did).split("-")[-1])
            if n > max_num:
                max_num = n
        except Exception:
            continue

    return f"{prefix}{max_num + 1:03d}"


# =========================
# Sidebar (premium, no red chips)
# =========================
st.sidebar.markdown("### User")
username = st.sidebar.text_input("Username (required)", value=st.session_state.get("username", "")).strip()
st.session_state.username = username

st.sidebar.markdown("---")
st.sidebar.markdown("### Filters")

def with_all(label: str, options: List[str]) -> List[str]:
    return ["All"] + options

company_choice = st.sidebar.selectbox("Company Code", options=with_all("Company", COMPANY_CODES), index=0)
module_choice = st.sidebar.selectbox("Module", options=with_all("Module", MODULES), index=0)
status_choice = st.sidebar.selectbox("Status", options=with_all("Status", STATUSES), index=0)
priority_choice = st.sidebar.selectbox("Priority", options=with_all("Priority", PRIORITIES), index=0)

owner_filter = st.sidebar.text_input("Owner contains", value="", help="Matches Current Owner / Responsible").strip().lower()
search = st.sidebar.text_input("Search", value="", help="Matches Defect ID / Title / Reported By").strip().lower()

st.sidebar.markdown("---")
show_closed = st.sidebar.toggle("Include Closed", value=True)


# =========================
# Load data (session)
# =========================
if "df" not in st.session_state:
    st.session_state.df = load_defects_df()

df_all = st.session_state.df.copy()


def apply_filters(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    if company_choice != "All":
        out = out[out["Company Code"] == company_choice]
    if module_choice != "All":
        out = out[out["Module"] == module_choice]
    if status_choice != "All":
        out = out[out["Status"] == status_choice]
    if priority_choice != "All":
        out = out[out["Priority"] == priority_choice]
    if not show_closed:
        out = out[out["Status"] != "Closed"]

    if owner_filter:
        s = (
            out[["Current Owner", "Responsible"]]
            .astype(str)
            .agg(" ".join, axis=1)
            .str.lower()
        )
        out = out[s.str.contains(owner_filter, na=False)]

    if search:
        s = (
            out[["Defect ID", "Defect Title", "Reported By"]]
            .astype(str)
            .agg(" ".join, axis=1)
            .str.lower()
        )
        out = out[s.str.contains(search, na=False)]

    return out


filtered = apply_filters(df_all)


# =========================
# Tabs (premium layout)
# =========================
tab_create, tab_defects, tab_dashboard, tab_export = st.tabs(
    ["➕ Create Defect", "📋 Defects", "📊 Dashboard", "⬇️ Export"]
)


# =========================
# CREATE TAB
# =========================
with tab_create:
    # Premium empty-state guidance
    if not username:
        st.warning("Enter your username in the sidebar to create defects.", icon="👤")

    st.markdown("#### Create New Defect")

    with st.form("create_form", clear_on_submit=True):
        r1c1, r1c2, r1c3, r1c4 = st.columns([1, 1, 1, 1])

        company_code = r1c1.selectbox("Company Code *", options=COMPANY_CODES, index=0)
        open_date = r1c2.date_input("Open Date *", value=today_date())
        module = r1c3.selectbox("Module *", options=MODULES, index=0)

        auto_id = next_defect_id(module, company_code)
        r1c4.text_input("Defect ID (auto)", value=auto_id, disabled=True)

        r2c1, r2c2, r2c3, r2c4 = st.columns([2, 1, 1, 1])
        defect_title = r2c1.text_input("Defect Title *", placeholder="Short, clear title")
        defect_type = r2c2.selectbox("Defect Type", options=DEFECT_TYPES, index=0)
        priority = r2c3.selectbox("Priority", options=PRIORITIES, index=1)
        status = r2c4.selectbox("Status", options=STATUSES, index=0)  # default New

        # Only show Resolved Date when relevant (your requirement)
        resolved_date = None
        if status in {"Resolved", "Closed"}:
            resolved_date = st.date_input("Resolved Date *", value=today_date())

        r3c1, r3c2, r3c3, r3c4 = st.columns([1, 1, 1, 1])
        open_with = r3c1.selectbox("Open with", options=OPEN_WITH, index=0)
        reported_by = r3c2.text_input("Reported By *", placeholder="Name of reporter")
        responsible = r3c3.text_input("Responsible (team/lead)", placeholder="Optional")
        environment = r3c4.selectbox("Environment", options=ENVIRONMENTS, index=0)

        # Current Owner = who is working NOW (your key ask)
        current_owner = st.text_input("Current Owner (who is working now)", value="")

        linked_test_id = st.text_input("Linked Test ID (optional)")

        description = st.text_area("Description (what is the issue?)", height=110)
        steps = st.text_area("Description / Steps (how to reproduce?)", height=140)

        submit = st.form_submit_button("Create / Save", type="primary")

    if submit:
        if not username:
            st.error("Username is required (sidebar).")
        elif not defect_title.strip():
            st.error("Defect Title is required.")
        elif not reported_by.strip():
            st.error("Reported By is required.")
        elif status in {"Resolved", "Closed"} and not resolved_date:
            st.error("Resolved Date is required when Status is Resolved/Closed.")
        else:
            # If current owner not provided, default to creator (username) for New/In Progress
            owner_value = current_owner.strip()
            if not owner_value and status in {"New", "In Progress", "Blocked", "Reopened"}:
                owner_value = username

            row = {
                "Company Code": company_code,
                "Open Date": open_date,
                "Module": module,
                "Defect ID": auto_id,
                "Defect Title": defect_title.strip(),
                "Defect Type": defect_type,
                "Priority": priority,
                "Status": status,
                "Current Owner": owner_value,
                "Resolved Date": resolved_date,
                "Open with": open_with,
                "Reported By": reported_by.strip(),
                "Responsible": responsible.strip(),
                "Environment": environment,
                "Linked Test ID": linked_test_id.strip(),
                "Description": description.strip(),
                "Description / Steps": steps.strip(),
                "Created By": username,
                "Created At": "",
                "Last Updated By": username,
                "Last Updated At": "",
            }

            try:
                upsert_defect(row, actor=username, is_create=True)
                st.success(f"Created **{auto_id}** • Owner: **{owner_value or '-'}** • Created by: **{username}**")
                st.session_state.df = load_defects_df()
                st.rerun()
            except Exception as e:
                st.error(f"Create failed: {e}")


# =========================
# DEFECTS TAB (edit below)
# =========================
with tab_defects:
    st.markdown("#### Defects")

    if df_all.empty:
        st.info("No defects yet. Create your first defect in the **Create Defect** tab.", icon="📝")
    else:
        st.write(f"Showing **{len(filtered)}** (filtered) • Total **{len(df_all)}**")

        # Recompute Age for display
        tmp = filtered.copy()
        tmp["Open Date"] = tmp["Open Date"].apply(parse_any_date)
        tmp["Resolved Date"] = tmp["Resolved Date"].apply(parse_any_date)
        tmp["Age (days)"] = tmp.apply(lambda r: compute_age_days(r["Open Date"], r["Resolved Date"], str(r["Status"])), axis=1)

        # Make “premium” column configs
        column_config = {
            "Company Code": st.column_config.SelectboxColumn("Company Code", options=COMPANY_CODES, required=True),
            "Open Date": st.column_config.DateColumn("Open Date"),
            "Module": st.column_config.SelectboxColumn("Module", options=MODULES, required=True),
            "Defect Type": st.column_config.SelectboxColumn("Defect Type", options=DEFECT_TYPES),
            "Priority": st.column_config.SelectboxColumn("Priority", options=PRIORITIES, required=True),
            "Status": st.column_config.SelectboxColumn("Status", options=STATUSES, required=True),
            "Current Owner": st.column_config.TextColumn("Current Owner", help="Who is working now"),
            "Resolved Date": st.column_config.DateColumn("Resolved Date"),
            "Open with": st.column_config.SelectboxColumn("Open with", options=OPEN_WITH),
            "Environment": st.column_config.SelectboxColumn("Environment", options=ENVIRONMENTS),
            "Age (days)": st.column_config.NumberColumn("Age (days)", help="Auto-calculated"),
            "Description": st.column_config.TextColumn("Description", width="large"),
            "Description / Steps": st.column_config.TextColumn("Description / Steps", width="large"),
        }

        st.info(
            "Edit cells directly. Then click **Save changes**. "
            "Age (days) is auto-calculated. Created/Updated captures the username.",
            icon="✍️",
        )

        edited_df = st.data_editor(
            tmp,
            use_container_width=True,
            hide_index=True,
            column_config=column_config,
            disabled=["Defect ID", "Age (days)", "Created By", "Created At", "Last Updated By", "Last Updated At"],
            num_rows="dynamic",
            height=520,
            key="defects_editor",
        )

        c1, c2, c3 = st.columns([1, 1, 2])

        with c1:
            if st.button("💾 Save changes", type="primary"):
                if not username:
                    st.error("Username is required (sidebar) to save changes.")
                else:
                    try:
                        df_to_save = edited_df.copy()
                        df_to_save["Open Date"] = df_to_save["Open Date"].apply(parse_any_date)
                        df_to_save["Resolved Date"] = df_to_save["Resolved Date"].apply(parse_any_date)

                        # Validate Resolved/Closed requires Resolved Date
                        bad = df_to_save[(df_to_save["Status"].isin(["Resolved", "Closed"])) & (df_to_save["Resolved Date"].isna())]
                        if len(bad) > 0:
                            st.error("Some rows are Resolved/Closed but missing Resolved Date. Please fill Resolved Date.")
                        else:
                            for _, r in df_to_save.iterrows():
                                row = r.to_dict()

                                # If owner empty but status active -> set owner to editor username
                                if (str(row.get("Status", "")) in {"New", "In Progress", "Blocked", "Reopened"}) and not str(row.get("Current Owner", "")).strip():
                                    row["Current Owner"] = username

                                upsert_defect(row, actor=username, is_create=False)

                            st.success(f"Saved changes • Updated by: **{username}**")
                            st.session_state.df = load_defects_df()
                            st.rerun()
                    except Exception as e:
                        st.error(f"Save failed: {e}")

        with c2:
            with st.popover("🗑️ Delete"):
                st.write("Delete by Defect ID (careful).")
                del_id = st.text_input("Defect ID", placeholder="e.g., SD-1-001")
                if st.button("Confirm delete"):
                    if not username:
                        st.error("Username is required (sidebar) to delete.")
                    elif del_id.strip():
                        delete_defect(del_id.strip())
                        st.success(f"Deleted **{del_id.strip()}**")
                        st.session_state.df = load_defects_df()
                        st.rerun()
                    else:
                        st.warning("Enter a Defect ID.")

        with c3:
            st.caption("Tip: Use sidebar filters for a clean, professional workflow (no multi-select chips).")


# =========================
# DASHBOARD TAB
# =========================
with tab_dashboard:
    st.markdown("#### Dashboard")

    df_stats = load_defects_df()
    if df_stats.empty:
        st.info("No data yet. Create defects to see trends.", icon="📊")
    else:
        # KPIs
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("New", int((df_stats["Status"] == "New").sum()))
        col2.metric("In Progress", int((df_stats["Status"] == "In Progress").sum()))
        col3.metric("Blocked", int((df_stats["Status"] == "Blocked").sum()))
        col4.metric("Closed", int((df_stats["Status"] == "Closed").sum()))
        col5.metric("P1 not closed", int(((df_stats["Priority"] == "P1 - Critical") & (df_stats["Status"] != "Closed")).sum()))

        st.write("")

        # Clean dataset for charts
        chart_df = df_stats.copy()
        chart_df["Open Date"] = chart_df["Open Date"].apply(parse_any_date)
        chart_df["Resolved Date"] = chart_df["Resolved Date"].apply(parse_any_date)
        chart_df["Age (days)"] = chart_df.apply(lambda r: compute_age_days(r["Open Date"], r["Resolved Date"], str(r["Status"])), axis=1)

        left, right = st.columns(2)

        with left:
            st.markdown("##### Open items by Module")
            open_df = chart_df[chart_df["Status"] != "Closed"].copy()
            if open_df.empty:
                st.info("No open items.")
            else:
                ch = (
                    alt.Chart(open_df)
                    .mark_bar()
                    .encode(
                        x=alt.X("Module:N", sort="-y"),
                        y=alt.Y("count():Q"),
                        color=alt.Color("Status:N"),
                        tooltip=["Module:N", "Status:N", "count():Q"],
                    )
                )
                st.altair_chart(ch, use_container_width=True, theme="streamlit")

        with right:
            st.markdown("##### Open items by Priority")
            open_df = chart_df[chart_df["Status"] != "Closed"].copy()
            if open_df.empty:
                st.info("No open items.")
            else:
                ch = (
                    alt.Chart(open_df)
                    .mark_bar()
                    .encode(
                        x=alt.X("Priority:N", sort=PRIORITIES),
                        y=alt.Y("count():Q"),
                        tooltip=["Priority:N", "count():Q"],
                    )
                )
                st.altair_chart(ch, use_container_width=True, theme="streamlit")

        st.write("")
        st.markdown("##### Aging (not closed)")
        open_df = chart_df[chart_df["Status"] != "Closed"].copy()
        if open_df.empty:
            st.info("No open items.")
        else:
            def bucket(age):
                if age is None:
                    return "Unknown"
                if age <= 2:
                    return "0–2"
                if age <= 7:
                    return "3–7"
                if age <= 14:
                    return "8–14"
                return "15+"

            open_df["Aging Bucket"] = open_df["Age (days)"].apply(bucket)

            ch = (
                alt.Chart(open_df)
                .mark_bar()
                .encode(
                    x=alt.X("Aging Bucket:N", sort=["0–2", "3–7", "8–14", "15+", "Unknown"]),
                    y=alt.Y("count():Q"),
                    color=alt.Color("Priority:N"),
                    tooltip=["Aging Bucket:N", "Priority:N", "count():Q"],
                )
            )
            st.altair_chart(ch, use_container_width=True, theme="streamlit")


# =========================
# EXPORT TAB
# =========================
with tab_export:
    st.markdown("#### Export")

    export_df = load_defects_df().copy()
    if export_df.empty:
        st.info("Nothing to export yet.", icon="⬇️")
    else:
        # Export-friendly dates
        export_df["Open Date"] = export_df["Open Date"].apply(lambda d: d.isoformat() if isinstance(d, dt.date) else "")
        export_df["Resolved Date"] = export_df["Resolved Date"].apply(lambda d: d.isoformat() if isinstance(d, dt.date) else "")
        csv_bytes = export_df.to_csv(index=False).encode("utf-8")

        st.download_button(
            "Download CSV",
            data=csv_bytes,
            file_name="defects_export.csv",
            mime="text/csv",
            type="primary",
        )
        st.caption("CSV keeps your Excel structure clean. If you want an Excel (.xlsx) export, tell me and I’ll add it.")


# =========================
# requirements.txt (minimum)
# streamlit
# pandas
# altair
# =========================
