from __future__ import annotations

import json
import sqlite3
import tarfile
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple, TypedDict, Union, cast, Iterator

# =========================
# CONFIG
# =========================

SCHEMA_FILE = "schema.json"
DATA_DIR = Path("json")
OUTPUT_DB_NAME = "app.db"
BATCH_SIZE = 1000

# =========================
# TYPES
# =========================

JSONScalar = Union[str, int, float, bool, None]

JSONSchemaProperty = TypedDict(
    "JSONSchemaProperty",
    {
        "type": Union[str, List[str]],
        "items": "JSONSchemaProperty",
        "properties": Dict[str, "JSONSchemaProperty"],
        "$ref": str,
    },
    total=False,
)

JSONSchemaRoot = TypedDict(
    "JSONSchemaRoot",
    {
        "properties": Dict[str, JSONSchemaProperty],
        "$defs": Dict[str, JSONSchemaProperty],
    },
    total=False,
)

# =========================
# AST
# =========================

@dataclass(frozen=True)
class Column:
    name: str
    type: str
    nullable: bool


@dataclass(frozen=True)
class Table:
    name: str
    columns: List[Column]

    def create_sql(self) -> str:
        cols = ",\n  ".join(
            f'"{c.name}" {c.type}{"" if c.nullable else " NOT NULL"}'
            for c in self.columns
        )
        return f"CREATE TABLE IF NOT EXISTS {self.name} (\n  {cols}\n);"

    def index_sql(self) -> List[str]:
        return [
            f'CREATE INDEX IF NOT EXISTS idx_{self.name}_{col.name} '
            f'ON {self.name} ("{col.name}");'
            for col in self.columns
        ]

# =========================
# SCHEMA
# =========================

def load_schema() -> JSONSchemaRoot:
    with open(SCHEMA_FILE, "r") as f:
        return cast(JSONSchemaRoot, json.load(f))


def resolve_type(prop: JSONSchemaProperty) -> Tuple[str, bool]:
    t = prop.get("type")

    if isinstance(t, list):
        nullable = "null" in t
        base = next((x for x in t if x != "null"), "string")
    else:
        nullable = False
        base = t

    if base == "string":
        return "TEXT", nullable
    if base == "integer":
        return "INTEGER", nullable
    if base == "number":
        return "REAL", nullable
    if base == "boolean":
        return "INTEGER", False
    if base == "array":
        return "TEXT", True

    return "TEXT", True


def extract_ref_name(prop: JSONSchemaProperty) -> str | None:
    ref = prop.get("$ref")
    if not ref:
        return None
    return ref.split("/")[-1]


def build_tables(schema: JSONSchemaRoot) -> List[Table]:
    tables: List[Table] = []
    defs = schema.get("$defs", {})

    for _, prop in schema["properties"].items():
        if prop.get("type") != "array":
            continue

        ref = extract_ref_name(prop.get("items", {}))
        if not ref:
            continue

        def_schema = defs.get(ref)
        if not def_schema:
            continue

        cols: List[Column] = [Column("network", "TEXT", False)]

        for col_name, col_schema in def_schema.get("properties", {}).items():
            col_type, nullable = resolve_type(col_schema)
            cols.append(Column(col_name, col_type, nullable))

        tables.append(Table(ref, cols))

    return tables


def build_meta_tables() -> List[Table]:
    return [
        Table(
            "__meta_categories",
            [
                Column("network", "TEXT", False),
                Column("key", "TEXT", False),
                Column("label", "TEXT", True),
                Column("icon", "TEXT", True),
                Column("description", "TEXT", True),
                Column("columns_order", "TEXT", True),
            ],
        ),
        Table(
            "__meta_columns",
            [
                Column("network", "TEXT", False),
                Column("key", "TEXT", False),
                Column("label", "TEXT", True),
                Column("icon", "TEXT", True),
                Column("description", "TEXT", True),
                Column("filter", "TEXT", True),
                Column("sorting", "TEXT", True),
                Column("pinning", "TEXT", True),
                Column("cellType", "TEXT", True),
                Column("group", "TEXT", True),
            ],
        ),
        Table(
            "__meta_providers",
            [
                Column("network", "TEXT", False),
                Column("slug", "TEXT", False),
                Column("name", "TEXT", True),
                Column("logoPath", "TEXT", True),
                Column("description", "TEXT", True),
                Column("website", "TEXT", True),
                Column("docs", "TEXT", True),
                Column("x", "TEXT", True),
                Column("github", "TEXT", True),
                Column("discord", "TEXT", True),
                Column("telegram", "TEXT", True),
                Column("linkedin", "TEXT", True),
                Column("supportEmail", "TEXT", True),
                Column("starred", "INTEGER", True),
                Column("tag", "TEXT", True),
                Column("categories", "TEXT", True),
                Column("key", "TEXT", True),
            ],
        ),
    ]

# =========================
# NDJSON
# =========================

def stream_ndjson(file_obj) -> Iterator[Dict]:
    for line in file_obj:
        if line.strip():
            yield json.loads(line)


def normalize_value(v):
    if isinstance(v, (list, dict)):
        return json.dumps(v)
    if isinstance(v, bool):
        return int(v)
    return v

# =========================
# INSERT
# =========================

def insert_batch(conn: sqlite3.Connection, table: Table, rows: List[Dict]):
    if not rows:
        return

    cols = [c.name for c in table.columns]
    placeholders = ",".join(["?"] * len(cols))

    quoted_cols = ",".join(f'"{c}"' for c in cols)
    sql = f'INSERT INTO {table.name} ({quoted_cols}) VALUES ({placeholders})'

    values = [
        [normalize_value(row.get(col)) for col in cols]
        for row in rows
    ]

    conn.executemany(sql, values)

# =========================
# DB INIT
# =========================

def init_db(conn: sqlite3.Connection, tables: List[Table]):
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = OFF;")

    for table in tables:
        conn.execute(table.create_sql())

    for table in tables:
        for idx_sql in table.index_sql():
            conn.execute(idx_sql)

# =========================
# COMPRESSION
# =========================

def compress_db(db_path: Path, output_dir: Path):
    archive_path = (output_dir / f"{db_path.name}.tar.gz").resolve()
    archive_path.unlink(missing_ok=True)

    subprocess.run(
        ["tar", "-czf", str(archive_path), db_path.name],
        cwd=db_path.parent,
        check=True,
    )

# =========================
# MAIN
# =========================

def main():
    schema = load_schema()
    tables = build_tables(schema) + build_meta_tables()
    table_map = {t.name: t for t in tables}

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp_dir_name:
        tmp_dir = Path(tmp_dir_name)

        # global DB
        global_db_path = tmp_dir / OUTPUT_DB_NAME
        global_conn = sqlite3.connect(global_db_path)
        init_db(global_conn, tables)

        # per-network DBs
        network_conns: Dict[str, sqlite3.Connection] = {}

        def get_network_conn(network: str) -> sqlite3.Connection:
            if network not in network_conns:
                path = tmp_dir / f"{network}.db"
                conn = sqlite3.connect(path)
                init_db(conn, tables)
                network_conns[network] = conn
            return network_conns[network]

        # process archives once
        for archive in DATA_DIR.glob("*-ndjson.tar.gz"):
            network = archive.name.replace("-ndjson.tar.gz", "")
            print(f"Processing {network}")

            with tarfile.open(archive, "r:gz") as tar:

                # --- collect columns/*.json ---
                columns_map: Dict[str, List[str]] = {}
                for member in tar.getmembers():
                    if member.name.startswith("columns/") and member.name.endswith(".json"):
                        f = tar.extractfile(member)
                        if not f:
                            continue
                        category = Path(member.name).stem
                        columns_map[category] = json.load(f)

                # --- process meta/*.ndjson ---
                meta_tables = {
                    "categories": table_map["__meta_categories"],
                    "columns": table_map["__meta_columns"],
                    "providers": table_map["__meta_providers"],
                }

                for member in tar.getmembers():
                    if not member.name.startswith("meta/") or not member.name.endswith(".ndjson"):
                        continue

                    name = Path(member.name).stem
                    table = meta_tables.get(name)
                    if not table:
                        continue

                    f = tar.extractfile(member)
                    if not f:
                        continue

                    batch_global: List[Dict] = []
                    batch_network: List[Dict] = []

                    for obj in stream_ndjson(f):
                        obj["network"] = network

                        if name == "categories":
                            key = obj.get("key")
                            if key and key in columns_map:
                                obj["columns_order"] = columns_map[key]

                        batch_global.append(obj)
                        batch_network.append(obj)

                        if len(batch_global) >= BATCH_SIZE:
                            insert_batch(global_conn, table, batch_global)
                            insert_batch(get_network_conn(network), table, batch_network)
                            batch_global.clear()
                            batch_network.clear()

                    insert_batch(global_conn, table, batch_global)
                    insert_batch(get_network_conn(network), table, batch_network)

                # --- process data tables ---
                for member in tar.getmembers():
                    if not member.name.endswith(".ndjson") or member.name.startswith("meta/"):
                        continue

                    table_name = Path(member.name).name.replace(".ndjson", "")
                    table = table_map.get(table_name)
                    if not table:
                        continue

                    f = tar.extractfile(member)
                    if not f:
                        continue

                    batch_global: List[Dict] = []
                    batch_network: List[Dict] = []

                    for obj in stream_ndjson(f):
                        obj["network"] = network

                        batch_global.append(obj)
                        batch_network.append(obj)

                        if len(batch_global) >= BATCH_SIZE:
                            insert_batch(global_conn, table, batch_global)
                            insert_batch(get_network_conn(network), table, batch_network)
                            batch_global.clear()
                            batch_network.clear()

                    insert_batch(global_conn, table, batch_global)
                    insert_batch(get_network_conn(network), table, batch_network)

            global_conn.commit()
            get_network_conn(network).commit()

        # close before compression
        global_conn.close()
        for conn in network_conns.values():
            conn.close()

        # compress into json/
        compress_db(global_db_path, DATA_DIR)

        for network in network_conns.keys():
            compress_db(tmp_dir / f"{network}.db", DATA_DIR)


if __name__ == "__main__":
    main()
