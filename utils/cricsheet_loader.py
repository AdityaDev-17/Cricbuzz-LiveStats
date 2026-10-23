"""Load Cricsheet ball-by-ball JSON into the scorecard tables (PostgreSQL)."""

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Connection

from utils.db_connection import DatabaseConnection

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CRICSHEET_DIR = PROJECT_ROOT / "data" / "cricsheet"
FOLDER_FORMAT = {"tests": "Test", "odis": "ODI", "t20is": "T20I"}

FULL_MEMBERS = {
    "India",
    "Australia",
    "England",
    "South Africa",
    "New Zealand",
    "Pakistan",
    "Sri Lanka",
    "West Indies",
    "Bangladesh",
    "Afghanistan",
    "Zimbabwe",
    "Ireland",
}
BOWLER_WICKETS = {"bowled", "caught", "caught and bowled", "lbw", "stumped", "hit wicket"}
NOT_OUT_KINDS = {"retired hurt", "retired not out"}

# Approximate public capacities (manual seed so Q4 has data). (name pattern, capacity)
MAJOR_VENUE_CAPACITY = [
    ("%narendra modi%", 132000),
    ("%melbourne cricket ground%", 100024),
    ("%eden gardens%", 66000),
    ("%shaheed veer narayan singh%", 65000),
    ("%perth stadium%", 60000),
    ("%rajiv gandhi international stadium%", 55000),
    ("%adelaide oval%", 53500),
]


def _overs_str(balls: int) -> str:
    return f"{balls // 6}.{balls % 6}" if balls % 6 else str(balls // 6)


def _real_fielders(wicket: dict) -> list[str]:
    """Fielder names, excluding substitutes (they are not in the XI)."""
    return [f["name"] for f in wicket.get("fielders", []) if f.get("name") and not f.get("substitute")]


def _dismissal_text(wicket: dict, bowler: str) -> str:
    """Build Cricbuzz-style dismissal text from a Cricsheet wicket."""
    kind = wicket.get("kind", "")
    fielders = _real_fielders(wicket)
    f0 = fielders[0] if fielders else "sub"
    return {
        "caught": f"c {f0} b {bowler}",
        "caught and bowled": f"c & b {bowler}",
        "bowled": f"b {bowler}",
        "lbw": f"lbw b {bowler}",
        "stumped": f"st {f0} b {bowler}",
        "hit wicket": f"hit wicket b {bowler}",
        "run out": f"run out ({f0})",
    }.get(kind, kind)


class CricsheetLoader:
    """Parses Cricsheet files and upserts them into the shared schema."""

    def __init__(self, since: str = "2022-01-01", full_members_only: bool = True):
        self.since = since
        self.full_members_only = full_members_only
        self.engine = DatabaseConnection.get_engine()
        self.venue_host_votes: dict[int, Counter] = defaultdict(Counter)
        self._reset_caches()
        self.existing = set(
            DatabaseConnection.run_query(
                "SELECT cricsheet_match_id FROM matches WHERE cricsheet_match_id IS NOT NULL"
            )["cricsheet_match_id"]
        )

    # ================= CACHES =================
    def _reset_caches(self) -> None:
        """Clear in-memory id caches (called after a failed match rolls back)."""
        self.team_cache: dict[str, int] = {}
        self.venue_cache: dict[tuple, int] = {}
        self.series_cache: dict[str, int] = {}
        self.player_cache: dict[str, int] = {}
        df = DatabaseConnection.run_query("""
            SELECT player_id, full_name, country FROM players
            WHERE cricbuzz_player_id IS NOT NULL AND cricsheet_player_id IS NULL
        """)
        self.link_index: dict[tuple, list] = defaultdict(list)
        for pid, name, country in df.itertuples(index=False, name=None):
            surname = name.split()[-1].lower()
            self.link_index[(country, surname)].append((pid, name))

    # ================= FILE DISCOVERY =================
    def iter_files(self):
        """Yield (path, format) for every Cricsheet JSON file."""
        for folder, fmt in FOLDER_FORMAT.items():
            for path in sorted((CRICSHEET_DIR / folder).glob("*.json")):
                yield path, fmt

    def _keep(self, info: dict) -> bool:
        if info.get("gender") != "male" or info.get("team_type") != "international":
            return False
        if not info.get("dates") or info["dates"][0] < self.since:
            return False
        if self.full_members_only and not set(info.get("teams", [])) <= FULL_MEMBERS:
            return False
        return len(info.get("teams", [])) == 2

    # ================= RESOLVERS =================
    def _team(self, conn: Connection, name: str) -> int:
        if name not in self.team_cache:
            self.team_cache[name] = conn.execute(
                text("""
                INSERT INTO teams (team_name, country) VALUES (:n, :n)
                ON CONFLICT (team_name) DO UPDATE SET team_name = EXCLUDED.team_name
                RETURNING team_id
            """),
                {"n": name},
            ).scalar_one()
        return self.team_cache[name]

    def _venue(self, conn: Connection, raw_name: str, city: str | None) -> int:
        name = raw_name
        if city and raw_name.endswith(f", {city}"):
            name = raw_name[: -len(f", {city}")]
        key = (name, city)
        if key not in self.venue_cache:
            self.venue_cache[key] = conn.execute(
                text("""
                INSERT INTO venues (venue_name, city) VALUES (:n, :c)
                ON CONFLICT (venue_name, city) DO UPDATE SET venue_name = EXCLUDED.venue_name
                RETURNING venue_id
            """),
                {"n": name, "c": city},
            ).scalar_one()
        return self.venue_cache[key]

    @staticmethod
    def _host_from_event(event_name: str | None) -> str | None:
        m = re.search(r"tour of (.+?)(?:,|\s+\d{4}|$)", event_name or "", re.I)
        return m.group(1).strip() if m else None

    def _series(self, conn: Connection, info: dict, fmt: str) -> int | None:
        event = (info.get("event") or {}).get("name")
        if not event:
            return None
        season = str(info.get("season", ""))
        name = event if season and season[:4] in event else f"{event} {season}".strip()
        if name not in self.series_cache:
            sid = conn.execute(
                text("""
                SELECT series_id FROM series
                WHERE series_name = :n AND cricbuzz_series_id IS NULL
            """),
                {"n": name},
            ).scalar()
            if not sid:
                sid = conn.execute(
                    text("""
                    INSERT INTO series (series_name, host_country, match_type)
                    VALUES (:n, :host, :mt) RETURNING series_id
                """),
                    {"n": name, "host": self._host_from_event(event), "mt": fmt},
                ).scalar_one()
            self.series_cache[name] = sid
        return self.series_cache[name]

    def _player(self, conn: Connection, name: str, cs_id: str | None, country: str) -> int:
        cs_id = cs_id or "x" + hashlib.md5(name.encode()).hexdigest()[:12]
        if cs_id in self.player_cache:
            return self.player_cache[cs_id]

        pid = conn.execute(
            text("SELECT player_id FROM players WHERE cricsheet_player_id = :c"), {"c": cs_id}
        ).scalar()
        if not pid:
            pid = self._link_cricbuzz(conn, name, cs_id, country)
        if not pid:
            pid = conn.execute(
                text("""
                INSERT INTO players (cricsheet_player_id, full_name, country)
                VALUES (:c, :n, :country) RETURNING player_id
            """),
                {"c": cs_id, "n": name, "country": country},
            ).scalar_one()
        self.player_cache[cs_id] = pid
        return pid

    def _link_cricbuzz(self, conn: Connection, name: str, cs_id: str, country: str) -> int | None:
        """'V Kohli' + India -> existing Cricbuzz 'Virat Kohli' row (if unique)."""
        tokens = name.split()
        if len(tokens) < 2:
            return None
        surname, initial = tokens[-1].lower(), tokens[0][0].lower()
        candidates = [
            (pid, full)
            for pid, full in self.link_index.get((country, surname), [])
            if full[0].lower() == initial
        ]
        if len(candidates) != 1:
            return None
        pid = candidates[0][0]
        conn.execute(
            text("UPDATE players SET cricsheet_player_id = :c WHERE player_id = :p"), {"c": cs_id, "p": pid}
        )
        self.link_index[(country, surname)] = [c for c in self.link_index[(country, surname)] if c[0] != pid]
        return pid

    # ================= INNINGS PARSING =================
    @staticmethod
    def _process_innings(inn: dict):
        """Ball-by-ball -> (batting order, batting, bowling, fielding) dicts."""
        order: list[str] = []
        bat = defaultdict(
            lambda: {"runs": 0, "balls": 0, "fours": 0, "sixes": 0, "out": False, "dismissal": None}
        )
        bowl = defaultdict(lambda: {"balls": 0, "runs": 0, "wickets": 0, "maidens": 0})
        field: dict[str, Counter] = defaultdict(Counter)

        for over in inn.get("overs", []):
            over_by_bowler = defaultdict(lambda: [0, 0])  # legal balls, conceded
            for d in over.get("deliveries", []):
                striker = d.get("batter") or d.get("batsman")
                bowler = d.get("bowler")
                for name in (striker, d.get("non_striker")):
                    if name and name not in bat:
                        order.append(name)
                        bat[name]

                runs, extras = d.get("runs", {}), d.get("extras", {})
                is_wide, is_noball = "wides" in extras, "noballs" in extras
                b_runs = runs.get("batter", 0)

                s = bat[striker]
                s["runs"] += b_runs
                if not is_wide:
                    s["balls"] += 1
                if not runs.get("non_boundary"):
                    s["fours"] += b_runs == 4
                    s["sixes"] += b_runs == 6

                conceded = b_runs + extras.get("wides", 0) + extras.get("noballs", 0)
                legal = not is_wide and not is_noball
                bowl[bowler]["runs"] += conceded
                bowl[bowler]["balls"] += legal
                over_by_bowler[bowler][0] += legal
                over_by_bowler[bowler][1] += conceded

                for w in d.get("wickets", []):
                    out_name, kind = w.get("player_out"), w.get("kind", "")
                    if out_name not in bat:
                        order.append(out_name)
                    bat[out_name]["out"] = kind not in NOT_OUT_KINDS
                    bat[out_name]["dismissal"] = _dismissal_text(w, bowler)
                    if kind in BOWLER_WICKETS:
                        bowl[bowler]["wickets"] += 1
                    fielders = _real_fielders(w)
                    if kind == "caught" and fielders:
                        field[fielders[0]]["catch"] += 1
                    elif kind == "caught and bowled":
                        field[bowler]["catch"] += 1
                    elif kind == "stumped" and fielders:
                        field[fielders[0]]["stumping"] += 1
                    elif kind == "run out" and fielders:
                        field[fielders[0]]["run_out"] += 1

            for name, (legal_balls, conc) in over_by_bowler.items():
                if legal_balls >= 6 and conc == 0:
                    bowl[name]["maidens"] += 1
        return order, bat, bowl, field

    # ================= MATCH LOADING =================
    @staticmethod
    def _result(outcome: dict) -> tuple[str | None, int | None, str | None, str]:
        """-> (winner, margin, victory_type, result_text)."""
        winner, by = outcome.get("winner"), outcome.get("by", {})
        if winner and "innings" in by:
            return winner, by.get("runs"), "innings", f"{winner} won by an innings and {by.get('runs')} runs"
        if winner and "runs" in by:
            return winner, by["runs"], "runs", f"{winner} won by {by['runs']} runs"
        if winner and "wickets" in by:
            return winner, by["wickets"], "wickets", f"{winner} won by {by['wickets']} wkts"
        result = outcome.get("result")
        if result == "tie":
            elim = outcome.get("eliminator")
            return elim, None, "tie", f"Match tied{f' ({elim} won Super Over)' if elim else ''}"
        if result == "draw":
            return None, None, "draw", "Match drawn"
        return None, None, "no result", "No result"

    def load_file(self, path: Path, fmt: str) -> str:
        """Load one file. Returns 'loaded', 'skipped' or 'exists'."""
        if path.stem in self.existing:
            return "exists"
        data = json.loads(path.read_text(encoding="utf-8"))
        info = data.get("info", {})
        if not self._keep(info):
            return "skipped"

        registry = info.get("registry", {}).get("people", {})
        team_a, team_b = info["teams"]

        with self.engine.begin() as conn:
            t_ids = {team_a: self._team(conn, team_a), team_b: self._team(conn, team_b)}
            other = {team_a: team_b, team_b: team_a}
            venue_id = self._venue(conn, info.get("venue", "Unknown"), info.get("city"))
            series_id = self._series(conn, info, fmt)

            host = self._host_from_event((info.get("event") or {}).get("name"))
            if host:
                self.venue_host_votes[venue_id][host] += 1

            toss = info.get("toss", {})
            decision = {"field": "bowl", "bat": "bat"}.get(toss.get("decision"))
            winner, margin, vtype, rtext = self._result(info.get("outcome", {}))
            event = info.get("event") or {}
            desc = (
                f"Match {event['match_number']}"
                if event.get("match_number")
                else f"{fmt} #{info.get('match_type_number', '')}"
            )

            match_id = conn.execute(
                text("""
                INSERT INTO matches (cricsheet_match_id, series_id, match_desc, format,
                    team1_id, team2_id, venue_id, match_date, toss_winner_id, toss_decision,
                    winner_id, victory_margin, victory_type, result_text, state, source)
                VALUES (:csid, :sid, :desc, :fmt, :t1, :t2, :vid, :mdate, :tw, :td,
                    :win, :margin, :vtype, :rtext, 'Complete', 'cricsheet')
                RETURNING match_id
            """),
                {
                    "csid": path.stem,
                    "sid": series_id,
                    "desc": desc,
                    "fmt": fmt,
                    "t1": t_ids[team_a],
                    "t2": t_ids[team_b],
                    "vid": venue_id,
                    "mdate": info["dates"][0],
                    "tw": t_ids.get(toss.get("winner")),
                    "td": decision,
                    "win": t_ids.get(winner),
                    "margin": margin,
                    "vtype": vtype,
                    "rtext": rtext,
                },
            ).scalar_one()

            # Make sure every XI player exists (also covers fielders who never batted/bowled)
            for team, names in info.get("players", {}).items():
                for n in names:
                    self._player(conn, n, registry.get(n), team)

            bat_rows, bowl_rows, field_totals = [], [], defaultdict(Counter)
            innings_list = [i for i in data.get("innings", []) if not i.get("super_over")]
            for inn_no, inn in enumerate(innings_list, start=1):
                if inn_no > 4:
                    break
                bat_team, bowl_team = inn["team"], other[inn["team"]]
                order, bat, bowl, field = self._process_innings(inn)

                for pos, name in enumerate(order, start=1):
                    s = bat[name]
                    bat_rows.append(
                        {
                            "mid": match_id,
                            "inn": inn_no,
                            "team": t_ids[bat_team],
                            "pid": self._player(conn, name, registry.get(name), bat_team),
                            "pos": pos if pos <= 11 else None,
                            "runs": s["runs"],
                            "balls": s["balls"],
                            "fours": s["fours"],
                            "sixes": s["sixes"],
                            "sr": round(s["runs"] * 100 / s["balls"], 2) if s["balls"] else None,
                            "out": s["out"],
                            "dis": s["dismissal"],
                        }
                    )
                for name, b in bowl.items():
                    bowl_rows.append(
                        {
                            "mid": match_id,
                            "inn": inn_no,
                            "team": t_ids[bowl_team],
                            "pid": self._player(conn, name, registry.get(name), bowl_team),
                            "balls": b["balls"],
                            "overs": _overs_str(b["balls"]),
                            "maidens": b["maidens"],
                            "runs": b["runs"],
                            "wkts": b["wickets"],
                            "eco": round(b["runs"] * 6 / b["balls"], 2) if b["balls"] else None,
                        }
                    )
                for name, counts in field.items():
                    pid = self._player(conn, name, registry.get(name), bowl_team)
                    field_totals[pid].update(counts)

            if bat_rows:
                conn.execute(
                    text("""
                    INSERT INTO batting_innings (match_id, innings_no, team_id, player_id,
                        batting_position, runs, balls, fours, sixes, strike_rate, is_out, dismissal)
                    VALUES (:mid, :inn, :team, :pid, :pos, :runs, :balls, :fours, :sixes,
                        :sr, :out, :dis)
                    ON CONFLICT (match_id, innings_no, player_id) DO NOTHING
                """),
                    bat_rows,
                )
            if bowl_rows:
                conn.execute(
                    text("""
                    INSERT INTO bowling_innings (match_id, innings_no, team_id, player_id,
                        balls_bowled, overs, maidens, runs_conceded, wickets, economy)
                    VALUES (:mid, :inn, :team, :pid, :balls, :overs, :maidens, :runs, :wkts, :eco)
                    ON CONFLICT (match_id, innings_no, player_id) DO NOTHING
                """),
                    bowl_rows,
                )
            if field_totals:
                conn.execute(
                    text("""
                    INSERT INTO fielding (match_id, player_id, catches, stumpings, run_outs)
                    VALUES (:mid, :pid, :c, :s, :r)
                    ON CONFLICT (match_id, player_id) DO NOTHING
                """),
                    [
                        {"mid": match_id, "pid": pid, "c": c["catch"], "s": c["stumping"], "r": c["run_out"]}
                        for pid, c in field_totals.items()
                    ],
                )

        self.existing.add(path.stem)
        return "loaded"

    # ================= FINALIZE =================
    def finalize(self) -> None:
        """Venue countries, series dates/counts/hosts, major venue capacities."""
        with self.engine.begin() as conn:
            for venue_id, votes in self.venue_host_votes.items():
                conn.execute(
                    text("""
                    UPDATE venues SET country = :c WHERE venue_id = :v AND country IS NULL
                """),
                    {"c": votes.most_common(1)[0][0], "v": venue_id},
                )

            conn.execute(text("""
                UPDATE series s SET
                    start_date = COALESCE(s.start_date, x.first_date),
                    end_date = COALESCE(s.end_date, x.last_date),
                    total_matches = x.n
                FROM (SELECT series_id, MIN(match_date) AS first_date,
                             MAX(match_date) AS last_date, COUNT(*) AS n
                      FROM matches WHERE series_id IS NOT NULL GROUP BY series_id) x
                WHERE s.series_id = x.series_id
            """))
            conn.execute(text("""
                UPDATE series s SET host_country = sub.country
                FROM (SELECT DISTINCT ON (m.series_id) m.series_id, v.country
                      FROM matches m JOIN venues v ON v.venue_id = m.venue_id
                      WHERE v.country IS NOT NULL
                      ORDER BY m.series_id, m.match_date) sub
                WHERE s.series_id = sub.series_id AND s.host_country IS NULL
            """))
            for pattern, capacity in MAJOR_VENUE_CAPACITY:
                conn.execute(
                    text("""
                    UPDATE venues SET capacity = :cap
                    WHERE venue_name ILIKE :pat AND capacity IS NULL
                """),
                    {"cap": capacity, "pat": pattern},
                )
