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
NPM_HOSTS = {"npmjs.com", "www.npmjs.com", "registry.npmjs.org"}

URL_RE = re.compile(r"https?://[^\s\)\"\']+")
MD_LINK_RE = re.compile(r"\[[^\]]*\]\((https?://[^)]+)\)")

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


def extract_urls_from_string(s: str) -> List[str]:
    if not s:
        return []
    urls: List[str] = []
    for m in MD_LINK_RE.findall(s):
        urls.append(m.rstrip(").,;]"))
    for m in URL_RE.findall(s):
        urls.append(m.rstrip(").,;]"))
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


def normalize_github_repo(url: str) -> Optional[str]:
    p = urllib.parse.urlparse(url)
    if p.netloc not in GITHUB_HOSTS:
        return None
    parts = [x for x in p.path.split("/") if x]
    if len(parts) < 2:
        return None
    return f"{parts[0]}/{parts[1].removesuffix('.git')}"


def has_github_repo(urls: List[str]) -> bool:
    return any(normalize_github_repo(u) for u in urls)


def normalize_npm_package(url: str) -> Optional[str]:
    p = urllib.parse.urlparse(url)
    if p.netloc not in NPM_HOSTS:
        return None

    if p.netloc == "registry.npmjs.org":
        path = p.path.lstrip("/")
        return urllib.parse.unquote(path) if path else None

    parts = [x for x in p.path.split("/") if x]
    if len(parts) < 2 or parts[0] != "package":
        return None
    if parts[1].startswith("@") and len(parts) >= 3:
        return f"{parts[1]}/{parts[2]}"
    return parts[1]


def choose_npm_package(urls: List[str]) -> Optional[str]:
    for u in urls:
        pkg = normalize_npm_package(u)
        if pkg:
            return pkg
    return None


def is_stable_npm_version(v: str) -> bool:
    if not v:
        return False
    s = v.strip()
    if PRERELEASE_KEYWORDS_RE.search(s):
        return False
    if "-" in s:
        return False
    s = s[1:] if s.startswith("v") else s
    s = s.split("+", 1)[0]
    parts = s.split(".")
    if len(parts) < 2 or len(parts) > 4:
        return False
    try:
        [int(x) for x in parts]
        return True
    except Exception:
        return False


def semver_key(v: str) -> Optional[Tuple[int, int, int, int]]:
    if not is_stable_npm_version(v):
        return None
    s = v[1:] if v.startswith("v") else v
    s = s.split("+", 1)[0]
    nums = [int(x) for x in s.split(".")]
    while len(nums) < 4:
        nums.append(0)
    return tuple(nums[:4])


# ---- HTTP + NPM ----

class Http:
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session = requests.Session()

    def get_json(self, url: str, headers: Optional[Dict[str, str]] = None):
        r = self.session.get(url, headers=headers or {}, timeout=self.timeout)
        if r.status_code == 204:
            return r.status_code, None
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, None


class Npm:
    def __init__(self, http: Http):
        self.http = http

    def package(self, name: str) -> Optional[dict]:
        enc = urllib.parse.quote(name, safe="@/")
        st, js = self.http.get_json(f"https://registry.npmjs.org/{enc}")
        return js if st == 200 and isinstance(js, dict) else None


def pick_latest_stable_version(pkg: dict) -> Optional[str]:
    dist = pkg.get("dist-tags") or {}
    latest = dist.get("latest")
    if isinstance(latest, str) and is_stable_npm_version(latest):
        return latest

    versions = pkg.get("versions")
    if not isinstance(versions, dict):
        return None

    best_v = None
    best_k = None
    for v in versions.keys():
        k = semver_key(v)
        if k and (best_k is None or k > best_k):
            best_k = k
            best_v = v
    return best_v


def normalize_npm_license(lic: Any) -> Optional[str]:
    if isinstance(lic, str) and lic.strip():
        return lic.strip()
    if isinstance(lic, dict):
        for k in ("type", "name"):
            v = lic.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
    return None


def compute_from_npm(npm: Npm, pkg: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    js = npm.package(pkg)
    if not js:
        return out

    v = pick_latest_stable_version(js)
    if v:
        out["latestKnownVersion"] = v
        t = (js.get("time") or {}).get(v)
        dt = parse_iso_datetime(t) if isinstance(t, str) else None
        if dt:
            out["latestKnownReleaseDate"] = iso_date(dt)

    maintainers = js.get("maintainers")
    if isinstance(maintainers, list) and maintainers:
        m = maintainers[0] or {}
        if isinstance(m, dict):
            name = m.get("name")
            email = m.get("email")
            if isinstance(name, str) and isinstance(email, str):
                out["maintainer"] = f"{name} <{email}>"
            elif isinstance(name, str):
                out["maintainer"] = name

    lic = normalize_npm_license(js.get("license"))
    if lic:
        out["license"] = lic

    return out


# ---- Main ----

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--jsonfile",
        required=True,
        help='JSON file name without .json, or "all" to process all files',
    )
    ap.add_argument("--json-dir", default="json")
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

    http = Http()
    npm = Npm(http)

    total_scanned = total_updated = 0
    total_skipped_gh = total_matched = 0

    for path in paths:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        sdks = data.get("sdks")
        if not isinstance(sdks, list):
            print(f"ERROR: {path} has no 'sdks' list", file=sys.stderr)
            continue

        scanned = updated = skipped_gh = matched = 0

        for sdk in sdks:
            if not isinstance(sdk, dict):
                continue
            scanned += 1

            urls = collect_urls(sdk)
            if has_github_repo(urls):
                skipped_gh += 1
                continue

            pkg = choose_npm_package(urls)
            if not pkg:
                continue
            matched += 1

            try:
                meta = compute_from_npm(npm, pkg)
            except requests.RequestException as e:
                print(f"WARN: fetch failed for npm:{pkg}: {e}", file=sys.stderr)
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
        print(f"SDKs with GitHub link (skipped): {skipped_gh}")
        print(f"SDKs with npm link (eligible): {matched}")
        print(f"SDKs updated: {updated}")

        total_scanned += scanned
        total_updated += updated
        total_skipped_gh += skipped_gh
        total_matched += matched

    if len(paths) > 1:
        print("\n=== Overall summary ===")
        print(f"SDKs scanned: {total_scanned}")
        print(f"SDKs with GitHub link (skipped): {total_skipped_gh}")
        print(f"SDKs with npm link (eligible): {total_matched}")
        print(f"SDKs updated: {total_updated}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
