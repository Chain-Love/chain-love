from __future__ import annotations

import sqlite3
import unittest

from create_sqlite import build_tables, insert_batch


def build_table(properties: dict, required: list[str]):
    schema = {
        "properties": {
            "records": {
                "type": "array",
                "items": {"$ref": "#/$defs/records"},
            }
        },
        "$defs": {
            "records": {
                "type": "object",
                "properties": properties,
                "required": required,
            }
        },
    }
    return build_tables(schema)[0]


class BuildTablesNullabilityTests(unittest.TestCase):
    def test_optional_scalar_accepts_missing_value(self):
        table = build_table(
            {
                "slug": {"type": "string"},
                "creator": {"type": "string"},
            },
            ["slug"],
        )

        columns = {column.name: column for column in table.columns}
        self.assertFalse(columns["slug"].nullable)
        self.assertTrue(columns["creator"].nullable)

        conn = sqlite3.connect(":memory:")
        conn.execute(table.create_sql())
        insert_batch(conn, table, [{"network": "base", "slug": "agent-1"}])

        self.assertEqual(
            conn.execute('SELECT "creator" FROM records').fetchone(),
            (None,),
        )

    def test_required_nullable_boolean_accepts_null(self):
        table = build_table(
            {"active": {"type": ["boolean", "null"]}},
            ["active"],
        )

        active = next(column for column in table.columns if column.name == "active")
        self.assertTrue(active.nullable)

    def test_required_array_is_not_nullable(self):
        table = build_table(
            {"tags": {"type": "array", "items": {"type": "string"}}},
            ["tags"],
        )

        tags = next(column for column in table.columns if column.name == "tags")
        self.assertFalse(tags.nullable)


if __name__ == "__main__":
    unittest.main()
