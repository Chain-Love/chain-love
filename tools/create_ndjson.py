from __future__ import annotations

import os
import json
import tarfile
import io
from typing import Dict, List, Union, cast

# --- JSON types ---
JSONPrimitive = Union[str, int, float, bool, None]
JSONValue = Union[JSONPrimitive, Dict[str, "JSONValue"], List["JSONValue"]]

CategoryItems = List[Dict[str, JSONValue]]
NetworkData = Dict[str, CategoryItems]

ColumnsMap = Dict[str, List[str]]
MetaMap = Dict[str, List[Dict[str, JSONValue]]]

RawRoot = Dict[str, JSONValue]

JSON_DIR: str = "./json"


def load_raw_json(path: str) -> RawRoot:
    with open(path, "r") as f:
        raw: JSONValue = json.load(f)

    if not isinstance(raw, dict):
        raise ValueError(f"Invalid JSON root in {path}, expected object")

    return cast(RawRoot, raw)


def extract_data(raw: RawRoot) -> NetworkData:
    result: NetworkData = {}

    for k, v in raw.items():
        if k in ("columns", "meta"):
            continue

        if not isinstance(v, list):
            continue

        items: CategoryItems = []
        for item in v:
            if isinstance(item, dict):
                items.append(cast(Dict[str, JSONValue], item))

        result[k] = items

    return result


def extract_columns(raw: RawRoot) -> ColumnsMap:
    columns_raw = raw.get("columns")
    if not isinstance(columns_raw, dict):
        return {}

    result: ColumnsMap = {}

    for k, v in columns_raw.items():
        if isinstance(k, str) and isinstance(v, list): # type: ignore
            cols: List[str] = []
            for col in v:
                if isinstance(col, str):
                    cols.append(col)
            result[k] = cols

    return result


def extract_meta(raw: RawRoot) -> MetaMap:
    meta_raw = raw.get("meta")
    if not isinstance(meta_raw, dict):
        return {}

    result: MetaMap = {}

    for meta_key, value in meta_raw.items():
        if not isinstance(meta_key, str):  # type: ignore
            continue

        rows: List[Dict[str, JSONValue]] = []

        # dict → flatten
        if isinstance(value, dict):
            for k, v in value.items():
                if isinstance(k, str) and isinstance(v, dict):  # type: ignore
                    item: Dict[str, JSONValue] = dict(v)
                    item["key"] = k
                    rows.append(item)

        # list → pass through
        elif isinstance(value, list):
            for item in value:  # type: ignore
                if isinstance(item, dict):  # type: ignore
                    rows.append(item)

        if rows:
            result[meta_key] = rows

    return result


def write_ndjson_file(
    tar: tarfile.TarFile,
    name: str,
    items: List[Dict[str, JSONValue]],
) -> None:
    buffer = io.BytesIO()

    for item in items:
        line = json.dumps(item, separators=(",", ":")) + "\n"
        buffer.write(line.encode("utf-8"))

    size = buffer.tell()
    buffer.seek(0)

    tarinfo = tarfile.TarInfo(name=name)
    tarinfo.size = size
    tar.addfile(tarinfo, buffer)


def write_json_file(
    tar: tarfile.TarFile,
    name: str,
    obj: Union[List[str], Dict[str, JSONValue]],
) -> None:
    data = json.dumps(obj, separators=(",", ":")).encode("utf-8")

    tarinfo = tarfile.TarInfo(name=name)
    tarinfo.size = len(data)
    tar.addfile(tarinfo, io.BytesIO(data))


def write_tar(network: str, raw: RawRoot) -> None:
    tar_path: str = os.path.join(JSON_DIR, f"{network}-ndjson.tar.gz")

    data: NetworkData = extract_data(raw)
    columns: ColumnsMap = extract_columns(raw)
    meta: MetaMap = extract_meta(raw)

    with tarfile.open(tar_path, "w:gz", compresslevel=9) as tar:

        # --- DATA ---
        for category, items in data.items():
            write_ndjson_file(tar, f"{category}.ndjson", items)

        # --- COLUMNS ---
        for category, cols in columns.items():
            write_json_file(tar, f"columns/{category}.json", cols)

        # --- META ---
        for meta_key, rows in meta.items():
            write_ndjson_file(tar, f"meta/{meta_key}.ndjson", rows)

    print(f"Created {tar_path}")


def main() -> None:
    for filename in os.listdir(JSON_DIR):
        if not filename.endswith(".json"):
            continue

        network: str = filename[:-5]
        path: str = os.path.join(JSON_DIR, filename)

        raw: RawRoot = load_raw_json(path)
        write_tar(network, raw)


if __name__ == "__main__":
    main()
