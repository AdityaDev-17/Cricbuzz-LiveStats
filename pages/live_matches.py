"""Live / recent matches from the Cricbuzz API with full scorecards."""

import pandas as pd
import streamlit as st

from utils.api_client import CricbuzzAPIError, CricbuzzClient

st.title("⚡ Live Matches")

LIST_ENDPOINTS = {
    "Live now": ("/matches/v1/live", "matches_live"),
    "Recent": ("/matches/v1/recent", "matches_recent"),
}


@st.cache_resource
def get_client() -> CricbuzzClient:
    return CricbuzzClient()


@st.cache_data(ttl=300, show_spinner="Fetching matches...")
def fetch_match_list(view: str) -> tuple[dict, str]:
    """Live view calls the API; Recent uses the cached file. Falls back to cache on error."""
    client = get_client()
    endpoint, cache_name = LIST_ENDPOINTS[view]
    if view == "Recent":
        return client.fetch(endpoint, cache_name, use_cache=True), "cached data"
    try:
        return client.fetch(endpoint, cache_name, use_cache=False), "live API"
    except CricbuzzAPIError as exc:
        return client.fetch(endpoint, cache_name, use_cache=True), f"cached data (API error: {exc})"


@st.cache_data(ttl=120, show_spinner="Loading scorecard...")
def fetch_scorecard(match_id: int, is_live: bool) -> dict:
    """Live matches get a fresh scorecard; completed ones use the cache."""
    client = get_client()
    endpoint, cache_name = f"/mcenter/v1/{match_id}/hscard", f"match_{match_id}_scorecard"
    try:
        return client.fetch(endpoint, cache_name, use_cache=not is_live)
    except CricbuzzAPIError:
        return client.fetch(endpoint, cache_name, use_cache=True)


def flatten_matches(data: dict) -> list[dict]:
    """typeMatches -> seriesMatches -> matches  ==>  flat list."""
    rows = []
    for type_block in data.get("typeMatches", []):
        for series_block in type_block.get("seriesMatches", []):
            wrapper = series_block.get("seriesAdWrapper")
            if not wrapper:
                continue
            for m in wrapper.get("matches", []):
                rows.append(
                    {
                        "category": type_block.get("matchType", "Other"),
                        "info": m.get("matchInfo", {}),
                        "score": m.get("matchScore", {}),
                    }
                )
    return rows


def score_text(team_score: dict | None) -> str:
    """{'inngs1': {...}} -> '225/4 (20)'. Converts Cricbuzz '15.6' to '16'."""
    parts = []
    for key in ("inngs1", "inngs2"):
        inn = (team_score or {}).get(key)
        if inn:
            overs = float(inn.get("overs", 0))
            whole, balls = int(overs), round((overs - int(overs)) * 10)
            overs_txt = str(whole + 1) if balls == 6 else (f"{whole}.{balls}" if balls else str(whole))
            parts.append(f"{inn.get('runs', 0)}/{inn.get('wickets', 0)} ({overs_txt})")
    return " & ".join(parts) or "Yet to bat"


def batting_table(batsmen: list[dict]) -> pd.DataFrame:
    rows = []
    for b in batsmen:
        if b.get("balls", 0) == 0 and not b.get("outdec"):
            continue  # did not bat
        tags = (" (c)" if b.get("iscaptain") else "") + (" (wk)" if b.get("iskeeper") else "")
        rows.append(
            {
                "Batter": b.get("name", "") + tags,
                "Dismissal": b.get("outdec") or "not out",
                "R": b.get("runs", 0),
                "B": b.get("balls", 0),
                "4s": b.get("fours", 0),
                "6s": b.get("sixes", 0),
                "SR": b.get("strkrate", ""),
            }
        )
    return pd.DataFrame(rows)


def bowling_table(bowlers: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Bowler": b.get("name", ""),
                "O": b.get("overs", ""),
                "M": b.get("maidens", 0),
                "R": b.get("runs", 0),
                "W": b.get("wickets", 0),
                "Econ": b.get("economy", ""),
            }
            for b in bowlers
        ]
    )


# ---------------- Controls ----------------
c1, c2, c3 = st.columns([2, 3, 1])
view = c1.radio("Show", list(LIST_ENDPOINTS), horizontal=True)
if c3.button("🔄 Refresh"):
    fetch_match_list.clear()
    fetch_scorecard.clear()
    st.rerun()

try:
    data, source = fetch_match_list(view)
except CricbuzzAPIError as exc:
    st.error(f"Could not load matches and no cached copy exists: {exc}")
    st.stop()

matches = flatten_matches(data)
categories = sorted({m["category"] for m in matches})
chosen = c2.multiselect(
    "Category", categories, default=[c for c in categories if c == "International"] or categories
)
matches = [m for m in matches if m["category"] in chosen]
st.caption(f"Source: {source} · API quota remaining: {get_client().quota_remaining}")

if not matches:
    st.info("No matches for this selection. Try **Recent** or another category.")
    st.stop()

# ---------------- Match selector ----------------
labels = [
    f"{m['info'].get('team1', {}).get('teamSName', '?')} vs "
    f"{m['info'].get('team2', {}).get('teamSName', '?')} - "
    f"{m['info'].get('matchDesc', '')} | {m['info'].get('status', '')}"
    for m in matches
]
selected = matches[st.selectbox("Select a match", range(len(matches)), format_func=lambda i: labels[i])]
info, score = selected["info"], selected["score"]

# ---------------- Match header ----------------
st.subheader(f"{info.get('team1', {}).get('teamName')} vs {info.get('team2', {}).get('teamName')}")
st.markdown(
    f"**{info.get('seriesName', '')}** · {info.get('matchDesc', '')} · " f"{info.get('matchFormat', '')}"
)

m1, m2 = st.columns(2)
m1.metric(info.get("team1", {}).get("teamName", "Team 1"), score_text(score.get("team1Score")))
m2.metric(info.get("team2", {}).get("teamName", "Team 2"), score_text(score.get("team2Score")))

venue = info.get("venueInfo", {})
start = (
    pd.to_datetime(int(info["startDate"]), unit="ms", utc=True).tz_convert("Asia/Kolkata")
    if info.get("startDate")
    else None
)
d1, d2, d3 = st.columns(3)
d1.markdown(f"🏟️ **Venue**  \n{venue.get('ground', '-')}, {venue.get('city', '')}")
d2.markdown(f"📅 **Start**  \n{start.strftime('%d %b %Y, %I:%M %p IST') if start is not None else '-'}")
d3.markdown(f"📢 **Status**  \n{info.get('status', info.get('state', '-'))}")

# ---------------- Scorecard ----------------
st.divider()
if st.toggle("Show full scorecard"):
    is_live = info.get("state") not in ("Complete", "Abandon")
    try:
        sc = fetch_scorecard(info["matchId"], is_live)
    except CricbuzzAPIError as exc:
        st.error(f"Scorecard unavailable: {exc}")
        st.stop()

    innings = sc.get("scorecard", [])
    if not innings:
        st.info("Scorecard not available yet for this match.")
    else:
        tabs = st.tabs(
            [f"{inn.get('batteamsname', '?')} - Innings {inn.get('inningsid')}" for inn in innings]
        )
        for tab, inn in zip(tabs, innings):
            with tab:
                st.metric(
                    inn.get("batteamname", ""),
                    f"{inn.get('score', 0)}/{inn.get('wickets', 0)}",
                    f"{inn.get('overs', 0)} overs · RR {inn.get('runrate', '-')}",
                    delta_color="off",
                )
                st.markdown("**Batting**")
                st.dataframe(batting_table(inn.get("batsman", [])), hide_index=True, use_container_width=True)
                ex = inn.get("extras", {})
                st.caption(
                    f"Extras: {ex.get('total', 0)} (wd {ex.get('wides', 0)}, "
                    f"nb {ex.get('noballs', 0)}, b {ex.get('byes', 0)}, "
                    f"lb {ex.get('legbyes', 0)})"
                )
                st.markdown("**Bowling**")
                st.dataframe(bowling_table(inn.get("bowler", [])), hide_index=True, use_container_width=True)
