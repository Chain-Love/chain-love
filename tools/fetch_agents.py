"""
Fetch ERC-8004 agent data from per-network Subgraph endpoints and inject
an ``agents`` array into the existing ``json/{network}.json`` files.
Environment variables
---------------------
ERC8004_API_KEY              – Shared subgraph query key for all installations.
ERC8004_SUBGRAPH_IDS       – JSON object mapping network names (matching the
                             json/{network}.json filenames) to subgraph query URLs.
                             Example:
                               {"arbitrum":"https://proxy.arbitrum.chain.love/subgraphs/name/arbitrum-one/8004-Watchtower-Subgraph"}
"""
import base64
import json
import os
from copy import deepcopy
from typing import Any, Dict, List, Optional, NewType, TypedDict

import requests
from jsonschema import Draft202012Validator
from validate import check_schema_validation  # type: ignore

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

NetworkName = NewType("NetworkName", str)
SubgraphQueryURL = NewType("SubgraphQueryURL", str)

SubgraphQueryURLByNetwork = Dict[NetworkName, SubgraphQueryURL]


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

class CategoryMeta(TypedDict):
    key: str
    label: str
    icon: Optional[str]
    description: str

class ColumnMeta(TypedDict):
    key: str
    label: str
    icon: Optional[str]
    description: str
    filter: Optional[str]
    sorting: Optional[str]
    pinning: Optional[str]
    cellType: Optional[str]

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
     "agentId",
    "description",
    "rank",
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

# Category meta entry (ensures meta.categories.agents exists for validation)
AGENTS_CATEGORY_META: CategoryMeta = {
    "key": "agents",
    "label": "Agents",
    "icon": "lucide:Bot",
    "description": "ERC-8004 on-chain AI agents with identity and reputation.",
}

# Column meta for agent-specific fields (injected into meta.columns if missing)
AGENTS_COLUMN_META: Dict[str, ColumnMeta] = {
    "agentId": {
        "key": "agentId",
        "label": "Agent ID",
        "icon": "lucide:Hash",
        "description": "ERC-8004 on-chain agent identifier.",
        "filter": None,
        "sorting": "number",
        "pinning": None,
        "cellType": None,
    },
    "owner": {
        "key": "owner",
        "label": "Owner",
        "icon": "lucide:User",
        "description": "Address that registered the agent.",
        "filter": "searchableMultiSelect",
        "sorting": "string",
        "pinning": None,
        "cellType": "address",
    },
    "agentURI": {
        "key": "agentURI",
        "label": "Agent URI",
        "icon": "lucide:ExternalLink",
        "description": "Off-chain metadata link (IPFS/HTTPS).",
        "filter": None,
        "sorting": "arrayLength",
        "pinning": None,
        "cellType": "link",
    },
    "agentURIType": {
        "key": "agentURIType",
        "label": "URI Type",
        "icon": None,
        "description": "Type of the Agent URI (ipfs, https, etc.).",
        "filter": "select",
        "sorting": "arrayLength",
        "pinning": None,
        "cellType": None,
    },
    "agentWallet": {
        "key": "agentWallet",
        "label": "Agent Wallet",
        "icon": "lucide:Wallet",
        "description": "Wallet address associated with the agent.",
        "filter": None,
        "sorting": "arrayLength",
        "pinning": None,
        "cellType": "address",
    },
    "identityRegistry": {
        "key": "identityRegistry",
        "label": "Identity Registry",
        "icon": "lucide:FileKey",
        "description": "ERC-8004 Identity Registry contract address.",
        "filter": None,
        "sorting": "string",
        "pinning": None,
        "cellType": "address",
    },
    "reputationRegistry": {
        "key": "reputationRegistry",
        "label": "Reputation Registry",
        "icon": "lucide:Star",
        "description": "ERC-8004 Reputation Registry contract address.",
        "filter": None,
        "sorting": "string",
        "pinning": None,
        "cellType": "address",
    },
    "totalFeedbackCount": {
        "key": "totalFeedbackCount",
        "label": "Total Feedback",
        "icon": "lucide:MessageSquare",
        "description": "Total number of feedback entries (including revoked).",
        "filter": None,
        "sorting": "number",
        "pinning": None,
        "cellType": None,
    },
    "activeFeedbackCount": {
        "key": "activeFeedbackCount",
        "label": "Active Feedback",
        "icon": "lucide:MessageSquareCheck",
        "description": "Number of non-revoked feedback entries.",
        "filter": None,
        "sorting": "number",
        "pinning": None,
        "cellType": None,
    },
    "averageRating": {
        "key": "averageRating",
        "label": "Avg Rating",
        "icon": "lucide:TrendingUp",
        "description": "Average reputation rating from active feedback.",
        "filter": None,
        "sorting": "string",
        "pinning": None,
        "cellType": None,
    },
    "registeredAt": {
        "key": "registeredAt",
        "label": "Registered At",
        "icon": "lucide:CalendarPlus",
        "description": "Unix timestamp when the agent was registered on-chain.",
        "filter": None,
        "sorting": "number",
        "pinning": None,
        "cellType": None,
    },
    "updatedAt": {
        "key": "updatedAt",
        "label": "Updated At",
        "icon": "lucide:CalendarClock",
        "description": "Unix timestamp of the last on-chain update.",
        "filter": None,
        "sorting": "number",
        "pinning": None,
        "cellType": None,
    },
    "rank": {
        "key": "rank",
        "label": "Rank",
        "icon": "lucide:Trophy",
        "description": "Bayesian-weighted rank among all agents on this chain (1 = best).",
        "filter": None,
        "sorting": "number",
        "pinning": None,
        "cellType": None,
    },
    "name": {
        "key": "name",
        "label": "Name",
        "icon": "lucide:Tag",
        "description": "Agent name from ERC-8004 registration file (agentURI).",
        "filter": "searchableMultiSelect",
        "sorting": "string",
        "pinning": "left",
        "cellType": "agent",
    },
    "image": {
        "key": "image",
        "label": "Image",
        "icon": "lucide:Image",
        "description": "Image URL from ERC-8004 registration file.",
        "filter": None,
        "sorting": None,
        "pinning": None,
        "cellType": "link",
    },
    "active": {
        "key": "active",
        "label": "Active",
        "icon": "lucide:CheckCircle",
        "description": "Whether the agent is marked active in the registration file (ERC-8004).",
        "filter": "select",
        "sorting": "boolean",
        "pinning": None,
        "cellType": None,
    },
    "supportedTrust": {
        "key": "supportedTrust",
        "label": "Supported Trust",
        "icon": "lucide:Shield",
        "description": "Trust models (e.g. reputation, crypto-economic) from ERC-8004.",
        "filter": "searchableMultiSelect",
        "sorting": "arrayLength",
        "pinning": None,
        "cellType": "arrayPopover",
    },
}

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


def _parse_subgraph_ids() -> SubgraphQueryURLByNetwork:
    """Parse ERC8004_SUBGRAPH_IDS JSON env var into a dict."""
    raw = _get_env("ERC8004_SUBGRAPH_IDS")
    try:
        ids = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ConfigError(f"ERC8004_SUBGRAPH_IDS is not valid JSON: {e}")
    if not isinstance(ids, dict):
        raise ConfigError("ERC8004_SUBGRAPH_IDS must be a JSON object")
    return ids  # type: ignore


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


def _fetch_registration_json(agent_uri: str) -> Optional[Dict[str, Any]]:
    """
    Resolve agentURI to JSON per EIP-8004.
    Supports: data:application/json;base64,..., ipfs://, https://
    Returns parsed JSON or None on failure.
    """
    if not agent_uri or not isinstance(agent_uri, str):
        return None
    agent_uri = agent_uri.strip()
    if agent_uri.startswith("data:application/json;base64,"):
        try:
            b64 = agent_uri.split(",", 1)[1]
            data = base64.b64decode(b64)
            return json.loads(data.decode("utf-8"))
        except Exception:
            return None
    if agent_uri.startswith("ipfs://"):
        # ipfs://Qm... or ipfs://cid
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
    Returns dict with name, description, image, active, supportedTrust (all optional).
    """
    out: Dict[str, Any] = {
        "name": None,
        "description": None,
        "image": None,
        "active": None,
        "supportedTrust": None,
    }
    if not isinstance(registration, dict):
        return out
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
    st = registration.get("supportedTrust")
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
    active, supportedTrust) when agentURI is resolvable.
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

    Agents are ranked by score descending (rank 1 = best).
    Agents with zero feedback are ranked last, ordered by agentId.
    """
    if not agents:
        return

    # Separate agents with and without feedback
    with_feedback = [a for a in agents if a["activeFeedbackCount"] > 0]
    without_feedback = [a for a in agents if a["activeFeedbackCount"] == 0]

    if not with_feedback:
        # No feedback data at all — rank by agentId ascending
        agents.sort(key=lambda a: a["agentId"])
        for i, a in enumerate(agents):
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

    # Compute Bayesian score for agents with feedback
    scored: list = []
    for a in with_feedback:
        v = float(a["activeFeedbackCount"])
        R = float(a["averageRating"])
        score = (v / (v + m)) * R + (m / (v + m)) * C
        scored.append((score, a))

    # Sort by score descending, then by agentId ascending for ties
    scored.sort(key=lambda t: (-t[0], t[1]["agentId"]))

    # Assign ranks
    rank = 1
    for _, a in scored:
        a["rank"] = rank
        rank += 1

    # Agents without feedback get the remaining ranks, ordered by agentId
    without_feedback.sort(key=lambda a: a["agentId"])
    for a in without_feedback:
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

    for network, subgraph_id in subgraph_ids.items():
        path = os.path.join("json", f"{network}.json")

        if not os.path.isfile(path):
            print(f"[{network}] WARNING: {path} not found, skipping")
            continue

        print(f"[{network}] Processing {path}")

        try:
            original_data = load_json_file(path)
        except Exception as e:
            print(f"[{network}] WARNING: failed to read JSON file: {e}")
            continue

        if not check_schema_validation(
            schema_validator=SCHEMA_VALIDATOR, data=original_data
        ):
            print(
                f"[{network}] ERROR: original data does not conform to schema, "
                "skipping enrichment"
            )
            continue

        # Fetch agents from subgraph
        raw_agents = fetch_all_agents(network, subgraph_id, erc8004_api_key)
        if raw_agents is None:
            continue

        agents: AgentsList = [transform_agent(a, network) for a in raw_agents]
        compute_ranks(agents)
        agents.sort(key=lambda a: a["agentId"])
        print(f"[{network}] Fetched {len(agents)} agents")

        # Inject into enriched copy
        enriched = deepcopy(original_data)
        enriched["agents"] = agents

        # Ensure columns includes agents
        if "columns" in enriched:
            enriched["columns"]["agents"] = AGENTS_COLUMNS

        # Ensure meta.categories.agents exists (needed for validation)
        meta = enriched.get("meta", {})
        categories = meta.get("categories", {})
        if "agents" not in categories:
            categories["agents"] = AGENTS_CATEGORY_META
            meta["categories"] = categories
            enriched["meta"] = meta

        # Ensure agent-specific columns use our meta (overwrite so pinning, cellType, etc. are correct)
        columns_meta = meta.get("columns", {})
        for col_key, col_def in AGENTS_COLUMN_META.items():
            columns_meta[col_key] = col_def
        meta["columns"] = columns_meta
        enriched["meta"] = meta

        # Validate enriched data
        if not check_schema_validation(
            schema_validator=SCHEMA_VALIDATOR, data=enriched
        ):
            print(
                f"[{network}] ERROR: enriched data does not conform to schema, "
                "skipping write"
            )
            continue

        if enriched != original_data:
            try:
                save_json_file(path, enriched)
                print(f"[{network}] JSON updated with {len(agents)} agents")
            except Exception as e:
                print(f"[{network}] ERROR: failed to write enriched JSON: {e}")


def main() -> None:
    try:
        process_all_networks()
    except ConfigError as e:
        print(f"Configuration error: {e}")
        raise


if __name__ == "__main__":
    main()
