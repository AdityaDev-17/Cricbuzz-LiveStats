"""Top player stats - DB-driven leaderboards + Cricbuzz API top stats/rankings."""

import pandas as pd
import plotly.express as px
import streamlit as st

from utils.api_client import CricbuzzAPIError, CricbuzzClient
from utils.db_connection import DatabaseConnection

st.title("📊 Top Player Stats")

# ---------------- Filters ----------------
f1, f2, f3, f4 = st.columns([2, 2, 1, 1])
formats = f1.multiselect("Format", ["Test", "ODI", "T20I"], default=["Test", "ODI", "T20I"])
years = f2.slider("Years", 2022, 2026, (2022, 2026))
min_innings = f3.number_input("Min innings", 1, 50, 10, help="Qualification for averages / SR")
top_n = f4.number_input("Show top", 5, 50, 15)

if not formats:
    st.warning("Select at least one format.")
    st.stop()

PARAMS = {
    "formats": formats,
    "y1": years[0],
    "y2": years[1],
    "n": int(top_n),
    "min_inn": int(min_innings),
    "min_balls": int(min_innings) * 30,
}
MATCH_FILTER = """m.format = ANY(:formats)
    AND EXTRACT(YEAR FROM m.match_date) BETWEEN :y1 AND :y2"""


@st.cache_data(ttl=600, show_spinner=False)
def run(sql: str, params: dict) -> pd.DataFrame:
    return DatabaseConnection.run_query(sql, params)


def leaderboard(df: pd.DataFrame, value_col: str, label: str, ascending: bool = False) -> None:
    """Top-10 bar chart + full table."""
    if df.empty:
        st.info("No data for these filters.")
        return
    chart_df = df.head(10).sort_values(value_col, ascending=not ascending)
    fig = px.bar(
        chart_df,
        x=value_col,
        y="player",
        orientation="h",
        text=value_col,
        labels={value_col: label, "player": ""},
        height=380,
    )
    fig.update_layout(margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(df, hide_index=True, use_container_width=True)


# ---------------- SQL ----------------
BATTING_SQL = f"""
    SELECT p.full_name AS player, p.country,
           COUNT(DISTINCT b.match_id) AS matches, COUNT(*) AS innings,
           SUM(b.runs) AS runs, MAX(b.runs) AS highest,
           ROUND(CAST(SUM(b.runs) AS NUMERIC) / NULLIF(SUM(CASE WHEN b.is_out THEN 1 ELSE 0 END), 0), 2) AS average,
           ROUND(SUM(b.runs) * 100.0 / NULLIF(SUM(b.balls), 0), 2) AS strike_rate,
           SUM(CASE WHEN b.runs >= 100 THEN 1 ELSE 0 END) AS hundreds,
           SUM(CASE WHEN b.runs BETWEEN 50 AND 99 THEN 1 ELSE 0 END) AS fifties,
           SUM(b.sixes) AS sixes
    FROM batting_innings b
    JOIN matches m ON m.match_id = b.match_id
    JOIN players p ON p.player_id = b.player_id
    WHERE {MATCH_FILTER}
    GROUP BY p.player_id, p.full_name, p.country
    HAVING COUNT(*) >= :min_inn_having
    ORDER BY {{order}} LIMIT :n
"""

BOWLING_SQL = f"""
    SELECT p.full_name AS player, p.country,
           COUNT(DISTINCT w.match_id) AS matches, SUM(w.wickets) AS wickets,
           SUM(w.balls_bowled) AS balls, SUM(w.runs_conceded) AS runs,
           ROUND(CAST(SUM(w.runs_conceded) AS NUMERIC) / NULLIF(SUM(w.wickets), 0), 2) AS average,
           ROUND(SUM(w.runs_conceded) * 6.0 / NULLIF(SUM(w.balls_bowled), 0), 2) AS economy,
           SUM(CASE WHEN w.wickets >= 5 THEN 1 ELSE 0 END) AS five_wkts
    FROM bowling_innings w
    JOIN matches m ON m.match_id = w.match_id
    JOIN players p ON p.player_id = w.player_id
    WHERE {MATCH_FILTER}
    GROUP BY p.player_id, p.full_name, p.country
    HAVING SUM(w.balls_bowled) >= :min_balls_having
    ORDER BY {{order}} LIMIT :n
"""

HIGHEST_SCORES_SQL = f"""
    SELECT p.full_name AS player, p.country, b.runs, b.balls, b.strike_rate,
           CASE WHEN b.is_out THEN 'out' ELSE 'not out' END AS status,
           opp.team_name AS opponent, m.format, m.match_date
    FROM batting_innings b
    JOIN matches m ON m.match_id = b.match_id
    JOIN players p ON p.player_id = b.player_id
    JOIN teams opp ON opp.team_id = CASE WHEN m.team1_id = b.team_id THEN m.team2_id ELSE m.team1_id END
    WHERE {MATCH_FILTER}
    ORDER BY b.runs DESC, b.balls ASC LIMIT :n
"""

BEST_FIGURES_SQL = f"""
    SELECT p.full_name AS player, p.country,
           w.wickets || '/' || w.runs_conceded AS figures, w.wickets, w.runs_conceded,
           w.overs, opp.team_name AS opponent, m.format, m.match_date
    FROM bowling_innings w
    JOIN matches m ON m.match_id = w.match_id
    JOIN players p ON p.player_id = w.player_id
    JOIN teams opp ON opp.team_id = CASE WHEN m.team1_id = w.team_id THEN m.team2_id ELSE m.team1_id END
    WHERE {MATCH_FILTER}
    ORDER BY w.wickets DESC, w.runs_conceded ASC LIMIT :n
"""

FIELDING_SQL = f"""
    SELECT p.full_name AS player, p.country, COUNT(DISTINCT f.match_id) AS matches,
           SUM(f.catches) AS catches, SUM(f.stumpings) AS stumpings, SUM(f.run_outs) AS run_outs,
           SUM(f.catches) + SUM(f.stumpings) + SUM(f.run_outs) AS dismissals
    FROM fielding f
    JOIN matches m ON m.match_id = f.match_id
    JOIN players p ON p.player_id = f.player_id
    WHERE {MATCH_FILTER}
    GROUP BY p.player_id, p.full_name, p.country
    ORDER BY dismissals DESC LIMIT :n
"""


def batting(order: str, qualified: bool) -> pd.DataFrame:
    params = {**PARAMS, "min_inn_having": PARAMS["min_inn"] if qualified else 1}
    return run(BATTING_SQL.format(order=order), params)


def bowling(order: str, qualified: bool) -> pd.DataFrame:
    params = {**PARAMS, "min_balls_having": PARAMS["min_balls"] if qualified else 1}
    return run(BOWLING_SQL.format(order=order), params)


# ---------------- Tabs ----------------
tab_bat, tab_bowl, tab_field, tab_api = st.tabs(
    ["🏏 Batting", "🎯 Bowling", "🧤 Fielding", "🌐 Cricbuzz API"]
)

try:
    with tab_bat:
        board = st.radio(
            "Leaderboard",
            [
                "Most runs",
                "Highest scores",
                "Best average",
                "Best strike rate",
                "Most hundreds",
                "Most sixes",
            ],
            horizontal=True,
            key="bat_board",
        )
        if board == "Most runs":
            leaderboard(batting("runs DESC", False), "runs", "Runs")
        elif board == "Highest scores":
            leaderboard(run(HIGHEST_SCORES_SQL, PARAMS), "runs", "Runs")
        elif board == "Best average":
            st.caption(f"Qualification: at least {PARAMS['min_inn']} innings")
            leaderboard(batting("average DESC NULLS LAST", True), "average", "Average")
        elif board == "Best strike rate":
            st.caption(f"Qualification: at least {PARAMS['min_inn']} innings")
            leaderboard(batting("strike_rate DESC NULLS LAST", True), "strike_rate", "Strike rate")
        elif board == "Most hundreds":
            leaderboard(batting("hundreds DESC, runs DESC", False), "hundreds", "Hundreds")
        else:
            leaderboard(batting("sixes DESC", False), "sixes", "Sixes")

    with tab_bowl:
        board = st.radio(
            "Leaderboard",
            ["Most wickets", "Best figures", "Best economy", "Best average", "Most 5-wicket hauls"],
            horizontal=True,
            key="bowl_board",
        )
        if board == "Most wickets":
            leaderboard(bowling("wickets DESC", False), "wickets", "Wickets")
        elif board == "Best figures":
            leaderboard(run(BEST_FIGURES_SQL, PARAMS), "wickets", "Wickets")
        elif board == "Best economy":
            st.caption(f"Qualification: at least {PARAMS['min_balls']} balls bowled")
            leaderboard(bowling("economy ASC NULLS LAST", True), "economy", "Economy", ascending=True)
        elif board == "Best average":
            st.caption(f"Qualification: at least {PARAMS['min_balls']} balls bowled")
            leaderboard(bowling("average ASC NULLS LAST", True), "average", "Average", ascending=True)
        else:
            leaderboard(bowling("five_wkts DESC, wickets DESC", False), "five_wkts", "5-wicket hauls")

    with tab_field:
        leaderboard(run(FIELDING_SQL, PARAMS), "dismissals", "Fielding dismissals")
except Exception as exc:
    st.error(f"Database query failed: {exc}")


# ---------------- Cricbuzz API tab ----------------
@st.cache_resource
def get_client() -> CricbuzzClient:
    return CricbuzzClient()


def api_to_df(data: dict) -> pd.DataFrame | None:
    """Handle the 'headers + values' grid and plain list responses."""
    if isinstance(data.get("headers"), list) and isinstance(data.get("values"), list):
        rows = [r.get("values", []) for r in data["values"]]
        if not rows:
            return pd.DataFrame()
        headers, width = data["headers"], len(rows[0])
        if len(headers) == width:
            return pd.DataFrame(rows, columns=headers)
        if len(headers) == width - 1:  # leading id column
            return pd.DataFrame(rows, columns=["id"] + headers).drop(columns="id")
        return pd.DataFrame(rows)
    for key in ("rank", "players", "values"):
        if isinstance(data.get(key), list):
            return pd.json_normalize(data[key])
    return None


with tab_api:
    st.caption(
        "Fetched from the Cricbuzz API. Each new selection costs 1 API call once, "
        "then it is served from the local cache."
    )
    a1, a2 = st.columns(2)

    with a1:
        st.subheader("Top stats")
        stat = st.selectbox(
            "Stat type",
            [
                "mostRuns",
                "mostWickets",
                "highestScore",
                "highestAvg",
                "mostHundreds",
                "mostSixes",
                "lowestEcon",
            ],
        )
        try:
            data = get_client().fetch("/stats/v1/topstats/0", f"topstats_{stat}", params={"statsType": stat})
            df = api_to_df(data)
            if df is not None:
                st.dataframe(df, hide_index=True, use_container_width=True)
            else:
                st.json(data, expanded=False)
        except CricbuzzAPIError as exc:
            st.error(str(exc))

    with a2:
        st.subheader("ICC rankings")
        r1, r2 = st.columns(2)
        category = r1.selectbox("Category", ["batsmen", "bowlers", "allrounders"])
        fmt = r2.selectbox("Format", ["odi", "test", "t20"])
        try:
            data = get_client().fetch(
                "/stats/v1/rankings/" + category, f"rankings_{fmt}_{category}", params={"formatType": fmt}
            )
            df = api_to_df(data)
            if df is not None:
                keep = [
                    c for c in ["rank", "name", "country", "rating", "points", "trend"] if c in df.columns
                ]
                st.dataframe(df[keep] if keep else df, hide_index=True, use_container_width=True)
            else:
                st.json(data, expanded=False)
        except CricbuzzAPIError as exc:
            st.error(str(exc))
