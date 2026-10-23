"""Load Cricbuzz API data (matches, scorecards, venues, players) into PostgreSQL."""

import re
from collections import Counter, defaultdict

from sqlalchemy import text
from sqlalchemy.engine import Connection

from utils import parsers as p
from utils.api_client import CricbuzzAPIError, CricbuzzClient
from utils.db_connection import DatabaseConnection

FIELDING_COLUMN = {"catch": "catches", "stumping": "stumpings", "run_out": "run_outs"}


class CricbuzzLoader:
    """Fetches Cricbuzz data through the cached client and upserts it into the DB."""

    def __init__(self, client: CricbuzzClient | None = None):
        self.client = client or CricbuzzClient()
        self.engine = DatabaseConnection.get_engine()

    # ================= DISCOVERY =================
    def list_recent_international(self, limit: int) -> list[dict]:
        """Completed international matches from the (cached) recent list."""
        data = self.client.recent_matches()
        found = []
        for type_block in data.get("typeMatches", []):
            if type_block.get("matchType") != "International":
                continue
            for series_block in type_block.get("seriesMatches", []):
                wrapper = series_block.get("seriesAdWrapper")
                if not wrapper:
                    continue  # ad entries have no wrapper
                for m in wrapper.get("matches", []):
                    info = m.get("matchInfo", {})
                    if info.get("state") == "Complete" and p.normalize_format(info.get("matchFormat")):
                        found.append(info)
        return found[:limit]

    def estimate_calls(self, matches: list[dict]) -> int:
        """Count API calls needed (files already cached cost nothing)."""
        cache = self.client.cache_dir
        needed, venues_seen = 0, set()
        for info in matches:
            mid, vid = info["matchId"], info.get("venueInfo", {}).get("id")
            needed += not (cache / f"match_{mid}_info.json").exists()
            needed += not (cache / f"match_{mid}_scorecard.json").exists()
            if vid and vid not in venues_seen and not (cache / f"venue_{vid}.json").exists():
                needed += 1
            venues_seen.add(vid)
        return needed

    # ================= SMALL UPSERTS =================
    @staticmethod
    def _upsert_team(conn: Connection, team: dict) -> int:
        return conn.execute(
            text("""
            INSERT INTO teams (cricbuzz_team_id, team_name, team_short_name, country)
            VALUES (:cid, :name, :short, :name)
            ON CONFLICT (team_name) DO UPDATE
                SET cricbuzz_team_id = COALESCE(teams.cricbuzz_team_id, EXCLUDED.cricbuzz_team_id),
                    team_short_name = EXCLUDED.team_short_name
            RETURNING team_id
        """),
            {"cid": team["teamId"], "name": team["teamName"], "short": team.get("teamSName")},
        ).scalar_one()

    def _get_or_load_venue(self, conn: Connection, venue_info: dict) -> int | None:
        vid = venue_info.get("id")
        if not vid:
            return None
        existing = conn.execute(
            text("SELECT venue_id FROM venues WHERE cricbuzz_venue_id = :v"), {"v": vid}
        ).scalar()
        if existing:
            return existing
        try:
            v = self.client.venue(vid)
        except CricbuzzAPIError as exc:
            print(f"    venue {vid} fetch failed ({exc}); saving basic info only")
            v = {}
        return conn.execute(
            text("""
            INSERT INTO venues (cricbuzz_venue_id, venue_name, city, country, capacity)
            VALUES (:vid, :name, :city, :country, :cap)
            ON CONFLICT (venue_name, city) DO UPDATE
                SET cricbuzz_venue_id = EXCLUDED.cricbuzz_venue_id,
                    country = COALESCE(EXCLUDED.country, venues.country),
                    capacity = COALESCE(EXCLUDED.capacity, venues.capacity)
            RETURNING venue_id
        """),
            {
                "vid": vid,
                "name": v.get("ground") or venue_info.get("ground"),
                "city": v.get("city") or venue_info.get("city"),
                "country": v.get("country"),
                "cap": p.parse_capacity(v.get("capacity")),
            },
        ).scalar_one()

    @staticmethod
    def _host_from_series_name(name: str | None) -> str | None:
        """'India tour of New Zealand 2026' -> 'New Zealand'."""
        m = re.search(r"tour of (.+?)(?:,|\s+\d{4}|$)", name or "", re.I)
        return m.group(1).strip() if m else None

    def _upsert_series(self, conn: Connection, info: dict, fmt: str) -> int | None:
        if not info.get("seriesId"):
            return None
        return conn.execute(
            text("""
            INSERT INTO series (cricbuzz_series_id, series_name, host_country, match_type,
                                start_date, end_date)
            VALUES (:sid, :name, :host, :mtype, :start, :end)
            ON CONFLICT (cricbuzz_series_id) DO UPDATE SET series_name = EXCLUDED.series_name
            RETURNING series_id
        """),
            {
                "sid": info["seriesId"],
                "name": info.get("seriesName"),
                "host": self._host_from_series_name(info.get("seriesName")),
                "mtype": fmt,
                "start": p.epoch_ms_to_date(info.get("seriesStartDt")),
                "end": p.epoch_ms_to_date(info.get("seriesEndDt")),
            },
        ).scalar_one()

    @staticmethod
    def _upsert_player(conn: Connection, cb_id: int, name: str, country: str | None) -> int:
        return conn.execute(
            text("""
            INSERT INTO players (cricbuzz_player_id, full_name, country)
            VALUES (:cid, :name, :country)
            ON CONFLICT (cricbuzz_player_id) DO UPDATE
                SET country = COALESCE(players.country, EXCLUDED.country)
            RETURNING player_id
        """),
            {"cid": cb_id, "name": name, "country": country},
        ).scalar_one()

    @staticmethod
    def _match_fielder(raw_name: str, squad: dict[str, int]) -> int | None:
        """Match 'Sanju Samson' / '†Samson' to a player id in the fielding XI."""
        name = re.sub(r"[†\(\)]|\bsub\b", "", raw_name).strip().lower()
        if name in squad:
            return squad[name]
        surname = name.split()[-1] if name else ""
        hits = [pid for full, pid in squad.items() if full.split()[-1] == surname]
        return hits[0] if len(hits) == 1 else None

    # ================= MATCH LOADING =================
    def load_match(self, info: dict) -> int:
        """Load one match: teams, venue, series, match row, innings, fielding."""
        mid = info["matchId"]
        center = self.client.match_info(mid)
        sc = self.client.scorecard(mid)
        fmt = p.normalize_format(info.get("matchFormat"))

        with self.engine.begin() as conn:
            t1 = self._upsert_team(conn, info["team1"])
            t2 = self._upsert_team(conn, info["team2"])
            team_by_name = {
                info["team1"]["teamName"]: t1,
                info["team1"].get("teamSName"): t1,
                info["team2"]["teamName"]: t2,
                info["team2"].get("teamSName"): t2,
            }
            team_name_by_id = {t1: info["team1"]["teamName"], t2: info["team2"]["teamName"]}
            venue_id = self._get_or_load_venue(conn, info.get("venueInfo", {}))
            series_id = self._upsert_series(conn, info, fmt)

            toss_team, toss_decision = p.parse_toss(center.get("tossstatus"))
            result_text = sc.get("status") or info.get("status")
            result = p.parse_result(result_text)

            match_id = conn.execute(
                text("""
                INSERT INTO matches (cricbuzz_match_id, series_id, match_desc, format,
                    team1_id, team2_id, venue_id, match_date, toss_winner_id, toss_decision,
                    winner_id, victory_margin, victory_type, result_text, state, source)
                VALUES (:cid, :sid, :desc, :fmt, :t1, :t2, :vid, :mdate, :toss_w, :toss_d,
                    :winner, :margin, :vtype, :rtext, :state, 'cricbuzz')
                ON CONFLICT (cricbuzz_match_id) DO UPDATE SET
                    toss_winner_id = EXCLUDED.toss_winner_id,
                    toss_decision  = EXCLUDED.toss_decision,
                    winner_id      = EXCLUDED.winner_id,
                    victory_margin = EXCLUDED.victory_margin,
                    victory_type   = EXCLUDED.victory_type,
                    result_text    = EXCLUDED.result_text,
                    state          = EXCLUDED.state
                RETURNING match_id
            """),
                {
                    "cid": mid,
                    "sid": series_id,
                    "desc": info.get("matchDesc"),
                    "fmt": fmt,
                    "t1": t1,
                    "t2": t2,
                    "vid": venue_id,
                    "mdate": p.epoch_ms_to_date(info.get("startDate")),
                    "toss_w": team_by_name.get(toss_team),
                    "toss_d": toss_decision,
                    "winner": team_by_name.get(result["winner"]),
                    "margin": result["margin"],
                    "vtype": result["type"],
                    "rtext": result_text,
                    "state": info.get("state"),
                },
            ).scalar_one()

            self._load_innings(conn, match_id, sc.get("scorecard", []), team_by_name, team_name_by_id)
        return match_id

    def _load_innings(
        self, conn: Connection, match_id: int, innings: list[dict], team_by_name: dict, team_name_by_id: dict
    ) -> None:
        # 1) Build each team's XI (name -> player_id) from the batsman lists
        squads: dict[int, dict[str, int]] = defaultdict(dict)
        for inn in innings:
            bat_team = team_by_name.get(inn.get("batteamname")) or team_by_name.get(inn.get("batteamsname"))
            for b in inn.get("batsman", []):
                pid = self._upsert_player(conn, b["id"], b["name"], team_name_by_id.get(bat_team))
                squads[bat_team][b["name"].lower()] = pid

        team_ids = list(team_name_by_id)
        other_team = {team_ids[0]: team_ids[1], team_ids[1]: team_ids[0]}
        fielding: dict[int, Counter] = defaultdict(Counter)

        for inn in innings:
            inn_no = inn["inningsid"]
            bat_team = team_by_name.get(inn.get("batteamname")) or team_by_name.get(inn.get("batteamsname"))
            bowl_team = other_team.get(bat_team)

            # 2) Batting rows (skip did-not-bat; list order = batting position)
            for pos, b in enumerate(inn.get("batsman", []), start=1):
                if b.get("balls", 0) == 0 and not b.get("outdec"):
                    continue
                d = p.parse_dismissal(b.get("outdec"))
                conn.execute(
                    text("""
                    INSERT INTO batting_innings (match_id, innings_no, team_id, player_id,
                        batting_position, runs, balls, fours, sixes, strike_rate, is_out, dismissal)
                    VALUES (:mid, :inn, :team, :pid, :pos, :runs, :balls, :fours, :sixes,
                        :sr, :out, :dis)
                    ON CONFLICT (match_id, innings_no, player_id) DO UPDATE SET
                        runs = EXCLUDED.runs, balls = EXCLUDED.balls, fours = EXCLUDED.fours,
                        sixes = EXCLUDED.sixes, strike_rate = EXCLUDED.strike_rate,
                        is_out = EXCLUDED.is_out, dismissal = EXCLUDED.dismissal
                """),
                    {
                        "mid": match_id,
                        "inn": inn_no,
                        "team": bat_team,
                        "pid": squads[bat_team][b["name"].lower()],
                        "pos": pos if pos <= 11 else None,
                        "runs": b.get("runs", 0),
                        "balls": b.get("balls", 0),
                        "fours": b.get("fours", 0),
                        "sixes": b.get("sixes", 0),
                        "sr": p.to_number(b.get("strkrate")),
                        "out": d["is_out"],
                        "dis": b.get("outdec") or None,
                    },
                )
                if d["fielder"] and d["kind"] in FIELDING_COLUMN and bowl_team in squads:
                    fid = self._match_fielder(d["fielder"], squads[bowl_team])
                    if fid:
                        fielding[fid][d["kind"]] += 1

            # 3) Bowling rows (balls computed from overs, not the API 'balls' field)
            for bw in inn.get("bowler", []):
                pid = self._upsert_player(conn, bw["id"], bw["name"], team_name_by_id.get(bowl_team))
                conn.execute(
                    text("""
                    INSERT INTO bowling_innings (match_id, innings_no, team_id, player_id,
                        balls_bowled, overs, maidens, runs_conceded, wickets, economy)
                    VALUES (:mid, :inn, :team, :pid, :balls, :overs, :maidens, :runs, :wkts, :eco)
                    ON CONFLICT (match_id, innings_no, player_id) DO UPDATE SET
                        balls_bowled = EXCLUDED.balls_bowled, overs = EXCLUDED.overs,
                        maidens = EXCLUDED.maidens, runs_conceded = EXCLUDED.runs_conceded,
                        wickets = EXCLUDED.wickets, economy = EXCLUDED.economy
                """),
                    {
                        "mid": match_id,
                        "inn": inn_no,
                        "team": bowl_team,
                        "pid": pid,
                        "balls": p.overs_to_balls(bw.get("overs")),
                        "overs": str(bw.get("overs")),
                        "maidens": bw.get("maidens", 0),
                        "runs": bw.get("runs", 0),
                        "wkts": bw.get("wickets", 0),
                        "eco": p.to_number(bw.get("economy")),
                    },
                )

        # 4) Fielding rows
        for pid, counts in fielding.items():
            conn.execute(
                text("""
                INSERT INTO fielding (match_id, player_id, catches, stumpings, run_outs)
                VALUES (:mid, :pid, :c, :s, :r)
                ON CONFLICT (match_id, player_id) DO UPDATE SET
                    catches = EXCLUDED.catches, stumpings = EXCLUDED.stumpings,
                    run_outs = EXCLUDED.run_outs
            """),
                {
                    "mid": match_id,
                    "pid": pid,
                    "c": counts["catch"],
                    "s": counts["stumping"],
                    "r": counts["run_out"],
                },
            )

    def update_series_counts(self) -> None:
        """Set total_matches = matches loaded per series (API gives no planned count)."""
        DatabaseConnection.execute("""
            UPDATE series s SET total_matches =
                (SELECT COUNT(*) FROM matches m WHERE m.series_id = s.series_id)
        """)

    # ================= PLAYER PROFILES =================
    def top_unprofiled_players(self, limit: int) -> list[tuple[int, str]]:
        """Most-appearing players that have no profile (role) loaded yet."""
        df = DatabaseConnection.run_query(
            """
            SELECT p.cricbuzz_player_id, p.full_name, COUNT(*) AS apps
            FROM players p
            JOIN (SELECT player_id FROM batting_innings
                  UNION ALL SELECT player_id FROM bowling_innings) x USING (player_id)
            WHERE p.cricbuzz_player_id IS NOT NULL AND p.playing_role IS NULL
            GROUP BY p.cricbuzz_player_id, p.full_name
            ORDER BY apps DESC
            LIMIT :n
        """,
            {"n": limit},
        )
        return list(df[["cricbuzz_player_id", "full_name"]].itertuples(index=False, name=None))

    def load_player_profile(self, cb_id: int) -> None:
        """Profile (role, styles, country) + per-format career stats."""
        info = self.client.player_info(cb_id)
        bat_grid = p.pivot_career_grid(self.client.player_batting(cb_id))
        bowl_grid = p.pivot_career_grid(self.client.player_bowling(cb_id))

        with self.engine.begin() as conn:
            pid = conn.execute(
                text("""
                INSERT INTO players (cricbuzz_player_id, full_name, country, playing_role,
                                     batting_style, bowling_style)
                VALUES (:cid, :name, :country, :role, :bat, :bowl)
                ON CONFLICT (cricbuzz_player_id) DO UPDATE SET
                    full_name = EXCLUDED.full_name, country = EXCLUDED.country,
                    playing_role = EXCLUDED.playing_role,
                    batting_style = EXCLUDED.batting_style,
                    bowling_style = EXCLUDED.bowling_style
                RETURNING player_id
            """),
                {
                    "cid": cb_id,
                    "name": info.get("name"),
                    "country": info.get("intlTeam"),
                    "role": info.get("role"),
                    "bat": info.get("bat"),
                    "bowl": info.get("bowl"),
                },
            ).scalar_one()

            for fmt in set(bat_grid) | set(bowl_grid):
                b, w = bat_grid.get(fmt, {}), bowl_grid.get(fmt, {})
                n_int = lambda d, k: p.to_number(d.get(k), int)
                n_flt = lambda d, k: p.to_number(d.get(k), float)
                if not (n_int(b, "Matches") or n_int(w, "Matches")):
                    continue  # format never played
                conn.execute(
                    text("""
                    INSERT INTO player_career_stats (player_id, format, matches, innings,
                        not_outs, runs, balls_faced, highest_score, batting_avg, strike_rate,
                        fours, sixes, fifties, hundreds, bowl_innings, balls_bowled,
                        runs_conceded, wickets, bowling_avg, economy, best_bowling, five_wickets)
                    VALUES (:pid, :fmt, :m, :inn, :no, :runs, :bf, :hs, :avg, :sr,
                        :fours, :sixes, :fifties, :hundreds, :binn, :bb,
                        :rc, :wkts, :bavg, :eco, :best, :fivew)
                    ON CONFLICT (player_id, format) DO UPDATE SET
                        matches = EXCLUDED.matches, innings = EXCLUDED.innings,
                        not_outs = EXCLUDED.not_outs, runs = EXCLUDED.runs,
                        balls_faced = EXCLUDED.balls_faced, highest_score = EXCLUDED.highest_score,
                        batting_avg = EXCLUDED.batting_avg, strike_rate = EXCLUDED.strike_rate,
                        fours = EXCLUDED.fours, sixes = EXCLUDED.sixes,
                        fifties = EXCLUDED.fifties, hundreds = EXCLUDED.hundreds,
                        bowl_innings = EXCLUDED.bowl_innings, balls_bowled = EXCLUDED.balls_bowled,
                        runs_conceded = EXCLUDED.runs_conceded, wickets = EXCLUDED.wickets,
                        bowling_avg = EXCLUDED.bowling_avg, economy = EXCLUDED.economy,
                        best_bowling = EXCLUDED.best_bowling, five_wickets = EXCLUDED.five_wickets
                """),
                    {
                        "pid": pid,
                        "fmt": fmt,
                        "m": n_int(b, "Matches") or n_int(w, "Matches"),
                        "inn": n_int(b, "Innings"),
                        "no": n_int(b, "Not Out"),
                        "runs": n_int(b, "Runs"),
                        "bf": n_int(b, "Balls"),
                        "hs": n_int(b, "Highest"),
                        "avg": n_flt(b, "Average"),
                        "sr": n_flt(b, "SR"),
                        "fours": n_int(b, "Fours"),
                        "sixes": n_int(b, "Sixes"),
                        "fifties": n_int(b, "50s"),
                        "hundreds": n_int(b, "100s"),
                        "binn": n_int(w, "Innings"),
                        "bb": n_int(w, "Balls"),
                        "rc": n_int(w, "Runs"),
                        "wkts": n_int(w, "Wickets"),
                        "bavg": n_flt(w, "Avg"),
                        "eco": n_flt(w, "Eco"),
                        "best": w.get("BBI") if w.get("BBI") not in ("-", "") else None,
                        "fivew": n_int(w, "5w"),
                    },
                )
