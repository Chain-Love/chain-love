"""
Fetch ERC-8004 agent data from per-network Subgraph endpoints and inject
an ``agents`` array into the existing ``json/{network}.json`` files.

Environment variables
---------------------
GRAPH_API_KEY              – Shared API key for The Graph gateway.
ERC8004_SUBGRAPH_IDS       – JSON object mapping network names (matching the
                             json/{network}.json filenames) to Subgraph IDs.
                             Example:
                               {"arbitrum":"ABC","ethereum":"DEF","base":"GHI","polygon":"JKL"}
"""
import json
import os
from copy import deepcopy
from typing import Any, Dict, List, Optional

import requests
from jsonschema import Draft202012Validator
from validate import check_schema_validation  # source of truth

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

# The Graph gateway URL template
GRAPH_GATEWAY = "https://gateway.thegraph.com/api/{key}/subgraphs/id/{id}"

# ERC-8004 contract addresses (same on every EVM chain via CREATE2)
IDENTITY_REGISTRY = "0x8004A169FB4a3325136EB29fA0ceB6D2e539a432"
REPUTATION_REGISTRY = "0x8004BAa17C55a88189AE136b182e5fdA19dE9b63"

PAGE_SIZE = 1000  # The Graph max entities per page

# Column order for the agents category (injected into data["columns"])
AGENTS_COLUMNS = [
    "slug",
    "offer",
    "agentId",
    "owner",
    "agentURI",
    "agentURIType",
    "agentWallet",
    "chain",
    "identityRegistry",
    "reputationRegistry",
    "totalFeedbackCount",
    "activeFeedbackCount",
    "averageRating",
    "registeredAt",
    "updatedAt",
    "starred",
]

# Category meta entry (ensures meta.categories.agents exists for validation)
AGENTS_CATEGORY_META = {
    "key": "agents",
    "label": "Agents",
    "icon": "lucide:Bot",
    "description": "ERC-8004 on-chain AI agents with identity and reputation.",
}

# Column meta for agent-specific fields (injected into meta.columns if missing)
AGENTS_COLUMN_META = {
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
        "sorting": None,
        "pinning": None,
        "cellType": "link",
    },
    "agentURIType": {
        "key": "agentURIType",
        "label": "URI Type",
        "icon": None,
        "description": "Type of the Agent URI (ipfs, https, etc.).",
        "filter": "select",
        "sorting": "string",
        "pinning": None,
        "cellType": None,
    },
    "agentWallet": {
        "key": "agentWallet",
        "label": "Agent Wallet",
        "icon": "lucide:Wallet",
        "description": "Wallet address associated with the agent.",
        "filter": None,
        "sorting": None,
        "pinning": None,
        "cellType": "address",
    },
    "identityRegistry": {
        "key": "identityRegistry",
        "label": "Identity Registry",
        "icon": "lucide:FileKey",
        "description": "ERC-8004 Identity Registry contract address.",
        "filter": None,
        "sorting": None,
        "pinning": None,
        "cellType": "address",
    },
    "reputationRegistry": {
        "key": "reputationRegistry",
        "label": "Reputation Registry",
        "icon": "lucide:Star",
        "description": "ERC-8004 Reputation Registry contract address.",
        "filter": None,
        "sorting": None,
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
        "sorting": "number",
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


def _parse_subgraph_ids() -> Dict[str, str]:
    """Parse ERC8004_SUBGRAPH_IDS JSON env var into a dict."""
    raw = _get_env("ERC8004_SUBGRAPH_IDS")
    try:
        ids = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ConfigError(f"ERC8004_SUBGRAPH_IDS is not valid JSON: {e}")
    if not isinstance(ids, dict):
        raise ConfigError("ERC8004_SUBGRAPH_IDS must be a JSON object")
    return ids


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------


def load_json_file(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json_file(path: str, data: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Subgraph helpers
# ---------------------------------------------------------------------------


def _build_url(subgraph_id: str, graph_api_key: str) -> str:
    return GRAPH_GATEWAY.format(key=graph_api_key, id=subgraph_id)


def graphql_request(
    url: str, query: str, variables: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
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

    return data


def fetch_all_agents(
    network: str, subgraph_id: str, graph_api_key: str
) -> Optional[List[Dict[str, Any]]]:
    """
    Paginate through all Agent entities.

    Returns list of raw agent dicts, or None on failure.
    """
    url = _build_url(subgraph_id, graph_api_key)
    all_agents: List[Dict[str, Any]] = []
    last_id = ""

    while True:
        try:
            data = graphql_request(url, AGENTS_QUERY, {"lastId": last_id})
        except RuntimeError as e:
            print(f"[{network}] WARNING: {e}")
            return None

        errors = list(AGENTS_RESPONSE_VALIDATOR.iter_errors(data))
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


def transform_agent(raw: Dict[str, Any], chain: str) -> Dict[str, Any]:
    """
    Map a Subgraph Agent entity to the Chain.Love JSON shape.

    The output mirrors the per-offer structure used by other categories
    (slug, offer, chain, starred, …) so the website can render it in
    the same table component.
    """
    agent_id = raw["agentId"]
    return {
        "slug": f"erc8004-agent-{agent_id}",
        "offer": f"Agent #{agent_id}",
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
        "registeredAt": int(raw["registeredAt"]),
        "updatedAt": int(raw["updatedAt"]),
        "starred": False,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def process_all_networks() -> None:
    graph_api_key = _get_env("GRAPH_API_KEY")
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
        raw_agents = fetch_all_agents(network, subgraph_id, graph_api_key)
        if raw_agents is None:
            continue

        agents = [transform_agent(a, network) for a in raw_agents]
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

        # Ensure agent-specific columns exist in meta.columns
        columns_meta = meta.get("columns", {})
        for col_key, col_def in AGENTS_COLUMN_META.items():
            if col_key not in columns_meta:
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
