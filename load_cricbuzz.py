"""Run the Cricbuzz loader.  Usage:
python load_cricbuzz.py --dry-run
python load_cricbuzz.py --matches 15 --profiles 20
"""

import argparse

from utils.cricbuzz_loader import CricbuzzLoader
from utils.db_connection import DatabaseConnection

parser = argparse.ArgumentParser()
parser.add_argument("--matches", type=int, default=15)
parser.add_argument("--profiles", type=int, default=20)
parser.add_argument("--dry-run", action="store_true")
args = parser.parse_args()

loader = CricbuzzLoader()
matches = loader.list_recent_international(args.matches)

print(f"Found {len(matches)} completed international matches:")
for m in matches:
    print(
        f"  {m['matchId']}: {m['team1']['teamSName']} vs {m['team2']['teamSName']} "
        f"- {m['matchDesc']} ({m['matchFormat']}) - {m.get('status', '')}"
    )
match_calls = loader.estimate_calls(matches)
print(
    f"\nEstimated API calls -> matches/venues: {match_calls}, "
    f"profiles: up to {args.profiles * 3}, total: up to {match_calls + args.profiles * 3}"
)

if args.dry_run:
    raise SystemExit("\nDry run only - nothing loaded.")

print("\n=== Loading matches ===")
for m in matches:
    try:
        loader.load_match(m)
        print(f"  OK   {m['matchId']} {m['matchDesc']}")
    except Exception as exc:
        print(f"  FAIL {m['matchId']}: {exc}")
loader.update_series_counts()

print("\n=== Loading player profiles ===")
for cb_id, name in loader.top_unprofiled_players(args.profiles):
    try:
        loader.load_player_profile(cb_id)
        print(f"  OK   {name}")
    except Exception as exc:
        print(f"  FAIL {name}: {exc}")
        if "quota" in str(exc).lower():
            break

print("\n=== Row counts ===")
print(DatabaseConnection.run_query("""
    SELECT 'teams' AS tbl, COUNT(*) FROM teams UNION ALL
    SELECT 'venues', COUNT(*) FROM venues UNION ALL
    SELECT 'series', COUNT(*) FROM series UNION ALL
    SELECT 'players', COUNT(*) FROM players UNION ALL
    SELECT 'matches', COUNT(*) FROM matches UNION ALL
    SELECT 'batting_innings', COUNT(*) FROM batting_innings UNION ALL
    SELECT 'bowling_innings', COUNT(*) FROM bowling_innings UNION ALL
    SELECT 'fielding', COUNT(*) FROM fielding UNION ALL
    SELECT 'player_career_stats', COUNT(*) FROM player_career_stats
""").to_string(index=False))
print(f"\nQuota remaining: {loader.client.quota_remaining}")
