"""Regression test for DBIP #3785: __meta_categories preserves defaultSorting.

Creates the real SQLite table via build_meta_tables(), inserts an agents
row carrying defaultSorting=rank and an API row without it, then reads the
values back. Fails on upstream (column missing); passes with the fix.
"""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from create_sqlite import build_meta_tables, insert_batch, Table, Column


def test_default_sorting_roundtrip():
    conn = sqlite3.connect(":memory:")
    tables = build_meta_tables()
    cats = next(t for t in tables if t.name == "__meta_categories")
    conn.execute(cats.create_sql())

    insert_batch(
        conn,
        cats,
        [{"network": "global", "key": "agents", "position": 0, "defaultSorting": "rank"}],
    )
    insert_batch(
        conn,
        cats,
        [{"network": "global", "key": "apis", "position": 1}],  # no setting -> SQL NULL
    )

    row_agents = conn.execute(
        'SELECT "defaultSorting" FROM "__meta_categories" WHERE "key" = ?',
        ("agents",),
    ).fetchone()
    row_apis = conn.execute(
        'SELECT "defaultSorting" FROM "__meta_categories" WHERE "key" = ?',
        ("apis",),
    ).fetchone()

    assert row_agents is not None and row_agents[0] == "rank", f"got {row_agents}"
    assert row_apis is not None and row_apis[0] is None, f"got {row_apis}"
    conn.close()


if __name__ == "__main__":
    test_default_sorting_roundtrip()
    print("PASS: defaultSorting preserved (rank) / NULL when absent")