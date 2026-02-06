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

# Extract semver-like substring anywhere in a tag/release name
# e.g. "dev/@scope/pkg/v0.3.0" -> "v0.3.0"
VERSION_IN_TAG_RE = re.compile(r"(v?\d+(?:\.\d+){1,3})(?:\+[0-9A-Za-z.-]+)?")

# For rejecting prerelease semver like "1.2.3-rc.1" even if embedded in a string
SEMVER_PRERELEASE_SEG_RE = re.compile(r"(?i)v?\d+(?:\.\d+){1,3}-")


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
        urls: List[str] = []
        for item in obj:
            urls.extend(collect_urls(item))
        return dedupe(urls)
    if isinstance(obj, dict):
        urls: List[str] = []
        for v in obj.values():
            urls.extend(collect_urls(v))
        return dedupe(urls)
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
        path = p.path.lstrip("/")
        if not path:
            return None
        return urllib.parse.unquote(path)

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
    """
    GitLab.com project URL -> "group/subgroup/project"
    Handles:
      https://gitlab.com/group/project
      https://gitlab.com/group/subgroup/project
      https://gitlab.com/group/project/-/tree/main
      https://gitlab.com/group/project.git
    """
    p = urllib.parse.urlparse(url)
    if p.netloc not in GITLAB_HOSTS:
        return None

    parts = [x for x in p.path.split("/") if x]
    if len(parts) < 2:
        return None

    # Truncate at "/-/" (split becomes ..., "-", "tree", ...)
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
    if not tag:
        return None
    matches = VERSION_IN_TAG_RE.findall(tag.strip())
    return matches[-1] if matches else None


def is_stable_version(v: str) -> bool:
    """
    Stable version rules:
      - looks like v0.3.0 / 0.3.0 / 0.3 / 0.3.0.0
      - may have +build metadata
      - must NOT have prerelease '-' segment (e.g. 1.2.3-rc.1)
      - must NOT contain letters in core numeric segments (rejects 1.2.3.dev2)
    """
    if not v:
        return False

    core = v.strip().split("+", 1)[0]
    if "-" in core:
        return False

    c = core[1:] if core.startswith("v") else core
    if re.search(r"[A-Za-z]", c):
        return False

    parts = c.split(".")
    if len(parts) < 2 or len(parts) > 4:
        return False
    try:
        [int(x) for x in parts]
        return True
    except Exception:
        return False


def is_stable_tag_string(tag_or_name: str) -> bool:
    """
    Applies stability check to an extracted version from within the tag string.
    Also rejects embedded semver prerelease segments like "v1.2.3-rc.1" anywhere.
    """
    if not tag_or_name:
        return False
    if SEMVER_PRERELEASE_SEG_RE.search(tag_or_name):
        return False
    v = extract_version_from_tag(tag_or_name)
    return is_stable_version(v or "")


def semver_key(v: str) -> Optional[Tuple[int, int, int, int]]:
    """
    Comparable tuple for stable versions only.
    """
    if not is_stable_version(v):
        return None
    core = v.strip().split("+", 1)[0]
    c = core[1:] if core.startswith("v") else core
    nums = [int(x) for x in c.split(".")]
    while len(nums) < 4:
        nums.append(0)
    return tuple(nums[:4])  # type: ignore


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


class GitLab:
    def __init__(self, http: Http):
        self.http = http
        self.headers = {"User-Agent": "sdks-metadata-updater"}

    def project(self, project_path: str) -> Optional[dict]:
        # project_path MUST be URL-encoded for the API route
        enc = urllib.parse.quote(project_path, safe="")
        url = f"https://gitlab.com/api/v4/projects/{enc}?license=true"
        st, js = self.http.get_json(url, headers=self.headers)
        return js if st == 200 and isinstance(js, dict) else None

    def releases(self, project_path: str, per_page: int = 100) -> List[dict]:
        enc = urllib.parse.quote(project_path, safe="")
        url = f"https://gitlab.com/api/v4/projects/{enc}/releases?per_page={per_page}"
        st, js = self.http.get_json(url, headers=self.headers)
        if st == 200 and isinstance(js, list):
            return [x for x in js if isinstance(x, dict)]
        return []

    def tags(self, project_path: str, per_page: int = 100) -> List[dict]:
        enc = urllib.parse.quote(project_path, safe="")
        url = f"https://gitlab.com/api/v4/projects/{enc}/repository/tags?per_page={per_page}"
        st, js = self.http.get_json(url, headers=self.headers)
        if st == 200 and isinstance(js, list):
            return [x for x in js if isinstance(x, dict)]
        return []


def dt_from_release(r: dict) -> Optional[datetime]:
    s = r.get("released_at") or r.get("created_at") or ""
    return parse_iso_datetime(s) if isinstance(s, str) else None


def dt_from_tag(t: dict) -> Optional[datetime]:
    commit = t.get("commit") or {}
    s = commit.get("committed_date") or commit.get("created_at") or ""
    return parse_iso_datetime(s) if isinstance(s, str) else None


def extract_gitlab_license(proj: dict) -> Optional[str]:
    lic = proj.get("license")
    if not isinstance(lic, dict):
        return None
    spdx = lic.get("spdx_identifier") or lic.get("spdx_id")
    if isinstance(spdx, str) and spdx.strip():
        return spdx.strip()
    name = lic.get("name") or lic.get("key")
    if isinstance(name, str) and name.strip():
        return name.strip()
    return None


def pick_latest_stable_release(releases: List[dict]) -> Optional[dict]:
    releases_sorted = sorted(
        releases,
        key=lambda r: (dt_from_release(r).timestamp() if dt_from_release(r) else 0.0),
        reverse=True,
    )
    for r in releases_sorted:
        # tag_name is what we should store as version (or extracted semver if you prefer)
        tag = (r.get("tag_name") or "").strip()
        if is_stable_tag_string(tag):
            return r
    return None


def pick_best_stable_tag(tags: List[dict]) -> Optional[dict]:
    """
    Choose the best stable tag. Strategy:
      - Prefer highest stable semver extracted from tag name.
      - Tie-break by committed date (newest).
    This handles repositories with multiple package tags on the same commit.
    """
    best = None
    best_ver_key = None
    best_time = 0.0

    for t in tags:
        name = (t.get("name") or "").strip()
        if not is_stable_tag_string(name):
            continue

        ver = extract_version_from_tag(name)
        if not ver:
            continue

        vk = semver_key(ver)
        if vk is None:
            continue

        dt = dt_from_tag(t)
        ts = dt.timestamp() if dt else 0.0

        if best is None:
            best = t
            best_ver_key = vk
            best_time = ts
            continue

        # Compare by version first, then by timestamp
        if vk > best_ver_key:  # type: ignore
            best = t
            best_ver_key = vk
            best_time = ts
        elif vk == best_ver_key and ts > best_time:
            best = t
            best_time = ts

    return best


def compute_from_gitlab(gl: GitLab, project_path: str, fallback_to_tags: bool) -> Dict[str, str]:
    out: Dict[str, str] = {}

    proj = gl.project(project_path)
    if not proj:
        return out

    # Public only
    if proj.get("visibility") != "public":
        return out

    # maintainer
    owner = proj.get("owner") or {}
    namespace = proj.get("namespace") or {}

    if isinstance(owner, dict) and isinstance(owner.get("username"), str) and owner["username"].strip():
        out["maintainer"] = owner["username"].strip()
    elif isinstance(namespace, dict) and isinstance(namespace.get("full_path"), str) and namespace["full_path"].strip():
        out["maintainer"] = namespace["full_path"].strip()
    elif isinstance(proj.get("path_with_namespace"), str) and proj["path_with_namespace"].strip():
        out["maintainer"] = proj["path_with_namespace"].strip()

    # license
    lic = extract_gitlab_license(proj)
    if lic:
        out["license"] = lic

    # Releases first
    rels = gl.releases(project_path, per_page=100)
    rel = pick_latest_stable_release(rels)
    if rel:
        tag_name = (rel.get("tag_name") or "").strip()
        # Store the extracted semver if possible; else store the raw tag_name.
        ver = extract_version_from_tag(tag_name) or tag_name
        if ver:
            out["latestKnownVersion"] = ver

        dt = dt_from_release(rel)
        if dt:
            out["latestKnownReleaseDate"] = iso_date(dt)
        return out

    if not fallback_to_tags:
        return out  # release-only mode

    tags = gl.tags(project_path, per_page=100)
    tag_obj = pick_best_stable_tag(tags)
    if not tag_obj:
        return out

    tag_name = (tag_obj.get("name") or "").strip()
    ver = extract_version_from_tag(tag_name)
    if ver:
        out["latestKnownVersion"] = ver

    dt = dt_from_tag(tag_obj)
    if dt:
        out["latestKnownReleaseDate"] = iso_date(dt)

    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--blockchain", required=True, help="Blockchain name (expects json/<blockchain>.json)")
    ap.add_argument("--json-dir", default="json", help="Directory containing blockchain JSON files")
    ap.add_argument(
        "--fallback-to-tags",
        action="store_true",
        help="If no GitLab Releases exist, use stable repository tags as fallback.",
    )
    ap.add_argument("--verbose", action="store_true", help="Print per-SDK decisions.")
    args = ap.parse_args()

    path = os.path.join(args.json_dir, f"{args.blockchain}.json")
    if not os.path.isfile(path):
        print(f"ERROR: file not found: {path}", file=sys.stderr)
        return 2

    http = Http()
    gl = GitLab(http)

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    sdks = data.get("sdks")
    if not isinstance(sdks, list):
        print(f"ERROR: {path} has no 'sdks' list", file=sys.stderr)
        return 2

    scanned = 0
    updated = 0
    skipped_github = 0
    skipped_npm = 0
    eligible_gitlab = 0

    for sdk in sdks:
        if not isinstance(sdk, dict):
            continue
        scanned += 1
        slug = sdk.get("slug", "(no-slug)")

        urls = collect_urls(sdk)

        # github > npm > gitlab
        if has_github_repo(urls):
            skipped_github += 1
            if args.verbose:
                print(f"[skip github] {slug}")
            continue

        if has_npm_link(urls):
            skipped_npm += 1
            if args.verbose:
                print(f"[skip npm] {slug}")
            continue

        project_path = choose_gitlab_project(urls)
        if not project_path:
            if args.verbose:
                print(f"[no gitlab] {slug}")
            continue

        eligible_gitlab += 1

        try:
            meta = compute_from_gitlab(gl, project_path, fallback_to_tags=args.fallback_to_tags)
        except requests.RequestException as e:
            print(f"WARN: fetch failed for gitlab:{project_path} ({slug}): {e}", file=sys.stderr)
            continue

        if not meta:
            if args.verbose:
                mode = "releases+tags" if args.fallback_to_tags else "releases-only"
                print(f"[no update {mode}] {slug} -> {project_path}")
            continue

        changed = False
        for k, v in meta.items():
            if v and sdk.get(k) != v:
                sdk[k] = v
                changed = True

        if changed:
            updated += 1
            if args.verbose:
                print(f"[updated] {slug} -> {project_path} :: {meta}")

    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
        f.write("\n")

    print(f"File: {path}")
    print(f"SDKs scanned: {scanned}")
    print(f"Skipped (GitHub precedence): {skipped_github}")
    print(f"Skipped (npm precedence): {skipped_npm}")
    print(f"Eligible (GitLab): {eligible_gitlab}")
    print(f"Updated: {updated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
