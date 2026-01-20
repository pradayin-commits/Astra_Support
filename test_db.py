import streamlit as st
from sqlalchemy import create_engine, text

st.write("Testing Supabase DB connection...")

engine = create_engine(
    st.secrets["SUPABASE_DATABASE_URL"],
    pool_pre_ping=True,
)

with engine.connect() as conn:
    st.success("Connected successfully!")
    st.write(conn.execute(text("select now()")).scalar())
