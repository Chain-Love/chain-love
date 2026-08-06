#!/usr/bin/env python3

import os
import json
from pathlib import Path

RELEASE_ASSETS_DIR = "release-assets"
OUTPUT_FILE = os.path.join(RELEASE_ASSETS_DIR, "release-index.json")

GITHUB_REPOSITORY = os.environ.get("GITHUB_REPOSITORY")
RELEASE_TAG = os.environ.get("RELEASE_TAG")  # must be passed from workflow

if not GITHUB_REPOSITORY:
    raise ValueError("GITHUB_REPOSITORY is not set")

if not RELEASE_TAG:
    raise ValueError("RELEASE_TAG is not set")

base_url = f"https://github.com/{GITHUB_REPOSITORY}/releases/download/{RELEASE_TAG}"

assets = []

for path in sorted(Path(RELEASE_ASSETS_DIR).iterdir()):
    if not path.is_file():
        continue

    name = path.name

    # avoid self-inclusion if re-run
    if name == os.path.basename(OUTPUT_FILE):
        continue

    assets.append({
        "name": name,
        "browser_download_url": f"{base_url}/{name}",
    })

index = {
    "assets": assets
}

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(index, f, indent=2)

print(f"Generated {OUTPUT_FILE} with {len(assets)} assets")
