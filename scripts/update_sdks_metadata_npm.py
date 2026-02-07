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

# Reject prerelease markers anywhere (practical)
PRERELEASE_KEYWORDS_RE = re.compile(
    r"(?i)\b(alpha|beta|rc|pre|preview|dev|snapshot|nightly|canary)\b"
)


# ---- Helpers ----

def iso_date(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).date().isoformat()


def parse_iso_datetime(s: str) -> Optional[datetime]:
    if not s:
        return None
    s = s.strip()
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
        for item in obj:
            out.extend(collect_urls(item))
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
    owner = parts[0]
    repo = parts[1].removesuffix(".git")
    return f"{owner}/{repo}"


def has_github_repo(urls: List[str]) -> bool:
    # github > npm: if any GitHub repo link exists, the npm script must skip this SDK entry
    for u in urls:
        if normalize_github_repo(u):
            return True
    return False


def normalize_npm_package(url: str) -> Optional[str]:
    """
    Accept:
      - https://www.npmjs.com/package/name
      - https://www.npmjs.com/package/@scope/name
      - https://registry.npmjs.org/name
      - https://registry.npmjs.org/@scope%2fname
    """
    p = urllib.parse.urlparse(url)
    if p.netloc not in NPM_HOSTS:
        return None

    if p.netloc == "registry.npmjs.org":
        path = p.path.lstrip("/")
        if not path:
            return None
        return urllib.parse.unquote(path)

    # npmjs.com/package/<name> or /package/@scope/name
    parts = [x for x in p.path.split("/") if x]
    if len(parts) < 2 or parts[0] != "package":
        return None
    if parts[1].startswith("@") and len(parts) >= 3:
        return f"{parts[1]}/{parts[2]}"
    return parts[1]


def choose_npm_package(urls: List[str]) -> Optional[str]:
    # pick first npm link encountered
    for u in urls:
        pkg = normalize_npm_package(u)
        if pkg:
            return pkg
    return None


def is_stable_npm_version(v: str) -> bool:
    """
    Stable = no '-' prerelease segment and no obvious prerelease keywords.
    NPM versions are typically semver like 1.2.3.
    """
    if not v:
        return False
    s = v.strip()

    if PRERELEASE_KEYWORDS_RE.search(s):
        return False
    if "-" in s:
        return False

    # Allow optional leading 'v' just in case
    s2 = s[1:] if s.startswith("v") else s

    # strip build metadata
    s2 = s2.split("+", 1)[0]
    parts = s2.split(".")
    if len(parts) < 2 or len(parts) > 4:
        return False
    try:
        _ = [int(x) for x in parts]
        return True
    except Exception:
        return False


def semver_key(v: str) -> Optional[Tuple[int, int, int, int]]:
    """
    Returns a comparable tuple for stable versions only.
    """
    if not is_stable_npm_version(v):
        return None
    s = v.strip()
    s = s[1:] if s.startswith("v") else s
    s = s.split("+", 1)[0]
    parts = [int(x) for x in s.split(".")]
    while len(parts) < 4:
        parts.append(0)
    return tuple(parts[:4])  # type: ignore


# ---- HTTP + NPM registry ----

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


class Npm:
    def __init__(self, http: Http):
        self.http = http

    def package(self, name: str) -> Optional[dict]:
        enc = urllib.parse.quote(name, safe="@/")
        st, js = self.http.get_json(f"https://registry.npmjs.org/{enc}")
        return js if st == 200 and isinstance(js, dict) else None


def pick_latest_stable_version(pkg_json: dict) -> Optional[str]:
    """
    Prefer dist-tags.latest if stable, otherwise pick the highest stable version
    from pkg_json["versions"] keys by numeric semver ordering.
    """
    dist = pkg_json.get("dist-tags") or {}
    latest = dist.get("latest")
    if isinstance(latest, str) and is_stable_npm_version(latest):
        return latest

    versions = pkg_json.get("versions")
    if not isinstance(versions, dict):
        return None

    best_v = None
    best_k = None
    for v in versions.keys():
        if not isinstance(v, str):
            continue
        k = semver_key(v)
        if k is None:
            continue
        if best_k is None or k > best_k:
            best_k = k
            best_v = v

    return best_v


def normalize_npm_license(lic_value: Any) -> Optional[str]:
    """
    NPM license can be string, dict, or rarely other shapes.
    """
    if isinstance(lic_value, str) and lic_value.strip():
        return lic_value.strip()
    if isinstance(lic_value, dict):
        t = lic_value.get("type")
        if isinstance(t, str) and t.strip():
            return t.strip()
        n = lic_value.get("name")
        if isinstance(n, str) and n.strip():
            return n.strip()
    return None


def compute_from_npm(npm: Npm, pkg: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    js = npm.package(pkg)
    if not js:
        return out

    stable_v = pick_latest_stable_version(js)
    if stable_v:
        out["latestKnownVersion"] = stable_v

        times = js.get("time") or {}
        if isinstance(times, dict) and stable_v in times:
            dt = parse_iso_datetime(times[stable_v])
            if dt:
                out["latestKnownReleaseDate"] = iso_date(dt)

    maintainers = js.get("maintainers")
    if isinstance(maintainers, list) and maintainers:
        m0 = maintainers[0] or {}
        if isinstance(m0, dict):
            name = m0.get("name")
            email = m0.get("email")
            if isinstance(name, str) and isinstance(email, str) and name.strip() and email.strip():
                out["maintainer"] = f"{name.strip()} <{email.strip()}>"
            elif isinstance(name, str) and name.strip():
                out["maintainer"] = name.strip()

    lic = normalize_npm_license(js.get("license"))
    if lic:
        out["license"] = lic

    return out


# ---- Main ----

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--blockchain", required=True, help="Blockchain name (expects json/<blockchain>.json)")
    ap.add_argument("--json-dir", default="json", help="Directory containing blockchain JSON files (default: json/)")
    args = ap.parse_args()

    path = os.path.join(args.json_dir, f"{args.blockchain}.json")
    if not os.path.isfile(path):
        print(f"ERROR: file not found: {path}", file=sys.stderr)
        return 2

    http = Http()
    npm = Npm(http)

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    sdks = data.get("sdks")
    if not isinstance(sdks, list):
        print(f"ERROR: {path} has no 'sdks' list", file=sys.stderr)
        return 2

    scanned = 0
    updated = 0
    skipped_due_to_github = 0
    matched_npm = 0

    for sdk in sdks:
        if not isinstance(sdk, dict):
            continue
        scanned += 1

        urls = collect_urls(sdk)

        # github > npm: if any GitHub repo link exists, do nothing here
        if has_github_repo(urls):
            skipped_due_to_github += 1
            continue

        pkg = choose_npm_package(urls)
        if not pkg:
            continue
        matched_npm += 1

        try:
            meta = compute_from_npm(npm, pkg)
        except requests.RequestException as e:
            print(f"WARN: fetch failed for npm:{pkg}: {e}", file=sys.stderr)
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
    print(f"SDKs with GitHub link (skipped): {skipped_due_to_github}")
    print(f"SDKs with npm link (eligible): {matched_npm}")
    print(f"SDKs updated: {updated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
