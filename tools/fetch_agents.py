"""
Fetch ERC-8004 agent data from per-network Subgraph endpoints and inject
an ``agents`` array into the existing ``json/{network}.json`` files.
Environment variables
---------------------
ERC8004_API_KEY              – Shared subgraph query key for all installations.
ERC8004_SUBGRAPH_IDS       – JSON object: each key is the network label (used for
                             json/{label}.json). Each value is
                             { "chain": "<value for agent.chain>", "url": "<subgraph URL>" }.
                             Example:
                               {"arbitrum": {"chain": "one", "url": "https://proxy.arbitrum.chain.love/..."}}
                             → file json/arbitrum.json, agents get agent["chain"] = "one"
"""
import base64
import gzip
import json
import os
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
import re
import unicodedata
from copy import deepcopy
from typing import Any, Dict, List, Optional, NewType, TypedDict, Tuple
from urllib.parse import unquote_plus


import requests
from jsonschema import Draft202012Validator
from validate import check_schema_validation  # type: ignore

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

NetworkName = NewType("NetworkName", str)
SubgraphQueryURL = NewType("SubgraphQueryURL", str)


class SubgraphEntry(TypedDict):
    chain: str
    url: str


SubgraphConfig = Dict[str, SubgraphEntry]


class AgentRaw(TypedDict):
    id: str
    agentId: str
    owner: str
    # Present only when the deployed subgraph schema includes these fields.
    creator: Optional[str]
    creatorTx: Optional[str]
    agentURI: str
    agentURIType: str
    agentWallet: Optional[str]
    registeredAt: str
    registeredBlock: str
    updatedAt: str
    totalFeedbackCount: str
    activeFeedbackCount: str
    feedbackValueSum: str
    averageRating: Any


class AgentRecord(TypedDict):
    slug: str
    offer: str
    name: Optional[str]
    description: Optional[str]
    image: Optional[str]
    active: Optional[bool]
    supportedTrust: Optional[List[str]]
    registrationType: Optional[str]
    agentId: int
    creator: Optional[str]
    creatorTx: Optional[str]
    owner: str
    agentURI: str
    agentURIType: str
    agentWallet: Optional[str]
    chain: str
    identityRegistry: str
    reputationRegistry: str
    totalFeedbackCount: int
    activeFeedbackCount: int
    averageRating: Any
    rank: int
    registeredAt: int
    updatedAt: int
    starred: bool
    feedbacks: List["FeedbackItem"]


AgentsList = List[AgentRecord]


class GraphQLResponse(TypedDict):
    agents: List[AgentRaw]


class FeedbackAgentRaw(TypedDict):
    agentId: str


class FeedbackItem(TypedDict):
    id: str
    isRevoked: bool
    clientAddress: str
    feedbackIndex: int
    value: str
    valueDecimals: int
    normalizedValue: str
    tag1: str
    tag2: str
    endpoint: str
    createdAt: int
    createdBlock: int
    responses: List["FeedbackResponseItem"]


class FeedbackResponseItem(TypedDict):
    id: str
    responseURI: str
    responseHash: str
    createdAt: int
    createdBlock: int


class FeedbackRaw(TypedDict):
    id: str
    agent: FeedbackAgentRaw
    isRevoked: bool
    clientAddress: str
    feedbackIndex: int
    value: str
    valueDecimals: int
    normalizedValue: str
    tag1: str
    tag2: str
    endpoint: str
    feedbackURI: str
    createdAt: int
    createdBlock: int
    responses: List["FeedbackResponseRaw"]


class FeedbackResponseRaw(TypedDict):
    id: str
    responseURI: str
    responseHash: str
    createdAt: int
    createdBlock: int


class FeedbacksGraphQLResponse(TypedDict):
    feedbacks: List[FeedbackRaw]


JsonObject = Dict[str, Any]

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_DIR = os.path.dirname(__file__)
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.json")
with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
    NETWORK_SCHEMA = json.load(f)

SCHEMA_VALIDATOR = Draft202012Validator(NETWORK_SCHEMA)

VALIDATION_DIR = os.path.join(BASE_DIR, "validation")

def _load_validator(path: str) -> Draft202012Validator:
    with open(path, "r", encoding="utf-8") as f:
        schema = json.load(f)
    return Draft202012Validator(schema)

AGENTS_RESPONSE_VALIDATOR = _load_validator(
    os.path.join(VALIDATION_DIR, "agents_response.schema.json")
)

FEEDBACKS_RESPONSE_VALIDATOR = _load_validator(
    os.path.join(VALIDATION_DIR, "feedbacks_response.schema.json")
)

# ERC-8004 contract addresses (same on every EVM chain via CREATE2)
IDENTITY_REGISTRY = "0x8004A169FB4a3325136EB29fA0ceB6D2e539a432"
REPUTATION_REGISTRY = "0x8004BAa17C55a88189AE136b182e5fdA19dE9b63"

PAGE_SIZE = 1000  # The Graph max entities per page
AGENT_SLUG_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")

# Column order for the agents category (injected into data["columns"])
AGENTS_COLUMNS = [
    "slug",
    "offer",
    "name",
    "rank",
    "agentId",
    "description",
    "registrationType",
    "averageRating",
    "image",
    "active",
    "supportedTrust",
    "creator",
    "creatorTx",
    "owner",
    "agentURI",
    "agentURIType",
    "agentWallet",
    "chain",
    "identityRegistry",
    "reputationRegistry",
    "totalFeedbackCount",
    "activeFeedbackCount",
    "registeredAt",
    "updatedAt",
    "starred",
]

# Ranking quality profile fields ordered by impact in AGENTS_COLUMNS.
# Earlier fields have larger penalties when missing.
# `creator`/`creatorTx` are always present when the subgraph is healthy, so
# excluding them avoids shifting rank weights.
RANK_QUALITY_COLUMNS = [
    c for c in AGENTS_COLUMNS if c not in {"rank", "creator", "creatorTx"}
]

# Strong penalties that enforce:
# - missing name can never appear at the very top against named agents
# - missing name + description ranks below complete (name+description) agents
MISSING_NAME_RANK_PENALTY = 1000.0
MISSING_DESCRIPTION_RANK_PENALTY = 500.0

# ---------------------------------------------------------------------------
# GraphQL query
# ---------------------------------------------------------------------------

# New fields in Agent schema are optional across different deployed subgraph versions.
# So we need both query variants for backward compatibility.
AGENTS_QUERY_WITH_CREATOR = """
query FetchAgents($lastId: ID!) {
  agents(
    first: %d
    where: { id_gt: $lastId }
    orderBy: id
    orderDirection: asc
  ) {
    id
    agentId
    owner
    creator
    creatorTx
    agentURI
    agentURIType
    agentWallet
    registeredAt
    registeredBlock
    updatedAt
    totalFeedbackCount
    activeFeedbackCount
    feedbackValueSum
    averageRating
  }
}
""" % PAGE_SIZE


AGENTS_QUERY_NO_CREATOR = """
query FetchAgents($lastId: ID!) {
  agents(
    first: %d
    where: { id_gt: $lastId }
    orderBy: id
    orderDirection: asc
  ) {
    id
    agentId
    owner
    agentURI
    agentURIType
    agentWallet
    registeredAt
    registeredBlock
    updatedAt
    totalFeedbackCount
    activeFeedbackCount
    feedbackValueSum
    averageRating
  }
}
""" % PAGE_SIZE


FEEDBACKS_QUERY = """
query FetchFeedbacks($lastId: ID!) {
  feedbacks(
    first: %d
    where: { id_gt: $lastId }
    orderBy: id
    orderDirection: asc
  ) {
    id
    agent { agentId }
    isRevoked
    clientAddress
    feedbackIndex
    value
    valueDecimals
    normalizedValue
    tag1
    tag2
    endpoint
    feedbackURI
    createdAt
    createdBlock
    responses(orderBy: createdAt, orderDirection: asc) {
      id
      responseURI
      responseHash
      createdAt
      createdBlock
    }
  }
}
""" % PAGE_SIZE


# ---------------------------------------------------------------------------
# Environment helpers
# ---------------------------------------------------------------------------


class ConfigError(RuntimeError):
    pass


def _utc_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _log(msg: str, network: Optional[str] = None) -> None:
    if network:
        print(f"[{_utc_ts()}] [{network}] {msg}")
    else:
        print(f"[{_utc_ts()}] {msg}")


def _get_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ConfigError(
            f"Environment variable {name} is required but not set or empty"
        )
    return value


def _parse_subgraph_ids() -> SubgraphConfig:
    """Parse ERC8004_SUBGRAPH_IDS JSON env var. Each value must have 'chain' and 'url'."""
    raw = _get_env("ERC8004_SUBGRAPH_IDS")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ConfigError(f"ERC8004_SUBGRAPH_IDS is not valid JSON: {e}")
    if not isinstance(data, dict):
        raise ConfigError("ERC8004_SUBGRAPH_IDS must be a JSON object")
    for key, entry in data.items():
        if not isinstance(entry, dict):
            raise ConfigError(
                f"ERC8004_SUBGRAPH_IDS['{key}'] must be an object with 'chain' and 'url'"
            )
        if "chain" not in entry or "url" not in entry:
            raise ConfigError(
                f"ERC8004_SUBGRAPH_IDS['{key}'] must have 'chain' and 'url'"
            )
    return data  # type: ignore


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------


def load_json_file(path: str) -> JsonObject:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json_file(path: str, data: JsonObject) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


# ---------------------------------------------------------------------------
# ERC-8004 registration file (agentURI)
# ---------------------------------------------------------------------------

# Public IPFS gateway for resolving ipfs:// URIs
IPFS_GATEWAY = "https://ipfs.io/ipfs/"

# Timeout for fetching registration file
REGISTRATION_FETCH_TIMEOUT = 10


def _decode_data_uri_payload(agent_uri: str) -> Optional[str]:
    """
    Decode data: URI payload (application/json; base64, URL-encoded, or gzip).
    Returns decoded UTF-8 string or None on failure.
    Mirrors agent-uri-cell.tsx decodeDataUri / decodeDataUriAsync logic.
    """
    if "," not in agent_uri:
        return None
    head, _, payload = agent_uri.partition(",")
    meta = head.lower()
    payload = payload.strip()
    if "enc=gzip" in meta or "gzip" in meta:
        if "base64" in meta:
            try:
                raw = base64.b64decode(payload)
                return gzip.decompress(raw).decode("utf-8")
            except Exception:
                return None
    if "base64" in meta:
        try:
            raw = base64.b64decode(payload)
            return raw.decode("utf-8")
        except Exception:
            return None
    # URL-encoded (e.g. data:application/json,{%22name%22:...})
    try:
        return unquote_plus(payload)
    except Exception:
        return None


def _fetch_registration_json(agent_uri: str) -> Optional[Dict[str, Any]]:
    """
    Resolve agentURI to JSON per EIP-8004.
    Supports: raw JSON string, data:application/json;base64,..., data: with gzip,
    data: URL-encoded, ipfs://, https://
    Returns parsed JSON (registration object) or None on failure.
    """
    if not agent_uri or not isinstance(agent_uri, str):
        return None
    agent_uri = agent_uri.strip()

    # Raw JSON string (e.g. "{\"name\":\"...\"}")
    if agent_uri.startswith("{") or agent_uri.startswith("["):
        try:
            return json.loads(agent_uri)
        except json.JSONDecodeError:
            return None

    # data: URI (inline JSON)
    if agent_uri.startswith("data:"):
        decoded = _decode_data_uri_payload(agent_uri)
        if decoded is None:
            return None
        try:
            data = json.loads(decoded)
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            return None

    if agent_uri.startswith("ipfs://"):
        cid = agent_uri[7:].strip()
        if not cid:
            return None
        url = f"{IPFS_GATEWAY}{cid}"
        try:
            resp = requests.get(url, timeout=REGISTRATION_FETCH_TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return None
    if agent_uri.startswith("https://") or agent_uri.startswith("http://"):
        try:
            resp = requests.get(agent_uri, timeout=REGISTRATION_FETCH_TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return None
    return None


def _extract_registration_fields(registration: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract EIP-8004 registration file fields for Chain.Love agents.
    Input is the JSON document at agentURI; field names are from that document
    (e.g. "type", "name", "description", "image"). Maps them into artifact
    fields: registrationType <- "type", name, description, image, active,
    supportedTrust. Uses supportedTrusts (plural) from EIP-8004 when present.
    """
    out: Dict[str, Any] = {
        "name": None,
        "description": None,
        "image": None,
        "active": None,
        "supportedTrust": None,
        "registrationType": None,
    }
    if not isinstance(registration, dict):
        return out
    # Registration document at agentURI has field "type" (e.g. registration-v1 URL)
    type_val = registration.get("type")
    if isinstance(type_val, str):
        out["registrationType"] = type_val.strip() or None
    name = registration.get("name")
    if isinstance(name, str):
        out["name"] = name.strip() or None
    desc = registration.get("description")
    if isinstance(desc, str):
        out["description"] = desc.strip() or None
    image = registration.get("image")
    if isinstance(image, str):
        out["image"] = image.strip() or None
    if "active" in registration:
        out["active"] = bool(registration["active"])
    # EIP-8004 registration may use supportedTrusts (plural)
    st = registration.get("supportedTrust") or registration.get("supportedTrusts")
    if isinstance(st, list):
        out["supportedTrust"] = [str(x).strip() for x in st if x]
    return out


def _slugify_agent_name(name: Optional[str]) -> Optional[str]:
    if not isinstance(name, str):
        return None

    ascii_name = (
        unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    )
    slug = AGENT_SLUG_NON_ALNUM_RE.sub("-", ascii_name.lower()).strip("-")
    return slug or None


def _build_agent_slug(agent_id: str, name: Optional[str], chain: str) -> str:
    name_slug = _slugify_agent_name(name)
    chain_slug = AGENT_SLUG_NON_ALNUM_RE.sub("-", chain.lower()).strip("-")
    if name_slug:
        return f"erc8004-agent-{name_slug}-{agent_id}-{chain_slug}"
    return f"erc8004-agent-{agent_id}-{chain_slug}"


# ---------------------------------------------------------------------------
# Subgraph helpers
# ---------------------------------------------------------------------------


def _build_url(subgraphQueryURL: SubgraphQueryURL, erc8004_api_key: str) -> str:
    return f"{subgraphQueryURL}?token={erc8004_api_key}"


def graphql_request(
    url: str, query: str, variables: Optional[Dict[str, Any]] = None
) -> GraphQLResponse:
    """Send a GraphQL POST request and return the parsed JSON body."""
    try:
        resp = requests.post(
            url,
            json={"query": query, "variables": variables or {}},
            headers={"Content-Type": "application/json"},
            timeout=60,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        raise RuntimeError(f"Subgraph request failed: {e}")

    try:
        payload = resp.json()
    except ValueError as e:
        raise RuntimeError(f"Invalid JSON from subgraph: {e}")

    if "errors" in payload:
        raise RuntimeError(
            f"GraphQL errors: {json.dumps(payload['errors'], indent=2)}"
        )

    data = payload.get("data")
    if data is None:
        raise RuntimeError("Subgraph response missing 'data'")

    return data  # type: ignore


def fetch_all_agents(
    network: NetworkName, subgraphQueryUrl: SubgraphQueryURL, erc8004_api_key: str
) -> Optional[List[AgentRaw]]:
    """
    Paginate through all Agent entities.

    Returns list of raw agent dicts, or None on failure.
    """
    url = _build_url(subgraphQueryUrl, erc8004_api_key)
    all_agents: List[AgentRaw] = []
    last_id = ""

    query_with_creator: Optional[str] = AGENTS_QUERY_WITH_CREATOR
    query_no_creator: Optional[str] = AGENTS_QUERY_NO_CREATOR

    # Detect subgraph schema capability once per network.
    active_query: Optional[str] = query_with_creator

    page = 0
    while True:
        page += 1
        if active_query is None:
            # Should never happen, but keep it explicit.
            return None

        try:
            data = graphql_request(url, active_query, {"lastId": last_id})
        except RuntimeError as e:
            msg = str(e)
            # The common failure mode when fields don't exist yet in the deployed subgraph.
            # Different GraphQL servers error messages differently:
            # - Type `Agent` has no field `creator`
            # - Cannot query field "creator" on type "Agent"
            # - Field "creator" doesn't exist
            missing_fields = (
                ("creator" in msg or "creatorTx" in msg)
                and ("no field" in msg or "Cannot query field" in msg or "doesn't exist" in msg)
            )
            if active_query == query_with_creator and missing_fields:
                _log(
                    "INFO: subgraph has no creator fields yet; retrying without creator/creatorTx",
                    str(network),
                )
                active_query = query_no_creator
                continue
            _log(f"WARNING: {e}", str(network))
            return None

        errors = list(AGENTS_RESPONSE_VALIDATOR.iter_errors(data)) # type: ignore
        if errors:
            first = errors[0]
            _log("WARNING: subgraph response schema mismatch", str(network))
            _log(f"  message: {first.message}", str(network))
            _log(f"  path   : {list(first.absolute_path)}", str(network))
            return None

        batch = data.get("agents", [])
        _log(
            f"Agents page {page}: fetched {len(batch)} rows (last_id='{last_id or '<start>'}')",
            str(network),
        )
        if not batch:
            break
        all_agents.extend(batch)
        last_id = batch[-1]["id"]
        if len(batch) < PAGE_SIZE:
            break

    return all_agents


def transform_agent(raw: AgentRaw, chain: NetworkName) -> AgentRecord:
    """
    Map a Subgraph Agent entity to the Chain.Love JSON shape.

    Enriches with EIP-8004 registration file fields (name, description, image,
    active, supportedTrust, registrationType) by fetching and parsing the
    document at agentURI (data:, ipfs://, or https://). registrationType
    comes from the "type" field of that JSON (e.g. registration-v1).
    """
    agent_id = raw["agentId"]
    agent_uri = raw.get("agentURI") or ""
    reg_data = _fetch_registration_json(agent_uri)
    reg = _extract_registration_fields(reg_data) if reg_data else _extract_registration_fields({})
    name = reg.get("name")
    out: AgentRecord = {
        "slug": _build_agent_slug(agent_id, name, str(chain)),
        "offer": name if name else f"Agent #{agent_id}",
        "name": name,
        "description": reg.get("description"),
        "image": reg.get("image"),
        "active": reg.get("active"),
        "supportedTrust": reg.get("supportedTrust"),
        "registrationType": reg.get("registrationType"),
        "agentId": int(agent_id),
        "owner": raw["owner"],
        "agentURI": raw["agentURI"],
        "agentURIType": raw.get("agentURIType", "unknown"),
        "agentWallet": raw.get("agentWallet"),
        "chain": chain,
        "identityRegistry": IDENTITY_REGISTRY,
        "reputationRegistry": REPUTATION_REGISTRY,
        # Default aggregates from `agents` query.
        # If we successfully parse Feedback entities, these will be overridden later.
        "totalFeedbackCount": int(raw["totalFeedbackCount"]),
        "activeFeedbackCount": int(raw["activeFeedbackCount"]),
        "averageRating": raw["averageRating"],
        "rank": 0,  # placeholder — overwritten by compute_ranks()
        "registeredAt": int(raw["registeredAt"]),
        "updatedAt": int(raw["updatedAt"]),
        "starred": False,
        "feedbacks": [],
    }

    # Backward compatible: older subgraph deployments won't have these fields.
    if "creator" in raw:
        # These are Bytes in the subgraph; Graph usually returns 0x-prefixed hex strings.
        out["creator"] = raw["creator"]
    if "creatorTx" in raw:
        out["creatorTx"] = raw["creatorTx"]

    return out


def _coerce_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def fetch_all_feedbacks_by_agent(
    network: NetworkName,
    subgraphQueryUrl: SubgraphQueryURL,
    erc8004_api_key: str,
    agent_onchain_ids: Optional[set[str]] = None,
    per_agent_limit: int = 20,
) -> Dict[str, List[FeedbackItem]]:
    """
    Scan Feedback entities and return per-agent feedback lists.

    Returns mapping:
      agentId -> [feedbackItem, ...]
    """
    url = _build_url(subgraphQueryUrl, erc8004_api_key)
    feedbacks: Dict[str, List[FeedbackItem]] = {}
    last_id = ""

    page = 0
    while True:
        page += 1
        try:
            data = graphql_request(url, FEEDBACKS_QUERY, {"lastId": last_id})
        except RuntimeError as e:
            _log(f"WARNING: {e}", str(network))
            return {}

        errors = list(FEEDBACKS_RESPONSE_VALIDATOR.iter_errors(data))  # type: ignore
        if errors:
            first = errors[0]
            _log("WARNING: feedback response schema mismatch", str(network))
            _log(f"  message: {first.message}", str(network))
            _log(f"  path   : {list(first.absolute_path)}", str(network))
            return {}

        batch = data.get("feedbacks", [])
        _log(
            f"Feedbacks page {page}: fetched {len(batch)} rows (last_id='{last_id or '<start>'}')",
            str(network),
        )
        if not batch:
            break

        for fb in batch:
            agent_id = str(fb["agent"]["agentId"])
            if agent_onchain_ids is not None and agent_id not in agent_onchain_ids:
                continue

            if agent_id not in feedbacks:
                feedbacks[agent_id] = []

            responses_raw = fb.get("responses", [])
            responses: List[FeedbackResponseItem] = []
            for response in responses_raw:
                responses.append(
                    {
                        "id": str(response["id"]),
                        "responseURI": str(response["responseURI"]),
                        "responseHash": str(response["responseHash"]),
                        "createdAt": _coerce_int(response["createdAt"]),
                        "createdBlock": _coerce_int(response["createdBlock"]),
                    }
                )

            item: FeedbackItem = {
                "id": str(fb["id"]),
                "isRevoked": bool(fb["isRevoked"]),
                "clientAddress": str(fb["clientAddress"]),
                "feedbackIndex": _coerce_int(fb["feedbackIndex"]),
                "value": str(fb["value"]),
                "valueDecimals": _coerce_int(fb["valueDecimals"]),
                "normalizedValue": str(fb["normalizedValue"]),
                "tag1": str(fb["tag1"]),
                "tag2": str(fb["tag2"]),
                "endpoint": str(fb["endpoint"]),
                "feedbackURI": str(fb["feedbackURI"]),
                "createdAt": _coerce_int(fb["createdAt"]),
                "createdBlock": _coerce_int(fb["createdBlock"]),
                "responses": responses,
            }

            if len(feedbacks[agent_id]) < per_agent_limit:
                feedbacks[agent_id].append(item)
                continue

            # Keep only the latest feedbacks by `createdAt`.
            # (We might see older entries after reaching the limit due to entity-id ordering.)
            min_item = min(feedbacks[agent_id], key=lambda x: x["createdAt"])
            if item["createdAt"] >= min_item["createdAt"]:
                min_idx = feedbacks[agent_id].index(min_item)
                feedbacks[agent_id][min_idx] = item

        last_id = batch[-1]["id"]
        if len(batch) < PAGE_SIZE:
            break

    return feedbacks


# ---------------------------------------------------------------------------
# Bayesian ranking
# ---------------------------------------------------------------------------


def _is_missing_profile_value(value: Any) -> bool:
    if value is None:
        return True

    if isinstance(value, str):
        normalized = value.strip().lower()
        return normalized in {"", "unknown", "none", "not available", "n/a", "na", "null"}

    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0

    return False


def _profile_completeness_penalty(agent: AgentRecord) -> int:
    """
    Compute weighted penalty for missing profile fields.

    Weight is derived from AGENTS_COLUMNS order:
    earlier columns apply stronger penalties.
    """
    total = len(RANK_QUALITY_COLUMNS)
    penalty = 0
    for index, field in enumerate(RANK_QUALITY_COLUMNS):
        if _is_missing_profile_value(agent.get(field)):
            penalty += total - index
    return penalty


def _ranking_penalty(agent: AgentRecord) -> float:
    penalty = float(_profile_completeness_penalty(agent))
    if _is_missing_profile_value(agent.get("name")):
        penalty += MISSING_NAME_RANK_PENALTY
    if _is_missing_profile_value(agent.get("description")):
        penalty += MISSING_DESCRIPTION_RANK_PENALTY
    return penalty


def compute_ranks(agents: AgentsList) -> None:
    """
    Assign a per-chain Bayesian rank to each agent **in place**.

    Uses the IMDB-style weighted rating formula:
        score = (v / (v + m)) * R  +  (m / (v + m)) * C

    Where:
        v = agent's activeFeedbackCount
        m = median activeFeedbackCount across all agents (minimum threshold)
        R = agent's averageRating
        C = global mean averageRating across all agents

    Profile completeness is folded into ranking via penalty:
        adjusted_score = bayesian_score - ranking_penalty
    Missing fields increase ranking_penalty, with stronger impact for earlier
    columns in AGENTS_COLUMNS. Missing name/description use extra hard penalties.
    Agents are ranked by adjusted_score descending (then agentId ascending).
    Agents with zero feedback are still ranked after agents with feedback.
    """
    if not agents:
        return

    # Separate agents with and without feedback
    with_feedback = [a for a in agents if a["activeFeedbackCount"] > 0]
    without_feedback = [a for a in agents if a["activeFeedbackCount"] == 0]

    if not with_feedback:
        # No feedback data at all — rank by profile completeness only.
        no_feedback_scored = [(-_ranking_penalty(a), a) for a in agents]
        no_feedback_scored.sort(key=lambda t: (-t[0], t[1]["agentId"]))
        for i, (_, a) in enumerate(no_feedback_scored):
            a["rank"] = i + 1
        return

    # Compute m (median active feedback count)
    counts = sorted(a["activeFeedbackCount"] for a in with_feedback)
    mid = len(counts) // 2
    if len(counts) % 2 == 0:
        m = (counts[mid - 1] + counts[mid]) / 2.0
    else:
        m = float(counts[mid])
    m = max(m, 1.0)  # floor at 1 to avoid division edge cases

    # Compute C (global mean average rating)
    ratings = [float(a["averageRating"]) for a in with_feedback]
    C = sum(ratings) / len(ratings)

    # Compute adjusted score for agents with feedback
    scored: list = []
    for a in with_feedback:
        v = float(a["activeFeedbackCount"])
        R = float(a["averageRating"])
        bayesian_score = (v / (v + m)) * R + (m / (v + m)) * C
        adjusted_score = bayesian_score - _ranking_penalty(a)
        scored.append((adjusted_score, a))

    # Keep original ordering semantics: score descending, then agentId.
    scored.sort(key=lambda t: (-t[0], t[1]["agentId"]))

    # Assign ranks
    rank = 1
    for _, a in scored:
        a["rank"] = rank
        rank += 1

    # Agents without feedback get the remaining ranks (completeness-aware).
    without_feedback_scored = [(-_ranking_penalty(a), a) for a in without_feedback]
    without_feedback_scored.sort(key=lambda t: (-t[0], t[1]["agentId"]))
    for _, a in without_feedback_scored:
        a["rank"] = rank
        rank += 1


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

MAX_WORKERS = 8


def _process_one_network(
    label: str, entry: SubgraphEntry, erc8004_api_key: str
) -> Tuple[str, str, Optional[JsonObject], Optional[JsonObject], int]:
    """Process one network; returns (label, path, original_data, enriched_data, count)."""
    started_at = datetime.now(timezone.utc)
    chain = entry["chain"]
    subgraph_url = entry["url"]
    path = os.path.join("json", f"{label}.json")
    if not os.path.isfile(path):
        _log(f"WARNING: {path} not found, skipping", label)
        return (label, path, None, None, 0)
    _log(f"START processing {path}", label)
    try:
        original_data = load_json_file(path)
    except Exception as e:
        _log(f"WARNING: failed to read JSON file: {e}", label)
        return (label, path, None, None, 0)
    if not check_schema_validation(SCHEMA_VALIDATOR, original_data):
        _log(
            "ERROR: original data does not conform to schema, skipping enrichment",
            label,
        )
        return (label, path, None, None, 0)
    _log("Fetching agents from subgraph", label)
    raw_agents = fetch_all_agents(NetworkName(label), SubgraphQueryURL(subgraph_url), erc8004_api_key)
    if raw_agents is None:
        _log("ABORT: failed to fetch agents", label)
        return (label, path, original_data, None, 0)
    _log(f"Fetched agents: {len(raw_agents)}", label)

    # Map Feedback.agent -> Agent.agentId (on-chain id), not Agent.id (entity id).
    agent_entity_ids = {a["agentId"] for a in raw_agents}
    _log("Fetching feedbacks from subgraph", label)
    feedbacks_by_agent = fetch_all_feedbacks_by_agent(
        NetworkName(label),
        SubgraphQueryURL(subgraph_url),
        erc8004_api_key,
        agent_onchain_ids={str(x) for x in agent_entity_ids},
        per_agent_limit=20,
    )
    _log(f"Feedback map built for {len(feedbacks_by_agent)} agents", label)

    def _transform(a: AgentRaw) -> AgentRecord:
        agent_entity_id = str(a["agentId"])
        agent_feedbacks = feedbacks_by_agent.get(agent_entity_id, [])
        agent = transform_agent(a, NetworkName(chain))
        agent["feedbacks"] = agent_feedbacks
        return agent

    agents: AgentsList = [_transform(a) for a in raw_agents]
    compute_ranks(agents)
    agents.sort(key=lambda a: a["agentId"])
    _log(f"Transformed and ranked {len(agents)} agents", label)
    enriched = deepcopy(original_data)
    enriched["agents"] = agents
    if isinstance(enriched.get("columns"), dict):
        enriched["columns"]["agents"] = list(AGENTS_COLUMNS)
    if not check_schema_validation(SCHEMA_VALIDATOR, enriched):
        _log("ERROR: enriched data does not conform to schema, skipping write", label)
        return (label, path, original_data, None, len(agents))
    elapsed = (datetime.now(timezone.utc) - started_at).total_seconds()
    _log(f"DONE in {elapsed:.2f}s", label)
    return (label, path, original_data, enriched, len(agents))


def process_all_networks() -> None:
    started_at = datetime.now(timezone.utc)
    _log("fetch_agents.py started")
    erc8004_api_key = _get_env("ERC8004_API_KEY")
    subgraph_ids = _parse_subgraph_ids()
    if not subgraph_ids:
        _log("ERC8004_SUBGRAPH_IDS is empty. Nothing to do.")
        return
    if not os.path.isdir("json"):
        _log("No 'json' directory found, nothing to enrich")
        return
    workers = min(MAX_WORKERS, len(subgraph_ids))
    _log(f"Networks to process: {len(subgraph_ids)} | workers: {workers}")
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(_process_one_network, label, entry, erc8004_api_key): label
            for label, entry in subgraph_ids.items()
        }
        for future in as_completed(futures):
            try:
                label, path, orig, enriched, count = future.result()
            except Exception as e:
                _log(f"ERROR: {e}", futures[future])
                continue
            if enriched is not None and orig is not None and enriched != orig:
                try:
                    save_json_file(path, enriched)
                    _log(f"JSON updated with {count} agents", label)
                except Exception as e:
                    _log(f"ERROR: failed to write enriched JSON: {e}", label)
            else:
                _log("No JSON changes to write", label)
    elapsed = (datetime.now(timezone.utc) - started_at).total_seconds()
    _log(f"fetch_agents.py finished in {elapsed:.2f}s")


def main() -> None:
    try:
        process_all_networks()
    except ConfigError as e:
        print(f"Configuration error: {e}")
        raise


if __name__ == "__main__":
    main()
