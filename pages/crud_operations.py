"""CRUD operations - create, read, update, delete players and matches."""

from datetime import date

import pandas as pd
import streamlit as st
from sqlalchemy.exc import IntegrityError

from utils.db_connection import DatabaseConnection as DB

st.title("🛠️ CRUD Operations")
st.caption("Every write is a parameterized query inside a transaction.")

ROLES = ["Batsman", "Bowler", "Batting Allrounder", "Bowling Allrounder", "WK-Batsman"]
FORMATS = ["Test", "ODI", "T20I"]
VICTORY_TYPES = ["runs", "wickets", "innings", "tie", "draw", "no result"]
SIDES = ["Team 1", "Team 2", "None"]

if "flash" in st.session_state:
    kind, msg = st.session_state.pop("flash")
    getattr(st, kind)(msg)


# ================= Shared helpers =================
@st.cache_data(ttl=300)
def teams() -> pd.DataFrame:
    return DB.run_query("SELECT team_id, team_name FROM teams ORDER BY team_name")


@st.cache_data(ttl=300)
def venues() -> pd.DataFrame:
    return DB.run_query("""
        SELECT venue_id, venue_name || COALESCE(', ' || city, '') AS label
        FROM venues ORDER BY venue_name
    """)


def clean(row: pd.Series) -> dict:
    """pandas row -> dict with NaN/NaT converted to None."""
    return {k: (None if pd.isna(v) else v) for k, v in row.items()}


def write(sql: str, params: dict, success: str) -> None:
    """Execute a write; show a friendly error or flash success and refresh."""
    ok = False
    try:
        DB.execute(sql, params)
        ok = True
    except IntegrityError as exc:
        st.error(f"Rejected by a database constraint: {exc.orig}")
    except Exception as exc:
        st.error(f"Database error: {exc}")
    if ok:
        teams.clear()
        venues.clear()
        st.session_state["flash"] = ("success", success)
        st.rerun()


# ================= PLAYERS =================
def pick_player(key: str) -> int | None:
    q = st.text_input("Search player by name", key=f"{key}_q", placeholder="e.g. Kohli")
    if not q.strip():
        st.caption("Type part of a name to search.")
        return None
    df = DB.run_query(
        """
        SELECT player_id, full_name, country, playing_role FROM players
        WHERE full_name ILIKE :q ORDER BY full_name LIMIT 50
    """,
        {"q": f"%{q.strip()}%"},
    )
    if df.empty:
        st.info("No players found.")
        return None
    labels = {
        int(r.player_id): f"{r.full_name} ({r.country or '-'}) · id {r.player_id}" for r in df.itertuples()
    }
    return st.selectbox("Select player", list(labels), format_func=labels.get, key=f"{key}_sel")


def players_read() -> None:
    c1, c2, c3 = st.columns(3)
    q = c1.text_input("Name contains", key="pr_q")
    country = c2.selectbox("Country", ["All"] + teams()["team_name"].tolist(), key="pr_c")
    role = c3.selectbox("Role", ["All", "Not set"] + ROLES, key="pr_r")
    df = DB.run_query(
        """
        SELECT player_id, full_name, country, playing_role, batting_style, bowling_style,
               cricbuzz_player_id, cricsheet_player_id
        FROM players
        WHERE full_name ILIKE :q
          AND (:country = 'All' OR country = :country)
          AND (:role = 'All' OR (:role = 'Not set' AND playing_role IS NULL) OR playing_role = :role)
        ORDER BY full_name LIMIT 500
    """,
        {"q": f"%{q.strip()}%", "country": country, "role": role},
    )
    st.caption(f"{len(df)} players (max 500 shown)")
    st.dataframe(df, hide_index=True, use_container_width=True)


def players_create() -> None:
    with st.form("player_create", clear_on_submit=True):
        name = st.text_input("Full name *")
        c1, c2 = st.columns(2)
        country = c1.selectbox("Country *", teams()["team_name"].tolist())
        role = c2.selectbox("Playing role", ROLES)
        bat = c1.selectbox("Batting style", ["Right Handed Bat", "Left Handed Bat"])
        bowl = c2.text_input("Bowling style", placeholder="e.g. Right-arm offbreak")
        submitted = st.form_submit_button("➕ Add player", type="primary")
    if submitted:
        if not name.strip():
            st.error("Full name is required.")
            return
        write(
            """
            INSERT INTO players (full_name, country, playing_role, batting_style, bowling_style)
            VALUES (:n, :c, :r, :b, :w)
        """,
            {"n": name.strip(), "c": country, "r": role, "b": bat, "w": bowl.strip() or None},
            f"Added player '{name.strip()}'.",
        )


def players_update() -> None:
    pid = pick_player("pu")
    if pid is None:
        return
    row = clean(DB.run_query("SELECT * FROM players WHERE player_id = :id", {"id": pid}).iloc[0])
    countries = ["Not set"] + teams()["team_name"].tolist()
    roles = (
        ["Not set"]
        + ROLES
        + ([row["playing_role"]] if row["playing_role"] and row["playing_role"] not in ROLES else [])
    )
    with st.form(f"player_update_{pid}"):
        name = st.text_input("Full name *", row["full_name"], key=f"pu_name_{pid}")
        c1, c2 = st.columns(2)
        country = c1.selectbox(
            "Country",
            countries,
            key=f"pu_country_{pid}",
            index=countries.index(row["country"]) if row["country"] in countries else 0,
        )
        role = c2.selectbox(
            "Playing role",
            roles,
            key=f"pu_role_{pid}",
            index=roles.index(row["playing_role"]) if row["playing_role"] in roles else 0,
        )
        bat = c1.text_input("Batting style", row["batting_style"] or "", key=f"pu_bat_{pid}")
        bowl = c2.text_input("Bowling style", row["bowling_style"] or "", key=f"pu_bowl_{pid}")
        submitted = st.form_submit_button("💾 Save changes", type="primary")
    if submitted:
        if not name.strip():
            st.error("Full name is required.")
            return
        write(
            """
            UPDATE players SET full_name = :n, country = :c, playing_role = :r,
                   batting_style = :b, bowling_style = :w
            WHERE player_id = :id
        """,
            {
                "n": name.strip(),
                "c": None if country == "Not set" else country,
                "r": None if role == "Not set" else role,
                "b": bat.strip() or None,
                "w": bowl.strip() or None,
                "id": pid,
            },
            f"Updated '{name.strip()}'.",
        )


def players_delete() -> None:
    pid = pick_player("pd")
    if pid is None:
        return
    c = DB.run_query(
        """
        SELECT (SELECT COUNT(*) FROM batting_innings WHERE player_id = :id) AS batting,
               (SELECT COUNT(*) FROM bowling_innings WHERE player_id = :id) AS bowling,
               (SELECT COUNT(*) FROM fielding WHERE player_id = :id) AS fielding,
               (SELECT COUNT(*) FROM player_career_stats WHERE player_id = :id) AS career
    """,
        {"id": pid},
    ).iloc[0]
    st.warning(
        f"This also deletes {c.batting} batting, {c.bowling} bowling, {c.fielding} fielding "
        f"and {c.career} career-stat rows (ON DELETE CASCADE)."
    )
    confirm = st.checkbox("I understand - delete this player", key=f"pd_confirm_{pid}")
    if st.button("🗑️ Delete player", type="primary", disabled=not confirm, key=f"pd_btn_{pid}"):
        write("DELETE FROM players WHERE player_id = :id", {"id": pid}, "Player deleted.")


# ================= MATCHES =================
MATCH_LIST_SQL = """
    SELECT m.match_id, m.match_date, m.format, m.match_desc,
           t1.team_name AS team1, t2.team_name AS team2, w.team_name AS winner,
           m.victory_margin, m.victory_type, v.venue_name, m.source
    FROM matches m
    JOIN teams t1 ON t1.team_id = m.team1_id
    JOIN teams t2 ON t2.team_id = m.team2_id
    LEFT JOIN teams w ON w.team_id = m.winner_id
    LEFT JOIN venues v ON v.venue_id = m.venue_id
    WHERE (:team = 'All' OR :team IN (t1.team_name, t2.team_name))
      AND (:fmt = 'All' OR m.format = :fmt)
      AND (:source = 'All' OR m.source = :source)
    ORDER BY m.match_date DESC, m.match_id DESC
"""


def match_filters(key: str, with_source: bool = True) -> dict:
    c1, c2, c3 = st.columns(3)
    team = c1.selectbox("Team", ["All"] + teams()["team_name"].tolist(), key=f"{key}_team")
    fmt = c2.selectbox("Format", ["All"] + FORMATS, key=f"{key}_fmt")
    source = (
        c3.selectbox("Source", ["All", "cricbuzz", "cricsheet", "manual"], key=f"{key}_src")
        if with_source
        else "All"
    )
    return {"team": team, "fmt": fmt, "source": source}


def matches_read() -> None:
    df = DB.run_query(MATCH_LIST_SQL + " LIMIT 500", match_filters("mr"))
    st.caption(f"{len(df)} matches (max 500 shown)")
    st.dataframe(df, hide_index=True, use_container_width=True)


def pick_match(key: str) -> int | None:
    df = DB.run_query(MATCH_LIST_SQL + " LIMIT 100", match_filters(key))
    if df.empty:
        st.info("No matches for these filters.")
        return None
    labels = {
        int(r.match_id): f"{r.match_date} · {r.team1} vs {r.team2} · {r.format} · "
        f"{r.match_desc or ''} · id {r.match_id}"
        for r in df.itertuples()
    }
    return st.selectbox("Select match", list(labels), format_func=labels.get, key=f"{key}_sel")


def match_form(key: str, row: dict | None = None) -> dict | None:
    """Shared create/update form. Returns validated values on submit, else None."""
    row = row or {}
    t = teams()
    team_ids = [int(x) for x in t["team_id"]]
    team_name = dict(zip(team_ids, t["team_name"]))
    v = venues()
    venue_ids = [None] + [int(x) for x in v["venue_id"]]
    venue_label = dict(zip([int(x) for x in v["venue_id"]], v["label"]))

    def idx(options, value, default=0):
        return options.index(value) if value in options else default

    def side_idx(col):
        if row.get(col) is None:
            return 2
        return 0 if row[col] == row.get("team1_id") else 1

    with st.form(f"match_form_{key}"):
        desc = st.text_input("Match description *", row.get("match_desc") or "", key=f"{key}_desc")
        c1, c2, c3 = st.columns(3)
        fmt = c1.selectbox("Format *", FORMATS, index=idx(FORMATS, row.get("format")), key=f"{key}_fmt_f")
        mdate = c2.date_input("Match date *", row.get("match_date") or date.today(), key=f"{key}_date")
        venue = c3.selectbox(
            "Venue",
            venue_ids,
            key=f"{key}_venue",
            index=idx(venue_ids, int(row["venue_id"]) if row.get("venue_id") else None),
            format_func=lambda x: "Not set" if x is None else venue_label[x],
        )
        c4, c5 = st.columns(2)
        t1 = c4.selectbox(
            "Team 1 *",
            team_ids,
            format_func=team_name.get,
            key=f"{key}_t1",
            index=idx(team_ids, int(row["team1_id"]) if row.get("team1_id") else None, 0),
        )
        t2 = c5.selectbox(
            "Team 2 *",
            team_ids,
            format_func=team_name.get,
            key=f"{key}_t2",
            index=idx(team_ids, int(row["team2_id"]) if row.get("team2_id") else None, 1),
        )
        c6, c7 = st.columns(2)
        toss = c6.radio(
            "Toss winner", SIDES, index=side_idx("toss_winner_id"), horizontal=True, key=f"{key}_toss"
        )
        decision_opts = ["bat", "bowl", "Not set"]
        decision = c7.radio(
            "Toss decision",
            decision_opts,
            horizontal=True,
            key=f"{key}_dec",
            index=idx(decision_opts, row.get("toss_decision"), 2),
        )
        c8, c9, c10 = st.columns(3)
        winner = c8.radio("Winner", SIDES, index=side_idx("winner_id"), horizontal=True, key=f"{key}_win")
        vtype_opts = ["Not set"] + VICTORY_TYPES
        vtype = c9.selectbox(
            "Result type", vtype_opts, key=f"{key}_vtype", index=idx(vtype_opts, row.get("victory_type"))
        )
        margin = c10.number_input(
            "Margin (runs / wickets)", 0, 1000, int(row.get("victory_margin") or 0), key=f"{key}_margin"
        )
        submitted = st.form_submit_button("💾 Save match", type="primary")

    if not submitted:
        return None

    errors = []
    if not desc.strip():
        errors.append("Match description is required.")
    if t1 == t2:
        errors.append("Team 1 and Team 2 must be different.")
    if vtype in ("runs", "wickets", "innings"):
        if winner == "None":
            errors.append("A win by runs/wickets/innings needs a winner.")
        if margin <= 0:
            errors.append("Margin must be greater than 0.")
        if vtype == "wickets" and margin > 10:
            errors.append("A wickets margin cannot exceed 10.")
    if vtype in ("draw", "no result") and winner != "None":
        errors.append("A draw / no result cannot have a winner.")
    if toss != "None" and decision == "Not set":
        errors.append("Choose a toss decision for the toss winner.")
    for e in errors:
        st.error(e)
    if errors:
        return None

    side = {"Team 1": t1, "Team 2": t2, "None": None}
    has_margin = vtype in ("runs", "wickets", "innings")
    win_id = side[winner]
    if win_id and has_margin:
        rtext = (
            f"{team_name[win_id]} won by an innings and {margin} runs"
            if vtype == "innings"
            else f"{team_name[win_id]} won by {margin} {'runs' if vtype == 'runs' else 'wkts'}"
        )
    else:
        rtext = {"tie": "Match tied", "draw": "Match drawn", "no result": "No result"}.get(vtype)
    return {
        "desc": desc.strip(),
        "fmt": fmt,
        "mdate": mdate,
        "vid": venue,
        "t1": t1,
        "t2": t2,
        "tw": side[toss],
        "td": None if decision == "Not set" else decision,
        "win": win_id,
        "vtype": None if vtype == "Not set" else vtype,
        "margin": margin if has_margin else None,
        "rtext": rtext,
    }


def matches_create() -> None:
    data = match_form("mc")
    if data:
        write(
            """
            INSERT INTO matches (match_desc, format, match_date, venue_id, team1_id, team2_id,
                toss_winner_id, toss_decision, winner_id, victory_type, victory_margin,
                result_text, state, source)
            VALUES (:desc, :fmt, :mdate, :vid, :t1, :t2, :tw, :td, :win, :vtype, :margin,
                :rtext, 'Complete', 'manual')
        """,
            data,
            f"Match '{data['desc']}' added.",
        )


def matches_update() -> None:
    mid = pick_match("mu")
    if mid is None:
        return
    row = clean(DB.run_query("SELECT * FROM matches WHERE match_id = :id", {"id": mid}).iloc[0])
    st.caption(f"Source: **{row['source']}** · current result: {row.get('result_text') or '-'}")
    data = match_form(f"mu_{mid}", row)
    if data:
        write(
            """
            UPDATE matches SET match_desc = :desc, format = :fmt, match_date = :mdate,
                venue_id = :vid, team1_id = :t1, team2_id = :t2, toss_winner_id = :tw,
                toss_decision = :td, winner_id = :win, victory_type = :vtype,
                victory_margin = :margin, result_text = :rtext
            WHERE match_id = :id
        """,
            {**data, "id": mid},
            f"Match {mid} updated.",
        )


def matches_delete() -> None:
    mid = pick_match("md")
    if mid is None:
        return
    c = DB.run_query(
        """
        SELECT (SELECT COUNT(*) FROM batting_innings WHERE match_id = :id) AS batting,
               (SELECT COUNT(*) FROM bowling_innings WHERE match_id = :id) AS bowling,
               (SELECT COUNT(*) FROM fielding WHERE match_id = :id) AS fielding
    """,
        {"id": mid},
    ).iloc[0]
    st.warning(
        f"This also deletes {c.batting} batting, {c.bowling} bowling and "
        f"{c.fielding} fielding rows for this match (ON DELETE CASCADE)."
    )
    confirm = st.checkbox("I understand - delete this match", key=f"md_confirm_{mid}")
    if st.button("🗑️ Delete match", type="primary", disabled=not confirm, key=f"md_btn_{mid}"):
        write("DELETE FROM matches WHERE match_id = :id", {"id": mid}, f"Match {mid} deleted.")


# ================= Layout =================
tab_players, tab_matches = st.tabs(["👤 Players", "🏟️ Matches"])
OPS = ["Read", "Create", "Update", "Delete"]

with tab_players:
    op = st.radio("Operation", OPS, horizontal=True, key="player_op")
    {"Read": players_read, "Create": players_create, "Update": players_update, "Delete": players_delete}[op]()

with tab_matches:
    op = st.radio("Operation", OPS, horizontal=True, key="match_op")
    {"Read": matches_read, "Create": matches_create, "Update": matches_update, "Delete": matches_delete}[op]()
