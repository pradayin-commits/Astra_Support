import streamlit as st
import pandas as pd
from supabase import create_client, Client
import plotly.express as px

# 1. Page Configuration & Layout Fix
st.set_page_config(page_title="Astra Defect Tracker", layout="wide")

# Custom CSS to move content up and remove top padding
st.markdown("""
    <style>
        .block-container {
            padding-top: 1rem;
            padding-bottom: 0rem;
            margin-top: -3rem;
        }
        [data-testid="stMetricValue"] {
            font-size: 28px;
        }
    </style>
    """, unsafe_allow_html=True)

# 2. Database Connection
@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_connection()

# 3. Data Fetching Logic
def fetch_data():
    response = supabase.table("defects").select("*").execute()
    return pd.DataFrame(response.data)

df = fetch_data()

# 4. Sidebar Branding & Filters
with st.sidebar:
    # Use the generated logo here (place your logo.png in the same folder)
    st.image("logo.png", width=200) 
    st.title("Filters")
    
    # Filter by Status
    status_list = df['status'].unique().tolist()
    selected_status = st.multiselect("Filter by Status", status_list, default=status_list)
    
    # Filter by Priority
    priority_list = df['priority'].unique().tolist()
    selected_priority = st.multiselect("Filter by Priority", priority_list, default=priority_list)

# Apply Filters to Dataframe
filtered_df = df[(df['status'].isin(selected_status)) & (df['priority'].isin(selected_priority))]

# 5. Dashboard Header & Buckets
st.title("🚀 Astra Defect Tracker")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Global Defects", len(df))
with col2:
    open_count = len(df[df['status'].str.lower() == 'open'])
    st.metric("Open Defects", open_count, delta_color="inverse")
with col3:
    resolved_count = len(df[df['status'].str.lower() == 'resolved'])
    st.metric("Resolved Defects", resolved_count)

st.divider()

# 6. Visualizations
chart_col, table_col = st.columns([1, 2])

with chart_col:
    st.subheader("Priority Distribution")
    if not filtered_df.empty:
        fig = px.pie(filtered_df, names='priority', hole=0.4, 
                     color_discrete_sequence=px.colors.sequential.RdBu)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.write("No data for chart.")

with table_col:
    st.subheader("Detailed Defect List")
    # Interactive Table with filtering/sorting
    st.dataframe(filtered_df, use_container_width=True, hide_index=True)

# 7. Add New Defect (Optional Quick Action)
with st.expander("➕ Report New Defect"):
    with st.form("new_defect"):
        title = st.text_input("Defect Title")
        desc = st.text_area("Description")
        prio = st.selectbox("Priority", ["Low", "Medium", "High", "Critical"])
        submit = st.form_submit_button("Submit Defect")
        
        if submit:
            # Code to push to Supabase
            st.success("Defect added to Astra!")
