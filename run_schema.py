"""Create all tables from sql/schema.sql and list them to verify."""

from pathlib import Path

from utils.db_connection import DatabaseConnection

if not DatabaseConnection.test_connection():
    raise SystemExit("Fix the DB connection first (python -m utils.db_connection).")

schema_sql = Path("sql/schema.sql").read_text(encoding="utf-8")
DatabaseConnection.execute(schema_sql)
print("Schema created.\n")

tables = DatabaseConnection.run_query("""
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = 'public'
    ORDER BY table_name
""")
print(tables.to_string(index=False))
print(f"\nTotal tables: {len(tables)} (expected 9)")
