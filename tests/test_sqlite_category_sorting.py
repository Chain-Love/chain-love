import sqlite3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from create_sqlite import build_meta_tables, insert_batch


class CategorySortingTests(unittest.TestCase):
    def test_default_sorting_survives_sqlite_projection(self):
        table = next(t for t in build_meta_tables() if t.name == "__meta_categories")
        with sqlite3.connect(":memory:") as conn:
            conn.execute(table.create_sql())
            insert_batch(conn, table, [
                {"network": "algorand", "key": "agents", "label": "Agents",
                 "defaultSorting": "rank", "position": 0},
                {"network": "algorand", "key": "apis", "label": "APIs",
                 "position": 1},
            ])
            columns = {row[1] for row in conn.execute("PRAGMA table_info(__meta_categories)")}
            self.assertIn("defaultSorting", columns)
            rows = conn.execute(
                'SELECT key, "defaultSorting" FROM __meta_categories ORDER BY position'
            ).fetchall()
            self.assertEqual(rows, [("agents", "rank"), ("apis", None)])


if __name__ == "__main__":
    unittest.main()
