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

JSON_DIR: str = "./json"


def load_network_json(path: str) -> NetworkData:
    with open(path, "r") as f:
        raw: JSONValue = json.load(f)

    if not isinstance(raw, dict):
        raise ValueError(f"Invalid JSON root in {path}, expected object")

    result: NetworkData = {}

    for k, v in raw.items():
        if not isinstance(v, list):
            continue

        # ensure list of dicts
        items: CategoryItems = []
        for item in v:
            if isinstance(item, dict):
                items.append(cast(Dict[str, JSONValue], item))

        result[k] = items

    return result


def write_tar(network: str, data: NetworkData) -> None:
    tar_path: str = os.path.join(JSON_DIR, f"{network}.ndjson.tar")

    with tarfile.open(tar_path, "w") as tar:
        for category, items in data.items():
            buffer: io.BytesIO = io.BytesIO()

            for item in items:
                line: str = json.dumps(item, separators=(",", ":")) + "\n"
                buffer.write(line.encode("utf-8"))

            size: int = buffer.tell()
            buffer.seek(0)

            tarinfo: tarfile.TarInfo = tarfile.TarInfo(
                name=f"{category}.ndjson"
            )
            tarinfo.size = size

            tar.addfile(tarinfo, buffer)

    print(f"Created {tar_path}")


def main() -> None:
    for filename in os.listdir(JSON_DIR):
        if not filename.endswith(".json"):
            continue

        network: str = filename[:-5]
        path: str = os.path.join(JSON_DIR, filename)

        data: NetworkData = load_network_json(path)
        write_tar(network, data)


if __name__ == "__main__":
    main()