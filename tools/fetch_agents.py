"""
Fetch ERC-8004 agent data from per-network Subgraph endpoints and inject
an ``agents`` array into the existing ``json/{network}.json`` files.
Environment variables
---------------------
ERC8004_API_KEY              – Shared subgraph query key for all installations.
ERC8004_SUBGRAPH_IDS       – JSON object: each key is a label, each value is
                             { "chain": "<chainKey>", "url": "<subgraph URL>" }.
                             ``chain`` is used for json/{chain}.json and agent.chain.
                             Example:
                               {"arbitrum": {"chain": "arbitrum-one", "url": "https://proxy.arbitrum.chain.love/subgraphs/name/arbitrum-one/8004-Watchtower-Subgraph"}}
"""
import base64
import gzip
import json
import os
from copy import deepcopy
from typing import Any, Dict, List, Optional, NewType, TypedDict
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


AgentsList = List[AgentRecord]


class GraphQLResponse(TypedDict):
    agents: List[AgentRaw]


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

# ERC-8004 contract addresses (same on every EVM chain via CREATE2)
IDENTITY_REGISTRY = "0x8004A169FB4a3325136EB29fA0ceB6D2e539a432"
REPUTATION_REGISTRY = "0x8004BAa17C55a88189AE136b182e5fdA19dE9b63"

PAGE_SIZE = 1000  # The Graph max entities per page

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
RANK_QUALITY_COLUMNS = [c for c in AGENTS_COLUMNS if c != "rank"]

# Strong penalties that enforce:
# - missing name can never appear at the very top against named agents
# - missing name + description ranks below complete (name+description) agents
MISSING_NAME_RANK_PENALTY = 1000.0
MISSING_DESCRIPTION_RANK_PENALTY = 500.0

# ---------------------------------------------------------------------------
# GraphQL query
# ---------------------------------------------------------------------------

AGENTS_QUERY = """
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

# ---------------------------------------------------------------------------
# Environment helpers
# ---------------------------------------------------------------------------


class ConfigError(RuntimeError):
    pass


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

    while True:
        try:
            data = graphql_request(url, AGENTS_QUERY, {"lastId": last_id})
        except RuntimeError as e:
            print(f"[{network}] WARNING: {e}")
            return None

        errors = list(AGENTS_RESPONSE_VALIDATOR.iter_errors(data)) # type: ignore
        if errors:
            first = errors[0]
            print(f"[{network}] WARNING: subgraph response schema mismatch")
            print("  message:", first.message)
            print("  path   :", list(first.absolute_path))
            return None

        batch = data.get("agents", [])
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
    return {
        "slug": f"erc8004-agent-{agent_id}",
        "offer": name if name else f"Agent #{agent_id}",
        "name": reg.get("name"),
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
        "totalFeedbackCount": int(raw["totalFeedbackCount"]),
        "activeFeedbackCount": int(raw["activeFeedbackCount"]),
        "averageRating": raw["averageRating"],
        "rank": 0,  # placeholder — overwritten by compute_ranks()
        "registeredAt": int(raw["registeredAt"]),
        "updatedAt": int(raw["updatedAt"]),
        "starred": False,
    }


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


def process_all_networks() -> None:
    erc8004_api_key = _get_env("ERC8004_API_KEY")
    subgraph_ids = _parse_subgraph_ids()

    if not subgraph_ids:
        print("ERC8004_SUBGRAPH_IDS is empty. Nothing to do.")
        return

    if not os.path.isdir("json"):
        print("No 'json' directory found, nothing to enrich")
        return

    for _label, entry in subgraph_ids.items():
        chain = entry["chain"]
        subgraph_url = entry["url"]
        path = os.path.join("json", f"{chain}.json")

        if not os.path.isfile(path):
            print(f"[{chain}] WARNING: {path} not found, skipping")
            continue

        print(f"[{chain}] Processing {path}")

        try:
            original_data = load_json_file(path)
        except Exception as e:
            print(f"[{chain}] WARNING: failed to read JSON file: {e}")
            continue

        if not check_schema_validation(
            schema_validator=SCHEMA_VALIDATOR, data=original_data
        ):
            print(
                f"[{chain}] ERROR: original data does not conform to schema, "
                "skipping enrichment"
            )
            continue

        # Fetch agents from subgraph
        raw_agents = fetch_all_agents(
            NetworkName(chain),
            SubgraphQueryURL(subgraph_url),
            erc8004_api_key,
        )
        if raw_agents is None:
            continue

        agents: AgentsList = [transform_agent(a, NetworkName(chain)) for a in raw_agents]
        compute_ranks(agents)
        agents.sort(key=lambda a: a["agentId"])
        print(f"[{chain}] Fetched {len(agents)} agents")

        # Inject into enriched copy
        enriched = deepcopy(original_data)
        enriched["agents"] = agents

        # agents column order is sourced from this script (AGENTS_COLUMNS).
        columns = enriched.get("columns")
        if isinstance(columns, dict):
            columns["agents"] = list(AGENTS_COLUMNS)

        # Validate enriched data
        if not check_schema_validation(
            schema_validator=SCHEMA_VALIDATOR, data=enriched
        ):
            print(
                f"[{chain}] ERROR: enriched data does not conform to schema, "
                "skipping write"
            )
            continue

        if enriched != original_data:
            try:
                save_json_file(path, enriched)
                print(f"[{chain}] JSON updated with {len(agents)} agents")
            except Exception as e:
                print(f"[{chain}] ERROR: failed to write enriched JSON: {e}")


def main() -> None:
    try:
        process_all_networks()
    except ConfigError as e:
        print(f"Configuration error: {e}")
        raise


if __name__ == "__main__":
    main()
