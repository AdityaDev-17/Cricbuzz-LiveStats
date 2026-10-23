# 🏏 Cricbuzz LiveStats: Real-Time Cricket Insights & SQL-Based Analytics

A multi-page Streamlit dashboard that combines **live data from the Cricbuzz API** with a
**PostgreSQL database** of ~1,000 international matches, delivering live scorecards, player
leaderboards, 25 SQL analytics queries, and full CRUD operations.

**Domain:** Sports Analytics · **Stack:** Python · SQL · Streamlit · JSON · REST API

---

## Features

| Page | Description |
|---|---|
| 🏠 **Home** | Project overview, live database summary, structure |
| ⚡ **Live Matches** | Live/recent matches from the Cricbuzz API with full batting & bowling scorecards |
| 📊 **Top Player Stats** | Filterable leaderboards (runs, averages, strike rate, wickets, economy, fielding) + Cricbuzz API top stats and ICC rankings |
| 🔍 **SQL Analytics** | 25 practice queries (beginner → advanced) with results, timing, CSV export, and a read-only custom SQL runner |
| 🛠️ **CRUD Operations** | Create, read, update, delete players and matches via validated forms |

## Tech Stack
- **Python 3.11**: requests, pandas
- **Streamlit**: multi-page web app (`st.navigation`)
- **PostgreSQL** + **SQLAlchemy 2.0** + psycopg2
- **Cricbuzz Cricket API** (RapidAPI): live data
- **Cricsheet**: open ball-by-ball data for historical scorecards
- **Plotly**: charts

## Data Architecture

    Cricbuzz API ──► api_client.py (on-disk JSON cache) ──► cricbuzz_loader.py ─┐
                                                                                ├──► PostgreSQL ──► Streamlit pages
    Cricsheet JSON ──► cricsheet_loader.py (ball-by-ball → scorecards) ─────────┘

| Source | Provides |
|---|---|
| Cricbuzz API | Live/recent matches, scorecards, venues (country, capacity), player profiles, career stats per format, top stats, rankings |
| Cricsheet | Men's international matches between full-member nations since 2022 (Tests, ODIs, T20Is), aggregated from ball-by-ball data |

### Database Schema (9 tables)
`teams`, `venues`, `players`, `series`, `matches`, `batting_innings`, `bowling_innings`,
`fielding`, `player_career_stats`. See `sql/schema.sql`; sample rows are in `sql/sample_data/`.

Key design points:
- Surrogate primary keys plus separate `cricbuzz_*_id` / `cricsheet_*_id` columns, so both sources share one schema
- `ON DELETE CASCADE` on innings and fielding tables, so CRUD deletes stay consistent
- `CHECK` constraints on format, toss decision, victory type and wickets
- Indexes on match date, format, venue and player IDs

---

## Setup

### 1. Clone and install
```powershell
git clone https://github.com/AdityaDev-17/cricbuzz-livestats.git
cd cricbuzz-livestats
uv venv .venv
.\.venv\Scripts\Activate.ps1
uv pip install -r requirements.txt
```

### 2. Configure secrets
Copy `.env.example` to `.env` and fill in the values:
cricbuzz_livestats/
├── app.py # Streamlit entry point + navigation (the brief’s “main.py”)
├── requirements.txt
├── run_schema.py # Creates tables from sql/schema.sql
├── load_cricbuzz.py # Loads Cricbuzz matches, scorecards, venues, profiles
├── load_india_profiles.py # Profiles Indian players (for Q1)
├── load_cricsheet.py # Loads Cricsheet history
├── export_sample_data.py # Exports sample rows to sql/sample_data/
├── test_parsers.py # Parser sanity checks
├── pages/
│ ├── home.py
│ ├── live_matches.py
│ ├── top_stats.py
│ ├── sql_queries.py
│ └── crud_operations.py
├── utils/
│ ├── db_connection.py # Centralized SQLAlchemy connection
│ ├── api_client.py # Cricbuzz client with JSON caching
│ ├── parsers.py # Toss/result/dismissal/overs parsing
│ ├── cricbuzz_loader.py
│ ├── cricsheet_loader.py
│ └── queries.py # The 25 SQL queries
├── sql/
│ ├── schema.sql
│ └── sample_data/
└── notebooks/data_fetching.ipynb


---

## SQL Analytics: 25 Queries
- **Beginner (1–8):** SELECT, WHERE, GROUP BY, ORDER BY
- **Intermediate (9–16):** JOINs, subqueries, conditional aggregation, self-joins
- **Advanced (17–25):** CTEs, window functions (`RANK`, `ROW_NUMBER`, `LAG`), `GROUPING SETS`,
  `STDDEV_SAMP`, `DATE_TRUNC`, `FILTER` clauses

### Interpretation notes
| Query | Interpretation |
|---|---|
| Q3, Q9 | Career figures from `player_career_stats` (Cricbuzz-profiled players) |
| Q13, Q24 | Partnership = runs of consecutive batting positions, as defined in the brief |
| Q15 | Players with at least 5 close matches |
| Q19 | Innings with 10+ balls faced, since 2022, minimum 10 innings |
| Q21 | Bowling formula read as `(50 − bowling_avg) × 0.5`; bowling points only when wickets > 0; minimum 10 matches per format |
| Q22 | Batting-first team derived from the toss; venue variety shown as a count of venues |
| Q23 | Form from the last-5 average (Excellent ≥ 50 with 3+ fifties, Good ≥ 35, Average ≥ 20); consistency = average ÷ standard deviation |
| Q25 | Improving/declining = a change of more than 10% versus the previous quarter; career phase by majority trend |

---

## Engineering Notes
- **API quota protection:** every Cricbuzz response is cached in `data/raw/`. Re-runs and page
  reloads read from disk, and the live page caches responses for 2–5 minutes.
- **Offline fallback:** if the API fails or the quota runs out, pages fall back to cached responses.
- **Idempotent loaders:** upserts (`ON CONFLICT`), one transaction per match, and already-loaded
  matches are skipped.
- **Security:** credentials live in `.env` (git-ignored), all SQL is parameterized, and the custom
  SQL runner uses a `READ ONLY` transaction with a 15 s timeout.

## Known Limitations
- The free API tier allows ~200 requests per month, so only ~30 players have full Cricbuzz profiles
  (role, styles, career stats). Cricsheet-only players have no role data.
- Cricsheet uses initial-style names ("V Kohli"). These are linked to Cricbuzz profiles where the
  country, surname and first initial match uniquely; the rest remain separate rows.
- Venue country for Cricsheet venues is inferred from bilateral tour names. A few neutral ICC-event
  venues have no country.
- Capacities for 7 major stadiums are seeded from approximate public figures, because Cricsheet
  has no capacity data.

---

## Author
**Aditya Singh** · [GitHub](https://github.com/AdityaDev-17) · 