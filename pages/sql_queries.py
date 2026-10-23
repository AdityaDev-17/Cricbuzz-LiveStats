"""SQL analytics - 25 practice queries + a read-only custom SQL runner."""

import re
import time

import pandas as pd
import streamlit as st
from sqlalchemy import text

from utils.db_connection import DatabaseConnection
from utils.queries import QUERIES

st.title("🔍 SQL Analytics")
QUERY_BY_ID = {q["id"]: q for q in QUERIES}


@st.cache_data(ttl=600, show_spinner="Running query...")
def run_saved(qid: int) -> tuple[pd.DataFrame, float]:
    """Run one of the 25 saved queries and time it."""
    start = time.perf_counter()
    df = DatabaseConnection.run_query(QUERY_BY_ID[qid]["sql"])
    return df, time.perf_counter() - start


def run_readonly(sql: str) -> pd.DataFrame:
    """Run user SQL in a READ ONLY transaction with a 15 s timeout."""
    if not re.match(r"^\s*(select|with)\b", sql, re.IGNORECASE):
        raise ValueError("Only SELECT / WITH queries are allowed here. Use the CRUD page to modify data.")
    with DatabaseConnection.get_engine().connect() as conn:
        conn.execute(text("SET TRANSACTION READ ONLY"))
        conn.execute(text("SET LOCAL statement_timeout = '15s'"))
        df = pd.read_sql(text(sql.replace(":", r"\:")), conn)  # literal colons (e.g. ::casts)
        conn.rollback()
    return df


tab_practice, tab_custom = st.tabs(["📚 25 Practice Questions", "✍️ Custom SQL"])

# ---------------- Practice questions ----------------
with tab_practice:
    c1, c2 = st.columns([1, 3])
    level = c1.radio("Level", ["All", "Beginner", "Intermediate", "Advanced"])
    options = [q["id"] for q in QUERIES if level == "All" or q["level"] == level]
    qid = c2.selectbox(
        "Question",
        options,
        format_func=lambda i: f"Q{i} · {QUERY_BY_ID[i]['level']} · {QUERY_BY_ID[i]['title']}",
    )
    q = QUERY_BY_ID[qid]

    st.info(f"**Q{q['id']}.** {q['question']}")
    with st.expander("Show SQL", expanded=False):
        st.code(q["sql"].strip(), language="sql")

    try:
        df, secs = run_saved(qid)
        m1, m2 = st.columns(2)
        m1.metric("Rows returned", f"{len(df):,}")
        m2.metric("Execution time", f"{secs * 1000:.0f} ms")
        if df.empty:
            st.warning("Query ran successfully but returned no rows for the current data.")
        else:
            st.dataframe(df, hide_index=True, use_container_width=True)
            st.download_button(
                "⬇️ Download CSV",
                df.to_csv(index=False).encode("utf-8"),
                file_name=f"q{qid}_results.csv",
                mime="text/csv",
            )
    except Exception as exc:
        st.error(f"Query failed: {exc}")

    st.divider()
    if st.button("✅ Run all 25 queries (validation)"):
        results = []
        for item in QUERIES:
            try:
                df_all, secs_all = run_saved(item["id"])
                results.append(
                    {
                        "Q": item["id"],
                        "title": item["title"],
                        "rows": len(df_all),
                        "ms": round(secs_all * 1000),
                        "status": "OK" if len(df_all) else "EMPTY",
                    }
                )
            except Exception as exc:
                results.append(
                    {
                        "Q": item["id"],
                        "title": item["title"],
                        "rows": 0,
                        "ms": 0,
                        "status": f"ERROR: {str(exc)[:80]}",
                    }
                )
        st.dataframe(pd.DataFrame(results), hide_index=True, use_container_width=True)

# ---------------- Custom SQL ----------------
with tab_custom:
    st.caption(
        "Read-only: SELECT / WITH only, 15-second timeout. "
        "Tables: teams, venues, players, series, matches, batting_innings, "
        "bowling_innings, fielding, player_career_stats."
    )
    sql = st.text_area(
        "SQL", height=180, value="SELECT format, COUNT(*) AS matches\nFROM matches\nGROUP BY format;"
    )
    if st.button("▶️ Run query", type="primary"):
        try:
            start = time.perf_counter()
            result = run_readonly(sql)
            st.caption(f"{len(result):,} rows · {(time.perf_counter() - start) * 1000:.0f} ms")
            st.dataframe(result, hide_index=True, use_container_width=True)
        except Exception as exc:
            st.error(str(exc))
