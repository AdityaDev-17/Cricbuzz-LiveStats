"""Cricbuzz LiveStats - main Streamlit entry point."""

import streamlit as st

st.set_page_config(page_title="Cricbuzz LiveStats", page_icon="🏏", layout="wide")

pages = [
    st.Page("pages/home.py", title="Home", icon="🏠", default=True),
    st.Page("pages/live_matches.py", title="Live Matches", icon="⚡"),
    st.Page("pages/top_stats.py", title="Top Player Stats", icon="📊"),
    st.Page("pages/sql_queries.py", title="SQL Analytics", icon="🔍"),
    st.Page("pages/crud_operations.py", title="CRUD Operations", icon="🛠️"),
]
st.navigation(pages).run()
