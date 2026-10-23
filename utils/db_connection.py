"""Centralized PostgreSQL connection handling using SQLAlchemy."""

import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, Engine

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


class DatabaseConnection:
    """Wraps a SQLAlchemy engine for the Cricbuzz database."""

    _engine: Engine | None = None
    REQUIRED_VARS = ("DB_NAME", "DB_USER", "DB_PASSWORD")

    @classmethod
    def _build_url(cls) -> URL:
        """Build the connection URL from environment variables."""
        missing = [v for v in cls.REQUIRED_VARS if not os.getenv(v)]
        if missing:
            raise RuntimeError(f"Missing in .env: {', '.join(missing)} (looked in {PROJECT_ROOT / '.env'})")
        return URL.create(
            drivername="postgresql+psycopg2",
            username=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "5432")),
            database=os.getenv("DB_NAME"),
        )

    @classmethod
    def get_engine(cls) -> Engine:
        """Create the engine once and reuse it."""
        if cls._engine is None:
            cls._engine = create_engine(cls._build_url(), pool_pre_ping=True)
        return cls._engine

    @classmethod
    def run_query(cls, sql: str, params: dict | None = None) -> pd.DataFrame:
        """Run a SELECT and return a DataFrame."""
        with cls.get_engine().connect() as conn:
            return pd.read_sql(text(sql), conn, params=params)

    @classmethod
    def execute(cls, sql: str, params: dict | None = None) -> None:
        """Run INSERT/UPDATE/DELETE/DDL inside a transaction."""
        with cls.get_engine().begin() as conn:
            conn.execute(text(sql), params or {})

    @classmethod
    def test_connection(cls) -> bool:
        """Return True if the database is reachable."""
        try:
            cls.run_query("SELECT 1")
            return True
        except Exception as exc:
            print(f"DB connection failed: {exc}")
            return False


if __name__ == "__main__":
    print("Connected!" if DatabaseConnection.test_connection() else "Not connected.")
