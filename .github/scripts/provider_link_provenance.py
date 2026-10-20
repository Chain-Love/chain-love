#!/usr/bin/env python3
"""Report provider ``website``/``docs`` link provenance for pull requests.

The repository's Lychee job answers one question: *did the URL respond?*
That is transport reachability, not product identity. A parked, repurposed,
or taken-over domain can return ``200`` while serving unrelated content, and
a genuine page can document one product while being proposed as a
provider-wide link.

This tool reports two independent axes for **new or changed** ``website`` and
``docs`` cells in ``references/providers/providers.csv``:

``reachable``
    ``reachable``, ``blocked_or_unknown``, ``unreachable``, ``not_checked``
    or ``not_applicable``.

``provenance``
    ``first_party_evidenced``, ``needs_manual_identity_review`` or
    ``not_applicable``.

Evidence is an explicit URL on a provider-controlled page that links to the
candidate URL. The tool matches URLs exactly (after normalisation); it never
classifies page text, never scores visual similarity, and never treats a
``401``/``403``/``429`` response as proof of a hijack.

Commands::

    # Offline: read the provider CSV at two git refs and emit the change set.
    provider_link_provenance.py collect \
        --base origin/main --head HEAD --output changes.json

    # Advisory: probe reachability and gather first-party evidence.
    provider_link_provenance.py report \
        --changes changes.json --probe --fetch-evidence \
        --pr-body pr-body.md --output report.md

The report command always exits ``0``. It is a review aid, not a blocking
validator; a maintainer makes the final identity decision.
"""

from __future__ import annotations

import argparse
import csv
import http.client
import io
import ipaddress
import json
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable, Sequence

PROVIDERS_PATH = "references/providers/providers.csv"
CHECKED_FIELDS = ("website", "docs")

# Statuses Lychee also accepts. They mean "the server refused this client",
# not "the domain is gone" and not "the domain changed owner".
BLOCKED_HTTP_STATUSES = frozenset({400, 401, 403, 405, 429})

MAX_RESPONSE_BYTES = 256 * 1024
MAX_PR_BODY_URLS = 10
USER_AGENT = (
    "Chain-Love-provider-link-provenance/1.0 "
    "(+https://github.com/Chain-Love/chain-love)"
)

FIRST_PARTY_EVIDENCED = "first_party_evidenced"
NEEDS_REVIEW = "needs_manual_identity_review"
NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True)
class Provider:
    slug: str
    name: str
    website: str
    docs: str
    github: str

    @classmethod
    def from_mapping(cls, data: dict) -> "Provider":
        return cls(
            slug=str(data.get("slug") or "").strip(),
            name=str(data.get("name") or "").strip(),
            website=str(data.get("website") or "").strip(),
            docs=str(data.get("docs") or "").strip(),
            github=str(data.get("github") or "").strip(),
        )


@dataclass(frozen=True)
class Evidence:
    """A provider-controlled page supplied as a possible ownership trail."""

    url: str
    content: str


@dataclass(frozen=True)
class Reachability:
    status: str
    http_status: int | None = None
    page_title: str = ""
    detail: str = ""


@dataclass(frozen=True)
class EvidenceScope:
    """How a page is owned and what scope it can speak for."""

    kind: str  # github_org | github_repo | official_site
    label: str
    canonical: bool = True


class CollectError(RuntimeError):
    """Raised when the git change set cannot be read."""


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------


def normalize_url(url: str, *, keep_fragment: bool = True) -> str:
    """Return a comparison key for a URL.

    Scheme and host are case-insensitive, ``www.`` is ignored, default ports
    and a trailing slash are dropped. Query strings and fragments are kept so
    that two different sections of a page remain distinguishable.
    """

    raw = (url or "").strip()
    try:
        parts = urllib.parse.urlsplit(raw)
        port = parts.port
    except ValueError:
        return raw.lower()

    scheme = parts.scheme.lower()
    host = _normalize_host(parts.hostname)
    if not scheme or not host:
        return raw.lower()

    if port is not None and not (
        (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    ):
        netloc = f"{host}:{port}"
    else:
        netloc = host

    path = parts.path or "/"
    if path != "/":
        path = path.rstrip("/")

    query = f"?{parts.query}" if parts.query else ""
    fragment = f"#{parts.fragment}" if keep_fragment and parts.fragment else ""
    return f"{scheme}://{netloc}{path}{query}{fragment}"


def _normalize_host(host: str | None) -> str:
    value = (host or "").strip().lower().rstrip(".")
    if value.startswith("www."):
        value = value[4:]
    return value


def _is_http_url(url: str) -> bool:
    try:
        parts = urllib.parse.urlsplit((url or "").strip())
    except ValueError:
        return False
    return parts.scheme in ("http", "https") and bool(parts.hostname)


def is_safe_fetch_url(url: str) -> bool:
    """Reject obviously non-public endpoints before making a request.

    This keeps CI from fetching loopback, link-local, private, or unusual-port
    URLs that may appear in an untrusted pull-request body. It is a
    defence-in-depth check, not a DNS-rebinding guarantee.
    """

    try:
        parts = urllib.parse.urlsplit((url or "").strip())
        port = parts.port
    except ValueError:
        return False

    if parts.scheme not in ("http", "https") or not parts.hostname:
        return False
    if parts.username or parts.password:
        return False
    if port not in (None, 80, 443):
        return False

    host = parts.hostname.lower().rstrip(".")
    if host in {"localhost", "localhost.localdomain"}:
        return False
    if host.endswith((".localhost", ".local", ".internal")):
        return False

    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return True  # A public DNS name; resolution happens in urlopen.
    return not (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
        or address.is_unspecified
    )


# ---------------------------------------------------------------------------
# HTML / Markdown link extraction
# ---------------------------------------------------------------------------


class _PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []
        self.title_parts: list[str] = []
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.links.append(href.strip())
        elif tag == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_parts.append(data)


def _parse_page(html: str) -> _PageParser:
    parser = _PageParser()
    try:
        parser.feed(html or "")
        parser.close()
    except Exception:
        # Malformed HTML must not abort the report; return what was parsed.
        pass
    return parser


def extract_html_links(html: str) -> list[str]:
    return _parse_page(html).links


def extract_title(html: str) -> str:
    title = " ".join("".join(_parse_page(html).title_parts).split())
    return title[:160]


_MARKDOWN_LINK_RE = re.compile(
    r"\]\(\s*<?([^)\s>]+)>?(?:\s+[\"'][^\"']*[\"'])?\s*\)"
)
_MARKDOWN_AUTOLINK_RE = re.compile(r"<(https?://[^>\s]+)>")
_MARKDOWN_REFERENCE_RE = re.compile(
    r"^\s{0,3}\[[^\]]+\]:\s*<?(https?://[^>\s]+)>?", re.MULTILINE
)


def extract_markdown_links(text: str) -> list[str]:
    """Return explicit Markdown link destinations and autolinks.

    Fenced and inline code are removed first: a URL shown as an example in a
    README is not an ownership crosslink. Bare prose URLs are deliberately not
    treated as links, so a README warning about an old domain cannot be
    mistaken for an endorsement of it.
    """

    cleaned = re.sub(r"```.*?```", "", text or "", flags=re.DOTALL)
    cleaned = re.sub(r"`[^`\n]*`", "", cleaned)
    links = [match.group(1) for match in _MARKDOWN_LINK_RE.finditer(cleaned)]
    links.extend(match.group(1) for match in _MARKDOWN_AUTOLINK_RE.finditer(cleaned))
    links.extend(match.group(1) for match in _MARKDOWN_REFERENCE_RE.finditer(cleaned))
    return links


def _linked_urls(evidence: Evidence) -> list[str]:
    raw_links = extract_html_links(evidence.content)
    raw_links.extend(extract_markdown_links(evidence.content))

    resolved: list[str] = []
    for raw in raw_links:
        try:
            absolute = urllib.parse.urljoin(evidence.url, raw.strip())
        except ValueError:
            continue
        if _is_http_url(absolute):
            resolved.append(absolute)
    return resolved


# ---------------------------------------------------------------------------
# Evidence ownership and scope
# ---------------------------------------------------------------------------


def _normalize_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def _strip_git_suffix(value: str) -> str:
    return value[:-4] if value.endswith(".git") else value


def _github_identity(provider: Provider) -> tuple[str, str | None] | None:
    handle = (provider.github or "").strip().strip("/")
    if not handle:
        return None

    parts = handle.split("/")
    org = parts[0].strip().lower()
    repo = None
    if len(parts) > 1:
        repo = _strip_git_suffix(parts[1].strip().lower())
    if not org:
        return None
    return org, repo


def classify_evidence(
    evidence_url: str,
    provider: Provider,
    changed_fields: Iterable[str],
) -> EvidenceScope | None:
    """Return the scope of a provider-controlled page, or ``None``.

    GitHub pages are anchored by the provider's canonical ``github`` handle.
    An official-site page is only independent when the ``website`` cell is not
    itself part of the same change; otherwise both cells could point at the
    same repurposed domain and "confirm" each other.
    """

    try:
        parts = urllib.parse.urlsplit(evidence_url)
    except ValueError:
        return None
    host = _normalize_host(parts.hostname)

    if host == "github.com":
        identity = _github_identity(provider)
        if identity is None:
            return None
        org, handle_repo = identity
        segments = [segment for segment in parts.path.split("/") if segment]
        if not segments or segments[0].lower() != org:
            return None
        if len(segments) == 1:
            return EvidenceScope("github_org", f"github.com/{segments[0]}")

        repo = _strip_git_suffix(segments[1].lower())
        canonical_names = {
            token
            for token in (_normalize_token(provider.slug), _normalize_token(provider.name))
            if token
        }
        is_canonical = repo in canonical_names or (
            handle_repo is not None and repo == handle_repo
        )
        return EvidenceScope(
            "github_repo",
            f"github.com/{segments[0]}/{segments[1]}",
            canonical=is_canonical,
        )

    website_host = ""
    if provider.website:
        try:
            website_host = _normalize_host(urllib.parse.urlsplit(provider.website).hostname)
        except ValueError:
            website_host = ""
    if website_host and host == website_host and "website" not in set(changed_fields):
        return EvidenceScope("official_site", host)
    return None


def _candidate_is_same_github_repo(candidate: str, evidence_label: str) -> bool:
    try:
        parts = urllib.parse.urlsplit(candidate)
    except ValueError:
        return False
    if _normalize_host(parts.hostname) != "github.com":
        return False
    segments = [segment for segment in parts.path.split("/") if segment]
    if len(segments) < 2:
        return False
    return f"github.com/{segments[0]}/{segments[1]}".lower() == evidence_label.lower()


def _scope_review_reason(
    scope: EvidenceScope,
    candidate: str,
    field_name: str,
) -> str | None:
    """Return a review reason when the evidence cannot speak for this field."""

    if scope.kind in ("github_org", "official_site"):
        return None
    if scope.canonical:
        return None
    if _candidate_is_same_github_repo(candidate, scope.label):
        return None
    return (
        f"Only product-scoped source {scope.label} links to this URL. "
        f"A provider-level `{field_name}` value needs an organization-level or "
        "canonical-repository crosslink; confirm the product/provider scope manually."
    )


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------


def _format_reachability(reachability: Reachability) -> str:
    status = reachability.status
    if status == "reachable":
        text = (
            f"reachable (HTTP {reachability.http_status})"
            if reachability.http_status
            else "reachable"
        )
        if reachability.page_title:
            text += f'; page title: "{reachability.page_title}"'
        if reachability.detail:
            text += f" — {reachability.detail}"
        return text
    if status == "blocked_or_unknown":
        code = f"HTTP {reachability.http_status}" if reachability.http_status else "no status"
        return f"unknown ({code}: access control or anti-bot; not treated as hijack)"
    if status == "unreachable":
        return f"unreachable ({reachability.detail or 'request failed'})"
    if status == "not_applicable":
        return "—"
    return "not checked"


def evaluate_change(
    change: dict,
    reachability: Reachability,
    evidence: Sequence[Evidence],
) -> dict:
    """Evaluate one changed provider field and return a report row."""

    provider_data = change.get("provider") or {}
    provider = Provider.from_mapping(
        {
            "slug": provider_data.get("slug", change.get("slug")),
            "name": provider_data.get("name", ""),
            "website": provider_data.get("website", ""),
            "docs": provider_data.get("docs", ""),
            "github": provider_data.get("github", ""),
        }
    )
    field_name = str(change.get("field") or "")
    candidate = str(change.get("new") or "").strip()
    changed_fields = tuple(change.get("changed_fields") or (field_name,))

    result = {
        "slug": provider.slug,
        "name": provider.name,
        "field": field_name,
        "url": candidate,
        "reachable": reachability.status,
        "http_status": reachability.http_status,
        "page_title": reachability.page_title,
        "reachability_note": _format_reachability(reachability),
        "provenance": NOT_APPLICABLE,
        "reason": "",
        "evidence_url": None,
    }

    if not candidate:
        result["reason"] = "Field is empty; nothing to verify."
        return result

    if not _is_http_url(candidate):
        result["provenance"] = NEEDS_REVIEW
        result["reason"] = (
            "Value is not an absolute http(s) URL; fix the format before "
            "identity review."
        )
        return result

    candidate_key = normalize_url(candidate)
    candidate_document = normalize_url(candidate, keep_fragment=False)

    matches: list[tuple[Evidence, EvidenceScope, bool]] = []
    skipped_self_reference = 0
    ignored_sources = 0

    for item in evidence:
        if not item.url or not item.content:
            continue
        if normalize_url(item.url, keep_fragment=False) == candidate_document:
            skipped_self_reference += 1
            continue

        scope = classify_evidence(item.url, provider, changed_fields)
        if scope is None:
            ignored_sources += 1
            continue

        linked = _linked_urls(item)
        exact_match = candidate_key in linked
        base_match = candidate_document in {
            normalize_url(url, keep_fragment=False) for url in linked
        }
        if exact_match or base_match:
            matches.append((item, scope, exact_match))

    for item, scope, exact_match in matches:
        review_reason = _scope_review_reason(scope, candidate, field_name)
        if review_reason is not None:
            continue

        result["provenance"] = FIRST_PARTY_EVIDENCED
        result["evidence_url"] = item.url
        reason = f"Linked from provider-controlled source {item.url}."
        if not exact_match and "#" in candidate:
            reason += (
                " The page URL matches; the section fragment was not "
                "separately verified."
            )
        result["reason"] = reason
        return result

    if matches:
        item, scope, _ = matches[0]
        result["provenance"] = NEEDS_REVIEW
        result["evidence_url"] = item.url
        result["reason"] = _scope_review_reason(scope, candidate, field_name) or (
            "The supplied source does not establish provider-wide scope."
        )
        return result

    result["provenance"] = NEEDS_REVIEW
    notes = ["No independent first-party crosslink found."]
    if skipped_self_reference:
        notes.append(
            "The only supplied source was the candidate URL itself; a URL in "
            "the same row is not independent proof."
        )
    if ignored_sources:
        notes.append(
            "Supplied sources were not controlled by this provider or were "
            "changed in the same PR."
        )
    notes.append(
        "HTTP reachability does not prove product identity. Add a canonical "
        "GitHub org/repo README or unchanged official-website link to this "
        "exact URL."
    )
    result["reason"] = " ".join(notes)
    return result


# ---------------------------------------------------------------------------
# Network probing (optional, best effort, never blocking)
# ---------------------------------------------------------------------------


def probe_url(url: str, timeout: float = 10.0) -> Reachability:
    """Check reachability without making any identity claim."""

    if not is_safe_fetch_url(url):
        return Reachability(
            "not_checked", detail="URL is not a public http(s) endpoint"
        )

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = getattr(response, "status", None) or response.getcode()
            final_url = response.geturl()
            content_type = response.headers.get_content_type()
            body = ""
            if content_type in ("text/html", "application/xhtml+xml"):
                body = response.read(MAX_RESPONSE_BYTES).decode("utf-8", "replace")

            detail = ""
            if normalize_url(final_url, keep_fragment=False) != normalize_url(
                url, keep_fragment=False
            ):
                detail = f"redirects to {final_url}"
            return Reachability(
                "reachable",
                status,
                page_title=extract_title(body),
                detail=detail,
            )
    except urllib.error.HTTPError as exc:
        if exc.code in BLOCKED_HTTP_STATUSES:
            return Reachability(
                "blocked_or_unknown",
                exc.code,
                detail="access control or anti-bot response",
            )
        return Reachability("unreachable", exc.code, detail=f"HTTP {exc.code}")
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        return Reachability("unreachable", detail=type(exc).__name__)
    except http.client.HTTPException as exc:
        return Reachability("unreachable", detail=type(exc).__name__)


def _fetch_text(url: str, timeout: float = 8.0) -> str:
    if not is_safe_fetch_url(url):
        return ""
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/plain,text/html;q=0.9,*/*;q=0.5",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read(MAX_RESPONSE_BYTES).decode("utf-8", "replace")
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return ""
    except http.client.HTTPException:
        return ""


def fetch_github_evidence(provider: Provider, timeout: float = 8.0) -> list[Evidence]:
    """Fetch the provider's canonical GitHub README as an evidence page."""

    identity = _github_identity(provider)
    if identity is None:
        return []

    org, repo = identity
    if repo:
        raw_base = f"https://raw.githubusercontent.com/{org}/{repo}/HEAD"
        candidates = (f"{raw_base}/README.md", f"{raw_base}/readme.md")
        evidence_url = f"https://github.com/{org}/{repo}"
    else:
        raw_base = f"https://raw.githubusercontent.com/{org}/.github/HEAD"
        candidates = (f"{raw_base}/profile/README.md", f"{raw_base}/README.md")
        evidence_url = f"https://github.com/{org}"

    for raw_url in candidates:
        content = _fetch_text(raw_url, timeout=timeout)
        if content:
            return [Evidence(url=evidence_url, content=content)]
    return []


def evidence_from_pr_body(
    body: str,
    provider: Provider,
    changed_fields: Iterable[str],
    candidate: str,
    timeout: float = 8.0,
) -> list[Evidence]:
    """Fetch provider-owned pages cited in the PR description.

    Only URLs that are already owned by the provider (GitHub org or unchanged
    official website) are fetched. This is how a contributor's explicit
    ownership trail becomes machine-checkable without trusting arbitrary text.
    """

    if not body:
        return []

    candidate_document = normalize_url(candidate, keep_fragment=False)
    evidence: list[Evidence] = []
    seen: set[str] = set()

    for match in re.finditer(r"https?://[^\s<>\"')\]]+", body):
        url = match.group(0).rstrip(".,;:")
        key = normalize_url(url, keep_fragment=False)
        if key in seen or key == candidate_document:
            continue
        seen.add(key)
        if len(evidence) >= MAX_PR_BODY_URLS:
            break
        if classify_evidence(url, provider, changed_fields) is None:
            continue
        content = _fetch_text(url, timeout=timeout)
        if content:
            evidence.append(Evidence(url=url, content=content))
    return evidence


def gather_evidence(
    change: dict,
    *,
    fetch_github: bool = False,
    pr_body: str = "",
    explicit: dict[str, list[Evidence]] | None = None,
    timeout: float = 8.0,
) -> list[Evidence]:
    provider_data = change.get("provider") or {}
    provider = Provider.from_mapping(
        {
            "slug": provider_data.get("slug", change.get("slug")),
            "name": provider_data.get("name", ""),
            "website": provider_data.get("website", ""),
            "docs": provider_data.get("docs", ""),
            "github": provider_data.get("github", ""),
        }
    )
    changed_fields = tuple(
        change.get("changed_fields") or (change.get("field") or "",)
    )

    evidence: list[Evidence] = list((explicit or {}).get(provider.slug, []))
    if fetch_github:
        evidence.extend(fetch_github_evidence(provider, timeout=timeout))
    if pr_body:
        evidence.extend(
            evidence_from_pr_body(
                pr_body,
                provider,
                changed_fields,
                candidate=str(change.get("new") or ""),
                timeout=timeout,
            )
        )

    deduplicated: list[Evidence] = []
    seen: set[str] = set()
    for item in evidence:
        key = normalize_url(item.url, keep_fragment=False)
        if key in seen:
            continue
        seen.add(key)
        deduplicated.append(item)
    return deduplicated


# ---------------------------------------------------------------------------
# Change-set collection
# ---------------------------------------------------------------------------


def _provider_rows(text: str) -> dict[str, dict[str, str]]:
    if not text.strip():
        return {}
    reader = csv.DictReader(io.StringIO(text, newline=""))
    rows: dict[str, dict[str, str]] = {}
    for row in reader:
        slug = (row.get("slug") or "").strip()
        if slug:
            rows[slug] = {key: (value or "").strip() for key, value in row.items()}
    return rows


def compute_changes(old_text: str, new_text: str) -> list[dict]:
    """Return only new/changed ``website`` and ``docs`` cells."""

    old_rows = _provider_rows(old_text)
    new_rows = _provider_rows(new_text)
    changes: list[dict] = []

    for slug, row in new_rows.items():
        previous = old_rows.get(slug, {})
        changed_fields = [
            field
            for field in CHECKED_FIELDS
            if (previous.get(field) or "").strip() != (row.get(field) or "").strip()
        ]
        for field_name in changed_fields:
            changes.append(
                {
                    "slug": slug,
                    "field": field_name,
                    "old": (previous.get(field_name) or "").strip(),
                    "new": (row.get(field_name) or "").strip(),
                    "provider": {
                        "slug": slug,
                        "name": row.get("name", ""),
                        "website": row.get("website", ""),
                        "docs": row.get("docs", ""),
                        "github": row.get("github", ""),
                    },
                    "changed_fields": changed_fields,
                }
            )

    changes.sort(key=lambda item: (item["slug"], item["field"]))
    return changes


def _git_ref_exists(ref: str, cwd: str | None = None) -> bool:
    completed = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    return completed.returncode == 0


def _git_show(ref: str, path: str, cwd: str | None = None) -> str:
    if not _git_ref_exists(ref, cwd=cwd):
        raise CollectError(f"git ref not found: {ref}")

    completed = subprocess.run(
        ["git", "show", f"{ref}:{path}"],
        cwd=cwd,
        capture_output=True,
        text=False,
    )
    if completed.returncode != 0:
        # The file may not exist at this ref (for example, before the CSV was
        # created). Treat that as an empty dataset, not a hard failure.
        print(
            f"warning: {path} is not available at {ref}",
            file=sys.stderr,
        )
        return ""
    return completed.stdout.decode("utf-8-sig", errors="replace")


def collect_changes(
    base: str,
    head: str,
    path: str = PROVIDERS_PATH,
    *,
    cwd: str | None = None,
) -> list[dict]:
    old_text = _git_show(base, path, cwd=cwd)
    if head == "WORKTREE":
        worktree_path = Path(cwd or ".") / path
        new_text = worktree_path.read_text(encoding="utf-8-sig", errors="replace")
    else:
        new_text = _git_show(head, path, cwd=cwd)
    return compute_changes(old_text, new_text)


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------


def _escape_cell(value: str) -> str:
    return " ".join((value or "").split()).replace("|", r"\|")


def _autolink(url: str) -> str:
    if not url:
        return "—"
    cell = _escape_cell(url)
    if any(character in cell for character in "<> "):
        return cell
    return f"<{cell}>"


def render_report(results: Sequence[dict], *, base: str = "", head: str = "") -> str:
    title = "### Provider link identity check"
    if not results:
        return (
            f"{title}\n\n"
            "No new or changed provider `website`/`docs` values were found in "
            "this change set.\n"
        )

    lines = [
        title,
        "",
        "> **HTTP success ≠ first-party identity verified.** Reachability and "
        "provenance are reported separately. `needs_manual_identity_review` is "
        "a request for a human decision, not an accusation of domain hijacking.",
        "",
    ]
    if base or head:
        lines.append(f"_Change set: `{base or '?'}` → `{head or '?'}`._")
        lines.append("")

    lines.extend(
        [
            "| Provider | Field | Candidate | Reachable | Provenance | First-party source | Reason |",
            "|---|---|---|---|---|---|---|",
        ]
    )
    for result in results:
        provenance = result["provenance"]
        provenance_cell = (
            f"**{provenance}**" if provenance == NEEDS_REVIEW else f"`{provenance}`"
        )
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{_escape_cell(result['slug'])}`",
                    f"`{_escape_cell(result['field'])}`",
                    _autolink(result["url"]),
                    _escape_cell(result["reachability_note"]),
                    provenance_cell,
                    _autolink(result.get("evidence_url") or ""),
                    _escape_cell(result["reason"]),
                ]
            )
            + " |"
        )

    evidenced = sum(1 for item in results if item["provenance"] == FIRST_PARTY_EVIDENCED)
    review = sum(1 for item in results if item["provenance"] == NEEDS_REVIEW)
    not_applicable = sum(
        1 for item in results if item["provenance"] == NOT_APPLICABLE
    )
    lines.extend(
        [
            "",
            f"**Summary:** {len(results)} changed field(s) — "
            f"{evidenced} first-party evidenced, {review} need manual identity "
            f"review, {not_applicable} not applicable.",
            "",
            "<details><summary>What the provenance statuses mean</summary>",
            "",
            f"- `{FIRST_PARTY_EVIDENCED}` — an independent provider-controlled "
            "page links to the candidate URL.",
            f"- `{NEEDS_REVIEW}` — no independent crosslink was found, the "
            "evidence is product-scoped, or the page is blocked/unknown. A "
            "reviewer must confirm identity.",
            f"- `{NOT_APPLICABLE}` — the field was cleared or is empty.",
            "",
            "HTTP `401`/`403`/`429`, anti-bot pages, redirects, and "
            "discontinued domains remain in manual review. They are neither "
            "automatically approved nor automatically condemned.",
            "",
            "</details>",
            "",
        ]
    )
    return "\n".join(lines)


def load_evidence_file(path: str) -> dict[str, list[Evidence]]:
    """Load offline evidence fixtures.

    Expected shape: ``{"<provider-slug>": [{"url": "...", "html": "..."}]}``.
    """

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("evidence file must be a JSON object keyed by provider slug")

    evidence: dict[str, list[Evidence]] = {}
    for slug, items in data.items():
        entries: list[Evidence] = []
        for item in items or []:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "").strip()
            content = item.get("content") or item.get("html") or ""
            if url and content:
                entries.append(Evidence(url=url, content=str(content)))
        evidence[str(slug)] = entries
    return evidence


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _cmd_collect(args: argparse.Namespace) -> int:
    try:
        changes = collect_changes(args.base, args.head, args.path)
    except (CollectError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    payload = {
        "schema": 1,
        "base": args.base,
        "head": args.head,
        "file": args.path,
        "changes": changes,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(changes)} changed provider field(s) to {output}")
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    payload = json.loads(Path(args.changes).read_text(encoding="utf-8"))
    changes = payload.get("changes") or []
    explicit = load_evidence_file(args.evidence) if args.evidence else {}

    pr_body = ""
    if args.pr_body:
        pr_body = Path(args.pr_body).read_text(encoding="utf-8", errors="replace")

    results: list[dict] = []
    for change in changes:
        candidate = str(change.get("new") or "").strip()
        try:
            if candidate:
                reachability = (
                    probe_url(candidate, timeout=args.timeout)
                    if args.probe
                    else Reachability("not_checked")
                )
            else:
                reachability = Reachability("not_applicable")

            evidence = gather_evidence(
                change,
                fetch_github=args.fetch_evidence,
                pr_body=pr_body,
                explicit=explicit,
                timeout=args.timeout,
            )
            results.append(evaluate_change(change, reachability, evidence))
        except Exception as exc:  # Keep the report available even on a bug.
            results.append(
                {
                    "slug": change.get("slug", "?"),
                    "name": "",
                    "field": change.get("field", "?"),
                    "url": candidate,
                    "reachable": "not_checked",
                    "http_status": None,
                    "page_title": "",
                    "reachability_note": "not checked",
                    "provenance": NEEDS_REVIEW,
                    "reason": f"provenance check failed: {type(exc).__name__}",
                    "evidence_url": None,
                }
            )

    report = render_report(results, base=payload.get("base", ""), head=payload.get("head", ""))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report, encoding="utf-8")
    print(f"wrote provider link provenance report to {output}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Report provenance for changed provider website/docs links."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    collect = subparsers.add_parser(
        "collect", help="extract changed website/docs cells from git"
    )
    collect.add_argument("--base", required=True, help="base git ref")
    collect.add_argument(
        "--head",
        default="HEAD",
        help="head git ref, or WORKTREE to read the file from disk",
    )
    collect.add_argument("--path", default=PROVIDERS_PATH, help="provider CSV path")
    collect.add_argument("--output", required=True, help="JSON output path")
    collect.set_defaults(func=_cmd_collect)

    report = subparsers.add_parser(
        "report", help="evaluate provenance and render a Markdown report"
    )
    report.add_argument("--changes", required=True, help="change-set JSON path")
    report.add_argument("--output", required=True, help="Markdown output path")
    report.add_argument(
        "--probe",
        action="store_true",
        help="check reachability (network; report only)",
    )
    report.add_argument(
        "--fetch-evidence",
        action="store_true",
        help="fetch canonical GitHub READMEs (network; report only)",
    )
    report.add_argument(
        "--pr-body",
        default="",
        help="PR description file; provider-owned URLs are fetched as evidence",
    )
    report.add_argument(
        "--evidence",
        default="",
        help="offline evidence JSON: {slug: [{url, html}]}",
    )
    report.add_argument(
        "--timeout",
        type=float,
        default=8.0,
        help="per-request timeout in seconds (default: 8)",
    )
    report.set_defaults(func=_cmd_report)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
