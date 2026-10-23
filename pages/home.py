"""Home page - project overview, live DB summary, navigation guide."""

import streamlit as st

from utils.db_connection import DatabaseConnection

st.title("🏏 Cricbuzz LiveStats")
st.caption("Real-Time Cricket Insights & SQL-Based Analytics")


@st.cache_data(ttl=600)
def db_summary():
    """Row counts for the headline metrics."""
    return DatabaseConnection.run_query("""
        SELECT (SELECT COUNT(*) FROM matches) AS matches,
               (SELECT COUNT(*) FROM players) AS players,
               (SELECT COUNT(*) FROM venues)  AS venues,
               (SELECT COUNT(*) FROM series)  AS series,
               (SELECT COUNT(*) FROM batting_innings) +
               (SELECT COUNT(*) FROM bowling_innings) AS innings_records
    """).iloc[0]


try:
    s = db_summary()
    cols = st.columns(5)
    for col, (label, value) in zip(
        cols,
        [
            ("Matches", s["matches"]),
            ("Players", s["players"]),
            ("Venues", s["venues"]),
            ("Series", s["series"]),
            ("Innings records", s["innings_records"]),
        ],
    ):
        col.metric(label, f"{int(value):,}")
except Exception as exc:
    st.error(f"Database not reachable: {exc}")

st.divider()

left, right = st.columns([3, 2])
with left:
    st.subheader("About the project")
    st.markdown("""
A cricket analytics dashboard that combines **live data from the Cricbuzz API**
with a **PostgreSQL database** of historical scorecards.

- ⚡ Real-time match updates and scorecards
- 📊 Top batting and bowling statistics
- 🔍 25 SQL analytics queries (beginner → advanced)
- 🛠️ Full CRUD operations on player and match data
""")

    st.subheader("Pages")
    st.markdown("""
| Page | What it does |
|---|---|
| ⚡ **Live Matches** | Live and recent matches from the Cricbuzz API with full scorecards |
| 📊 **Top Player Stats** | Leaderboards for runs, wickets, averages and strike rates |
| 🔍 **SQL Analytics** | Run the 25 practice queries and see results as tables |
| 🛠️ **CRUD Operations** | Add, view, update and delete player and match records |
""")

with right:
    st.subheader("Tech stack")
    st.markdown("""
- **Python** - requests, pandas
- **Streamlit** - multi-page web app
- **PostgreSQL** + **SQLAlchemy** - database
- **Cricbuzz API** (RapidAPI) - live data
- **Cricsheet** - historical scorecards (2022+)
- **Plotly** - charts
""")

    st.subheader("Data sources")
    st.markdown("""
- **Cricbuzz API**: live/recent matches, scorecards, player profiles,
  career stats, venues. Responses are cached locally to respect the
  free-tier quota.
- **Cricsheet**: ball-by-ball data for men's internationals between
  full-member nations since 2022, aggregated into scorecards.
""")

st.subheader("Project structure")
st.code(
    """
cricbuzz_livestats/
├── app.py                    # Streamlit entry point + navigation
├── requirements.txt
├── README.md
├── run_schema.py             # Creates DB tables
├── load_cricbuzz.py          # Loads Cricbuzz API data
├── load_cricsheet.py         # Loads Cricsheet history
├── pages/
│   ├── home.py
│   ├── live_matches.py
│   ├── top_stats.py
│   ├── sql_queries.py
│   └── crud_operations.py
├── utils/
│   ├── db_connection.py      # SQLAlchemy connection
│   ├── api_client.py         # Cached Cricbuzz client
│   ├── parsers.py            # Text/JSON parsing helpers
│   ├── cricbuzz_loader.py
│   └── cricsheet_loader.py
├── sql/schema.sql
└── notebooks/data_fetching.ipynb
""",
    language="text",
)
