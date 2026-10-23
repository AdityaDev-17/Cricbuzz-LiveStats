"""Run the Cricsheet loader.  Usage:
python load_cricsheet.py --limit 20          (test run)
python load_cricsheet.py                     (full load, 2022+, full members)
python load_cricsheet.py --all-teams         (include associate nations)
"""

import argparse
import time
from collections import Counter

from utils.cricsheet_loader import CricsheetLoader
from utils.db_connection import DatabaseConnection

parser = argparse.ArgumentParser()
parser.add_argument("--since", default="2022-01-01")
parser.add_argument("--limit", type=int, default=None, help="stop after N loaded matches")
parser.add_argument("--all-teams", action="store_true")
args = parser.parse_args()

loader = CricsheetLoader(since=args.since, full_members_only=not args.all_teams)
stats, start = Counter(), time.time()

for path, fmt in loader.iter_files():
    try:
        status = loader.load_file(path, fmt)
        stats[status] += 1
        if status == "loaded" and stats["loaded"] % 100 == 0:
            print(f"  {stats['loaded']} matches loaded... ({time.time() - start:.0f}s)")
    except Exception as exc:
        stats["failed"] += 1
        print(f"  FAIL {path.name}: {str(exc)[:150]}")
        loader._reset_caches()
    if args.limit and stats["loaded"] >= args.limit:
        break

print("\nFinalizing (venue countries, series, capacities)...")
loader.finalize()

print(f"\nDone in {time.time() - start:.0f}s -> {dict(stats)}")
print(DatabaseConnection.run_query("""
    SELECT source, format, COUNT(*) AS matches,
           MIN(match_date) AS first, MAX(match_date) AS last
    FROM matches GROUP BY source, format ORDER BY source, format
""").to_string(index=False))
print(DatabaseConnection.run_query("""
    SELECT 'players' AS tbl, COUNT(*) FROM players UNION ALL
    SELECT 'linked (both sources)', COUNT(*) FROM players
        WHERE cricbuzz_player_id IS NOT NULL AND cricsheet_player_id IS NOT NULL UNION ALL
    SELECT 'batting_innings', COUNT(*) FROM batting_innings UNION ALL
    SELECT 'bowling_innings', COUNT(*) FROM bowling_innings UNION ALL
    SELECT 'fielding', COUNT(*) FROM fielding UNION ALL
    SELECT 'venues', COUNT(*) FROM venues UNION ALL
    SELECT 'venues with country', COUNT(*) FROM venues WHERE country IS NOT NULL UNION ALL
    SELECT 'series', COUNT(*) FROM series
""").to_string(index=False))
