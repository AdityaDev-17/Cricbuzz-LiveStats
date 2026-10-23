"""Export the first 100 rows of every table to sql/sample_data/<table>.csv."""
from pathlib import Path

from utils.db_connection import DatabaseConnection

TABLES = ["teams", "venues", "players", "series", "matches",
          "batting_innings", "bowling_innings", "fielding", "player_career_stats"]
OUT = Path("sql/sample_data")
OUT.mkdir(parents=True, exist_ok=True)

for table in TABLES:
    df = DatabaseConnection.run_query(f"SELECT * FROM {table} LIMIT 100")
    df.to_csv(OUT / f"{table}.csv", index=False)
    print(f"{table:<22} {len(df)} rows")