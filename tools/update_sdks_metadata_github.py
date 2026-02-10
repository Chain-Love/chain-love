#!/usr/bin/env python3
import argparse
import json
import os
import re
import sys
import urllib.parse
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests


# ---- Config / patterns ----

GITHUB_HOSTS = {"github.com", "www.github.com"}

URL_RE = re.compile(r"https?://[^\s\)\"\']+")
MD_LINK_RE = re.compile(r"\[[^\]]*\]\((https?://[^)]+)\)")

STABLE_TAG_RE = re.compile(r"^v?\d+(?:\.\d+){1,3}(?:\+[0-9A-Za-z.-]+)?$")
PRERELEASE_KEYWORDS_RE = re.compile(
    r"(?i)\b(alpha|beta|rc|pre|preview|dev|snapshot|nightly|canary)\b"
)


# ---- Helpers ----

def iso_date(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).date().isoformat()


def parse_iso_datetime(s: str) -> Optional[datetime]:
    if not s:
        return None
    try:
        if s.endswith("Z"):
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        return datetime.fromisoformat(s)
    except Exception:
        return None


def is_stable_release_tag(tag: str) -> bool:
    if not tag:
        return False
    t = tag.strip()
    if PRERELEASE_KEYWORDS_RE.search(t):
        return False
    if "-" in t:
        return False
    return bool(STABLE_TAG_RE.match(t))


def normalize_github_repo(url: str) -> Optional[str]:
    p = urllib.parse.urlparse(url)
    if p.netloc not in GITHUB_HOSTS:
        return None
    parts = [x for x in p.path.split("/") if x]
    if len(parts) < 2:
        return None
    return f"{parts[0]}/{parts[1].removesuffix('.git')}"


def extract_urls_from_string(s: str) -> List[str]:
    if not s:
        return []
    urls = []
    urls.extend(m.rstrip(").,;]") for m in MD_LINK_RE.findall(s))
    urls.extend(m.rstrip(").,;]") for m in URL_RE.findall(s))
    return dedupe(urls)


def collect_urls(obj: Any) -> List[str]:
    if obj is None:
        return []
    if isinstance(obj, str):
        return extract_urls_from_string(obj)
    if isinstance(obj, list):
        out: List[str] = []
        for x in obj:
            out.extend(collect_urls(x))
        return dedupe(out)
    if isinstance(obj, dict):
        out: List[str] = []
        for v in obj.values():
            out.extend(collect_urls(v))
        return dedupe(out)
    return []


def dedupe(items: List[str]) -> List[str]:
    seen = set()
    out = []
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def choose_github_repo(urls: List[str]) -> Optional[str]:
    for u in urls:
        gh = normalize_github_repo(u)
        if gh:
            return gh
    return None


# ---- HTTP + GitHub API ----

class Http:
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session = requests.Session()

    def get_json(self, url: str, headers: Optional[Dict[str, str]] = None) -> Tuple[int, Optional[object]]:
        r = self.session.get(url, headers=headers or {}, timeout=self.timeout)
        if r.status_code == 204:
            return r.status_code, None
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, None


class GitHub:
    def __init__(self, token: Optional[str], http: Http):
        self.http = http
        self.headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "sdks-metadata-updater",
        }
        if token:
            self.headers["Authorization"] = f"Bearer {token}"

    def repo(self, full: str) -> Optional[dict]:
        st, js = self.http.get_json(f"https://api.github.com/repos/{full}", headers=self.headers)
        return js if st == 200 and isinstance(js, dict) else None

    def releases(self, full: str, per_page: int = 100) -> List[dict]:
        st, js = self.http.get_json(
            f"https://api.github.com/repos/{full}/releases?per_page={per_page}",
            headers=self.headers,
        )
        if st == 200 and isinstance(js, list):
            return [x for x in js if isinstance(x, dict)]
        return []


def pick_latest_stable_release(releases: List[dict]) -> Optional[dict]:
    for r in releases:
        if r.get("draft") or r.get("prerelease"):
            continue
        tag = (r.get("tag_name") or "").strip()
        if is_stable_release_tag(tag):
            return r
    return None


def compute_from_github(gh: GitHub, full: str) -> Dict[str, str]:
    out: Dict[str, str] = {}

    repo = gh.repo(full)
    if not repo:
        return out

    owner = repo.get("owner") or {}
    if owner.get("login"):
        out["maintainer"] = owner["login"]

    lic = repo.get("license")
    if isinstance(lic, dict):
        spdx = lic.get("spdx_id")
        name = lic.get("name")
        if spdx and spdx != "NOASSERTION":
            out["license"] = spdx
        elif name:
            out["license"] = name

    rel = pick_latest_stable_release(gh.releases(full))
    if not rel:
        return out

    tag = rel.get("tag_name")
    published = rel.get("published_at") or rel.get("created_at")

    if tag:
        out["latestKnownVersion"] = tag

    dt = parse_iso_datetime(published) if published else None
    if dt:
        out["latestKnownReleaseDate"] = iso_date(dt)

    return out


# ---- Main ----

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--jsonfile",
        required=True,
        help='JSON file name without .json, or "all" to process all files',
    )
    ap.add_argument("--json-dir", default="json", help="Directory containing blockchain JSON files")
    args = ap.parse_args()

    if args.jsonfile == "all":
        paths = [
            os.path.join(args.json_dir, f)
            for f in os.listdir(args.json_dir)
            if f.endswith(".json") and os.path.isfile(os.path.join(args.json_dir, f))
        ]
        if not paths:
            print(f"ERROR: no json files found in {args.json_dir}", file=sys.stderr)
            return 2
    else:
        path = os.path.join(args.json_dir, f"{args.jsonfile}.json")
        if not os.path.isfile(path):
            print(f"ERROR: file not found: {path}", file=sys.stderr)
            return 2
        paths = [path]

    gh_token = os.getenv("GITHUB_TOKEN")
    http = Http()
    gh = GitHub(gh_token, http)

    total_scanned = 0
    total_updated = 0

    for path in paths:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        sdks = data.get("sdks")
        if not isinstance(sdks, list):
            print(f"ERROR: {path} has no 'sdks' list", file=sys.stderr)
            continue

        scanned = 0
        updated = 0

        for sdk in sdks:
            if not isinstance(sdk, dict):
                continue
            scanned += 1

            urls = collect_urls(sdk)
            repo_full = choose_github_repo(urls)
            if not repo_full:
                continue

            try:
                meta = compute_from_github(gh, repo_full)
            except requests.RequestException as e:
                print(f"WARN: fetch failed for github:{repo_full}: {e}", file=sys.stderr)
                continue

            if not meta:
                continue

            changed = False
            for k, v in meta.items():
                if v and sdk.get(k) != v:
                    sdk[k] = v
                    changed = True

            if changed:
                updated += 1

        with open(path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
            f.write("\n")

        print(f"File: {path}")
        print(f"SDKs scanned: {scanned}")
        print(f"SDKs updated: {updated}")

        total_scanned += scanned
        total_updated += updated

    if len(paths) > 1:
        print("\n=== Overall summary ===")
        print(f"SDKs scanned: {total_scanned}")
        print(f"SDKs updated: {total_updated}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
