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


# ---- Hosts ----

GITLAB_HOSTS = {"gitlab.com", "www.gitlab.com"}
GITHUB_HOSTS = {"github.com", "www.github.com"}
NPM_HOSTS = {"npmjs.com", "www.npmjs.com", "registry.npmjs.org"}


# ---- Regex ----

URL_RE = re.compile(r"https?://[^\s\)\"\']+")
MD_LINK_RE = re.compile(r"\[[^\]]*\]\((https?://[^)]+)\)")
VERSION_IN_TAG_RE = re.compile(r"(v?\d+(?:\.\d+){1,3})(?:\+[0-9A-Za-z.-]+)?")
SEMVER_PRERELEASE_SEG_RE = re.compile(r"(?i)v?\d+(?:\.\d+){1,3}-")


# ---- Helpers ----

def iso_date(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).date().isoformat()


def parse_iso_datetime(s: str) -> Optional[datetime]:
    try:
        if s and s.endswith("Z"):
            s = s.replace("Z", "+00:00")
        return datetime.fromisoformat(s) if s else None
    except Exception:
        return None


def dedupe(items: List[str]) -> List[str]:
    seen, out = set(), []
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def extract_urls_from_string(s: str) -> List[str]:
    urls = []
    urls.extend(m.rstrip(").,;]") for m in MD_LINK_RE.findall(s or ""))
    urls.extend(m.rstrip(").,;]") for m in URL_RE.findall(s or ""))
    return dedupe(urls)


def collect_urls(obj: Any) -> List[str]:
    if isinstance(obj, str):
        return extract_urls_from_string(obj)
    if isinstance(obj, list):
        return dedupe(u for x in obj for u in collect_urls(x))
    if isinstance(obj, dict):
        return dedupe(u for v in obj.values() for u in collect_urls(v))
    return []


# ---- Normalizers ----

def normalize_gitlab_project(url: str) -> Optional[str]:
    p = urllib.parse.urlparse(url)
    if p.netloc not in GITLAB_HOSTS:
        return None
    parts = [x for x in p.path.split("/") if x]
    if "-" in parts:
        parts = parts[: parts.index("-")]
    if len(parts) < 2:
        return None
    parts[-1] = parts[-1].removesuffix(".git")
    return "/".join(parts)


def choose_gitlab_project(urls: List[str]) -> Optional[str]:
    for u in urls:
        p = normalize_gitlab_project(u)
        if p:
            return p
    return None


def has_github_repo(urls: List[str]) -> bool:
    return any(urllib.parse.urlparse(u).netloc in GITHUB_HOSTS for u in urls)


def has_npm_link(urls: List[str]) -> bool:
    return any(urllib.parse.urlparse(u).netloc in NPM_HOSTS for u in urls)


# ---- Semver ----

def extract_version_from_tag(tag: str) -> Optional[str]:
    m = VERSION_IN_TAG_RE.findall(tag or "")
    return m[-1] if m else None


def is_stable_tag_string(s: str) -> bool:
    if not s or SEMVER_PRERELEASE_SEG_RE.search(s):
        return False
    v = extract_version_from_tag(s)
    return bool(v and "-" not in v)


def semver_key(v: str) -> Optional[Tuple[int, int, int, int]]:
    if not v or "-" in v:
        return None
    v = v.lstrip("v").split("+", 1)[0]
    try:
        nums = [int(x) for x in v.split(".")]
        while len(nums) < 4:
            nums.append(0)
        return tuple(nums[:4])
    except Exception:
        return None


# ---- HTTP ----

class Http:
    def __init__(self, timeout: int = 30):
        self.session = requests.Session()
        self.timeout = timeout

    def get_json(self, url: str, headers=None):
        r = self.session.get(url, headers=headers or {}, timeout=self.timeout)
        try:
            data = r.json() if r.status_code != 204 else None
        except Exception:
            data = None
        return r.status_code, data, r.headers


# ---- GitLab API ----

class GitLab:
    def __init__(self, http: Http, token: Optional[str]):
        self.http = http
        self.headers = {"User-Agent": "sdks-metadata-updater"}
        if token:
            self.headers["Authorization"] = f"Bearer {token}"
        self._rate_limit_warned = False

    def _warn_if_limited(self, status: int, headers: Dict[str, str]) -> None:
        if status == 429 and not self._rate_limit_warned:
            ra = headers.get("Retry-After")
            msg = "WARN: GitLab API rate limit exceeded"
            if ra:
                msg += f", retry after {ra}s"
            print(msg, file=sys.stderr)
            self._rate_limit_warned = True

    def _get(self, url: str):
        st, js, hdrs = self.http.get_json(url, self.headers)
        self._warn_if_limited(st, hdrs)
        return js

    def project(self, path: str):
        enc = urllib.parse.quote(path, safe="")
        return self._get(f"https://gitlab.com/api/v4/projects/{enc}?license=true")

    def releases(self, path: str):
        enc = urllib.parse.quote(path, safe="")
        return self._get(f"https://gitlab.com/api/v4/projects/{enc}/releases?per_page=100") or []

    def tags(self, path: str):
        enc = urllib.parse.quote(path, safe="")
        return self._get(f"https://gitlab.com/api/v4/projects/{enc}/repository/tags?per_page=100") or []


# ---- Cache ----

_gitlab_cache: Dict[str, Dict[str, str]] = {}


def compute_from_gitlab(gl: GitLab, project_path: str, fallback_to_tags: bool) -> Dict[str, str]:
    if project_path in _gitlab_cache:
        return _gitlab_cache[project_path]

    out: Dict[str, str] = {}
    proj = gl.project(project_path)
    if not isinstance(proj, dict) or proj.get("visibility") != "public":
        _gitlab_cache[project_path] = out
        return out

    owner = proj.get("owner") or {}
    ns = proj.get("namespace") or {}
    out["maintainer"] = (
        owner.get("username")
        or ns.get("full_path")
        or proj.get("path_with_namespace")
    )

    lic = (proj.get("license") or {}).get("spdx_identifier")
    if lic:
        out["license"] = lic

    for r in gl.releases(project_path):
        tag = (r.get("tag_name") or "").strip()
        if is_stable_tag_string(tag):
            out["latestKnownVersion"] = extract_version_from_tag(tag) or tag
            dt = parse_iso_datetime(r.get("released_at") or "")
            if dt:
                out["latestKnownReleaseDate"] = iso_date(dt)
            _gitlab_cache[project_path] = out
            return out

    if fallback_to_tags:
        best_vk, best = None, None
        for t in gl.tags(project_path):
            name = (t.get("name") or "").strip()
            if not is_stable_tag_string(name):
                continue
            v = extract_version_from_tag(name)
            vk = semver_key(v)
            if vk and (best_vk is None or vk > best_vk):
                best_vk, best = vk, t
        if best:
            out["latestKnownVersion"] = extract_version_from_tag(best["name"])
            dt = parse_iso_datetime((best.get("commit") or {}).get("committed_date") or "")
            if dt:
                out["latestKnownReleaseDate"] = iso_date(dt)

    _gitlab_cache[project_path] = out
    return out


# ---- Main ----

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jsonfile", required=True)
    ap.add_argument("--json-dir", default="json")
    ap.add_argument("--fallback-to-tags", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    paths = (
        [os.path.join(args.json_dir, f) for f in os.listdir(args.json_dir) if f.endswith(".json")]
        if args.jsonfile == "all"
        else [os.path.join(args.json_dir, f"{args.jsonfile}.json")]
    )

    http = Http()
    gl = GitLab(http, os.getenv("GITLAB_TOKEN"))

    total_scanned = 0
    total_updated = 0

    for path in paths:
        if not os.path.isfile(path):
            print(f"ERROR: file not found: {path}", file=sys.stderr)
            continue

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        sdks = data.get("sdks", [])
        scanned = 0
        updated = 0

        for sdk in sdks:
            if not isinstance(sdk, dict):
                continue

            scanned += 1
            before = dict(sdk)

            urls = collect_urls(sdk)
            if has_github_repo(urls) or has_npm_link(urls):
                continue

            proj = choose_gitlab_project(urls)
            if not proj:
                continue

            meta = compute_from_gitlab(gl, proj, args.fallback_to_tags)
            if meta:
                sdk.update({k: v for k, v in meta.items() if v})

            if sdk != before:
                updated += 1

        with open(path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
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
