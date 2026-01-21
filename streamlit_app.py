import os
import datetime as dt
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

# ... (Previous Branding & Engine code remains the same) ...

def load_status_history(defect_id):
    """Fetches the audit trail for a specific defect."""
    try:
        with get_engine().connect() as conn:
            df = pd.read_sql(
                text("SELECT * FROM public.defect_history WHERE defect_id = :id ORDER BY changed_at DESC"),
                conn, params={"id": int(defect_id)}
            )
            return df
    except:
        return pd.DataFrame()

@st.dialog("✏️ Modify Defect")
def edit_defect_dialog(record):
    with st.form("edit_form"):
        st.markdown(f"### ID: {record['id']}")
        new_title = st.text_input("Summary", value=record.get('defect_title', ''))
        c1, c2 = st.columns(2)
        
        # Get current index
        cur_status = record.get('status', 'New')
        s_idx = STATUSES.index(cur_status) if cur_status in STATUSES else 0
        new_status = c1.selectbox("Status", STATUSES, index=s_idx)
        new_pri = c2.selectbox("Priority", PRIORITIES, index=PRIORITIES.index(record.get('priority', 'P3 - Medium')))
        
        new_desc = st.text_area("Description", value=record.get('description', ''))
        
        col_save, col_cancel = st.columns(2)
        if col_save.form_submit_button("💾 Commit Changes", use_container_width=True):
            with get_engine().begin() as conn:
                # 1. Update the Main Record
                conn.execute(text("""
                    UPDATE public.defects SET defect_title=:t, status=:s, priority=:p, description=:d WHERE id=:id
                """), {"t": new_title, "s": new_status, "p": new_pri, "d": new_desc, "id": record['id']})
                
                # 2. LOG HISTORY: Only if status actually changed
                if new_status != cur_status:
                    conn.execute(text("""
                        INSERT INTO public.defect_history (defect_id, old_status, new_status, changed_by)
                        VALUES (:id, :old, :new, :user)
                    """), {"id": record['id'], "old": cur_status, "new": new_status, "user": record.get('reported_by', 'System')})
            
            st.cache_data.clear()
            st.session_state.editing_id = None
            st.success("Changes committed and history logged.")
            st.rerun()
            
        if col_cancel.form_submit_button("Cancel", use_container_width=True):
            st.session_state.editing_id = None
            st.rerun()

    # --- STATUS HISTORY SECTION (Inside Dialog, outside Form) ---
    st.divider()
    st.markdown("#### 🕒 Status Change History")
    history_df = load_status_history(record['id'])
    if not history_df.empty:
        st.dataframe(history_df[['old_status', 'new_status', 'changed_at']], use_container_width=True, hide_index=True)
    else:
        st.caption("No status changes recorded yet.")

# ... (Rest of the Main UI code remains the same) ...
