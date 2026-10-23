"""Profile Kohli (cached = 0 calls) + top Indian players from loaded matches."""

from utils.cricbuzz_loader import CricbuzzLoader
from utils.db_connection import DatabaseConnection

LIMIT = 8  # 3 calls each

loader = CricbuzzLoader()
loader.load_player_profile(1413)
print("OK   Virat Kohli (from cache)")

df = DatabaseConnection.run_query(
    """
    SELECT p.cricbuzz_player_id, p.full_name, COUNT(*) AS apps
    FROM players p
    JOIN (SELECT player_id FROM batting_innings
          UNION ALL SELECT player_id FROM bowling_innings) x USING (player_id)
    WHERE p.country = 'India' AND p.playing_role IS NULL
    GROUP BY p.cricbuzz_player_id, p.full_name
    ORDER BY apps DESC
    LIMIT :n
""",
    {"n": LIMIT},
)

for cb_id, name in df[["cricbuzz_player_id", "full_name"]].itertuples(index=False, name=None):
    try:
        loader.load_player_profile(int(cb_id))
        print(f"OK   {name}")
    except Exception as exc:
        print(f"FAIL {name}: {exc}")
        break

print(f"\nQuota remaining: {loader.client.quota_remaining}")
print(DatabaseConnection.run_query("""
    SELECT full_name, playing_role, batting_style, bowling_style
    FROM players WHERE country = 'India' AND playing_role IS NOT NULL
""").to_string(index=False))
