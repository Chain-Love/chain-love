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


# Only public GitLab.com repos
GITLAB_HOSTS = {"gitlab.com", "www.gitlab.com"}

# Precedence: github > npm > gitlab
GITHUB_HOSTS = {"github.com", "www.github.com"}
NPM_HOSTS = {"npmjs.com", "www.npmjs.com", "registry.npmjs.org"}

URL_RE = re.compile(r"https?://[^\s\)\"\']+")
MD_LINK_RE = re.compile(r"\[[^\]]*\]\((https?://[^)]+)\)")

VERSION_IN_TAG_RE = re.compile(r"(v?\d+(?:\.\d+){1,3})(?:\+[0-9A-Za-z.-]+)?")
SEMVER_PRERELEASE_SEG_RE = re.compile(r"(?i)v?\d+(?:\.\d+){1,3}-")


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


def dedupe(items: List[str]) -> List[str]:
    seen = set()
    out = []
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


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
        return dedupe([u for x in obj for u in collect_urls(x)])
    if isinstance(obj, dict):
        return dedupe([u for x in obj.values() for u in collect_urls(x)])
    return []


def normalize_github_repo(url: str) -> Optional[str]:
    p = urllib.parse.urlparse(url)
    if p.netloc not in GITHUB_HOSTS:
        return None
    parts = [x for x in p.path.split("/") if x]
    if len(parts) < 2:
        return None
    return f"{parts[0]}/{parts[1].removesuffix('.git')}"


def normalize_npm_package(url: str) -> Optional[str]:
    p = urllib.parse.urlparse(url)
    if p.netloc not in NPM_HOSTS:
        return None
    if p.netloc == "registry.npmjs.org":
        return urllib.parse.unquote(p.path.lstrip("/")) or None
    parts = [x for x in p.path.split("/") if x]
    if len(parts) < 2 or parts[0] != "package":
        return None
    if parts[1].startswith("@") and len(parts) >= 3:
        return f"{parts[1]}/{parts[2]}"
    return parts[1]


def has_github_repo(urls: List[str]) -> bool:
    return any(normalize_github_repo(u) for u in urls)


def has_npm_link(urls: List[str]) -> bool:
    return any(normalize_npm_package(u) for u in urls)


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
        proj = normalize_gitlab_project(u)
        if proj:
            return proj
    return None


def extract_version_from_tag(tag: str) -> Optional[str]:
    m = VERSION_IN_TAG_RE.findall(tag or "")
    return m[-1] if m else None


def is_stable_version(v: str) -> bool:
    if not v:
        return False
    core = v.split("+", 1)[0]
    if "-" in core:
        return False
    c = core[1:] if core.startswith("v") else core
    if re.search(r"[A-Za-z]", c):
        return False
    parts = c.split(".")
    if not 2 <= len(parts) <= 4:
        return False
    try:
        [int(x) for x in parts]
        return True
    except Exception:
        return False


def is_stable_tag_string(s: str) -> bool:
    if not s or SEMVER_PRERELEASE_SEG_RE.search(s):
        return False
    return is_stable_version(extract_version_from_tag(s) or "")


def semver_key(v: str) -> Optional[Tuple[int, int, int, int]]:
    if not is_stable_version(v):
        return None
    c = v.split("+", 1)[0]
    c = c[1:] if c.startswith("v") else c
    nums = [int(x) for x in c.split(".")]
    while len(nums) < 4:
        nums.append(0)
    return tuple(nums[:4])


class Http:
    def __init__(self, timeout: int = 30):
        self.session = requests.Session()
        self.timeout = timeout

    def get_json(self, url: str, headers=None):
        r = self.session.get(url, headers=headers or {}, timeout=self.timeout)
        if r.status_code == 204:
            return r.status_code, None
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, None


class GitLab:
    def __init__(self, http: Http):
        self.http = http
        self.headers = {"User-Agent": "sdks-metadata-updater"}

    def project(self, path: str):
        enc = urllib.parse.quote(path, safe="")
        return self.http.get_json(f"https://gitlab.com/api/v4/projects/{enc}?license=true", self.headers)[1]

    def releases(self, path: str):
        enc = urllib.parse.quote(path, safe="")
        return self.http.get_json(f"https://gitlab.com/api/v4/projects/{enc}/releases?per_page=100", self.headers)[1] or []

    def tags(self, path: str):
        enc = urllib.parse.quote(path, safe="")
        return self.http.get_json(f"https://gitlab.com/api/v4/projects/{enc}/repository/tags?per_page=100", self.headers)[1] or []


def compute_from_gitlab(gl: GitLab, project_path: str, fallback_to_tags: bool) -> Dict[str, str]:
    out = {}
    proj = gl.project(project_path)
    if not isinstance(proj, dict) or proj.get("visibility") != "public":
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
            return out

    if not fallback_to_tags:
        return out

    best = None
    best_vk = None
    for t in gl.tags(project_path):
        name = (t.get("name") or "").strip()
        if not is_stable_tag_string(name):
            continue
        v = extract_version_from_tag(name)
        vk = semver_key(v)
        if vk and (best_vk is None or vk > best_vk):
            best = t
            best_vk = vk

    if best:
        out["latestKnownVersion"] = extract_version_from_tag(best["name"])
        dt = parse_iso_datetime((best.get("commit") or {}).get("committed_date") or "")
        if dt:
            out["latestKnownReleaseDate"] = iso_date(dt)

    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jsonfile", required=True, help='File name without .json or "all"')
    ap.add_argument("--json-dir", default="json")
    ap.add_argument("--fallback-to-tags", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    if args.jsonfile == "all":
        paths = [
            os.path.join(args.json_dir, f)
            for f in os.listdir(args.json_dir)
            if f.endswith(".json")
        ]
    else:
        paths = [os.path.join(args.json_dir, f"{args.jsonfile}.json")]

    http = Http()
    gl = GitLab(http)

    for path in paths:
        if not os.path.isfile(path):
            print(f"ERROR: file not found: {path}", file=sys.stderr)
            continue

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        sdks = data.get("sdks", [])
        for sdk in sdks:
            urls = collect_urls(sdk)
            if has_github_repo(urls) or has_npm_link(urls):
                continue
            proj = choose_gitlab_project(urls)
            if not proj:
                continue
            meta = compute_from_gitlab(gl, proj, args.fallback_to_tags)
            sdk.update({k: v for k, v in meta.items() if v})

        with open(path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
            f.write("\n")

        print(f"Processed: {path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
