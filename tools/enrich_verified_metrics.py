import json
import os
from copy import deepcopy
from typing import Any, Dict, List, Optional

import requests
from jsonschema import Draft202012Validator
from validate import check_schema_validation


VERIFIED_API_TOKEN_ENV = "VERIFIED_API_TOKEN"
SLA_MONITORING_SUBGRAPH_URL_ENV = "SLA_MONITORING_SUBGRAPH_URL"
GRAPH_API_KEY_ENV = "GRAPH_API_KEY"

VERIFIED_CATEGORIES = ["apis"]
BPS_DENOMINATOR = 10000

BASE_DIR = os.path.dirname(__file__)
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.json")
with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
    NETWORK_SCHEMA = json.load(f)

SCHEMA_VALIDATOR = Draft202012Validator(NETWORK_SCHEMA)


def _load_validator(path: str) -> Draft202012Validator:
    with open(path, "r", encoding="utf-8") as f:
        schema = json.load(f)
    return Draft202012Validator(schema)


VALIDATION_DIR = os.path.join(BASE_DIR, "validation")
VERIFIED_PROVIDERS_VALIDATOR = _load_validator(
    os.path.join(VALIDATION_DIR, "verified_providers.schema.json")
)
SLA_RESPONSE_VALIDATOR = _load_validator(
    os.path.join(VALIDATION_DIR, "sla_response.schema.json")
)

_SUBDOMAIN_OVERRIDES: Dict[str, str] = {
    "ethereum": "eth",
}


def _network_to_hostname(network: str) -> str:
    subdomain = _SUBDOMAIN_OVERRIDES.get(network, network)
    return f"{subdomain}.chain.love"


class EnrichmentConfigError(RuntimeError):
    pass


def _get_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise EnrichmentConfigError(f"Environment variable {name} is required but not set or empty")
    return value


def load_json_file(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json_file(path: str, data: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def fetch_verified_providers(network: str, token: str) -> Optional[List[Dict[str, str]]]:
    """
    Returns a list of { slug, serviceId } for the given network, or:
      - None if the API call failed
      - []  if the API returned 200 OK with an empty list
    """
    hostname = _network_to_hostname(network)
    url = f"https://{hostname}/external-api/toolbox/api/verified-providers"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[{network}] WARNING: failed to fetch verified providers: {e}")
        return None

    try:
        data = resp.json()
    except ValueError as e:
        print(f"[{network}] WARNING: invalid JSON from verified-providers: {e}")
        return None

    errors = list(VERIFIED_PROVIDERS_VALIDATOR.iter_errors(data))
    if errors:
        print(f"[{network}] WARNING: verified-providers response schema mismatch")
        first = errors[0]
        print("  message:", first.message)
        print("  path   :", list(first.absolute_path))
        return None

    providers: List[Dict[str, str]] = data
    return providers


def fetch_sla_metrics_for_network(
    network: str,
    service_ids: List[str],
    subgraph_url: str,
    graph_api_key: str,
) -> Optional[Dict[str, Any]]:
    """
    Fetch SLA metrics for a single network in one GraphQL batch.

    Returns a mapping { serviceId -> metrics_dict } or None if the request failed.
    """
    if not service_ids:
        return {}

    unique_ids: List[str] = list(set(service_ids))

    query = """
    query ($serviceIds: [String!]!) {
      serviceHealthMetrics(where: { id_in: $serviceIds }) {
        id
        totalProofs
        downtimeCount
        latencyCount
        blockLatencyAvg
        timeLatencyAvg
        consensusExecutions
        violations
      }
    }
    """

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {graph_api_key}",
    }

    try:
        resp = requests.post(
            subgraph_url,
            json={"query": query, "variables": {"serviceIds": unique_ids}},
            headers=headers,
            timeout=20,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[{network}] WARNING: SLA subgraph request failed: {e}")
        return None

    try:
        payload = resp.json()
    except ValueError as e:
        print(f"[{network}] WARNING: invalid JSON from SLA subgraph: {e}")
        return None

    if "errors" in payload:       
        print(f"[{network}] WARNING: SLA subgraph returned errors: {payload['errors']}")
        return None

    errors = list(SLA_RESPONSE_VALIDATOR.iter_errors(payload))
    if errors:
        print(f"[{network}] WARNING: SLA subgraph response schema mismatch")
        first = errors[0]
        print("  message:", first.message)
        print("  path   :", list(first.absolute_path))
        return None

 
    def _has_activity(m: Dict[str, Any]) -> bool:
        return int(m["totalProofs"]) > 0 or int(m["consensusExecutions"]) > 0

    active_metrics = filter(_has_activity, metrics_list)

    metrics_by_id: Dict[str, Any] = {m["id"]: m for m in active_metrics}

    return metrics_by_id


def normalize_metrics(metric: dict) -> dict:
    total_proofs = int(metric["totalProofs"])
    downtime_count = int(metric["downtimeCount"])
    latency_count = int(metric["latencyCount"])
    consensus_exec = int(metric["consensusExecutions"])
    violations = int(metric["violations"])

    proofs_bps = 0
    if total_proofs > 0:
        total_count = downtime_count + latency_count
        proofs_bps = (total_count * BPS_DENOMINATOR) // total_proofs

    consensus_bps = 0
    if consensus_exec > 0:
        consensus_bps = (violations * BPS_DENOMINATOR) // consensus_exec

    if total_proofs > 0 and consensus_exec > 0:
        downtime_bps = (proofs_bps + consensus_bps) // 2
    elif consensus_exec == 0:
        downtime_bps = proofs_bps
    else:
        downtime_bps = consensus_bps

    verified_uptime = BPS_DENOMINATOR - downtime_bps

    return {
        "verifiedUptime": str(verified_uptime),
        "verifiedLatency": str(metric["timeLatencyAvg"]),
        "verifiedBlocksBehindAvg": str(metric["blockLatencyAvg"]),
    }

def enrich_network_data(
    network: str,
    original_data: Dict[str, Any],
    verified_providers: List[Dict[str, Any]],
    sla_metrics_by_id: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Apply verified metrics enrichment for a single network.

    Rules recap:
      - If verified_providers is empty (200 OK, []): all apis items get verified* = null.
      - If SLA failed (sla_metrics_by_id is None): do not change any verified* fields.
      - If SLA succeeded:
          * join: slug -> serviceId -> metrics
          * filter metrics to only those with totalProofs>0 || consensusExecutions>0 (done earlier)
          * if provider no longer verified: verified* = null.
    """
    enriched = deepcopy(original_data)

    if not verified_providers:
        for category in VERIFIED_CATEGORIES:
            for item in enriched.get(category, []):
                item["verifiedUptime"] = None
                item["verifiedLatency"] = None
                item["verifiedBlocksBehindAvg"] = None
        return enriched

    if sla_metrics_by_id is None:
        return enriched

    slug_to_service_id: Dict[str, str] = {p["slug"]: p["serviceId"] for p in verified_providers}

    for category in VERIFIED_CATEGORIES:
        for item in enriched.get(category, []):
            slug = item["slug"]

            service_id = slug_to_service_id.get(slug)
            if not service_id:
                item["verifiedUptime"] = None
                item["verifiedLatency"] = None
                item["verifiedBlocksBehindAvg"] = None
                continue

            metric = sla_metrics_by_id.get(service_id)
            if metric is None:
                continue

            item.update(normalize_metrics(metric))

    return enriched


def process_all_networks() -> None:
    verified_api_token = _get_env(VERIFIED_API_TOKEN_ENV)
    subgraph_url = _get_env(SLA_MONITORING_SUBGRAPH_URL_ENV)
    graph_api_key = _get_env(GRAPH_API_KEY_ENV)

    if not os.path.isdir("json"):
        print("No 'json' directory found, nothing to enrich")
        return

    for filename in sorted(os.listdir("json")):
        if not filename.endswith(".json"):
            continue

        network = filename[:-5]
        path = os.path.join("json", filename)

        print(f"[{network}] Processing {path}")

        try:
            original_data = load_json_file(path)
        except Exception as e:
            print(f"[{network}] WARNING: failed to read JSON file: {e}")
            continue

        if not check_schema_validation(schema_validator=SCHEMA_VALIDATOR, data=original_data):
            print(f"[{network}] ERROR: original data does not conform to schema, skipping enrichment")
            continue

        providers = fetch_verified_providers(network, verified_api_token)
        if providers is None:
            continue

        sla_metrics_by_id: Optional[Dict[str, Any]] = None
        if len(providers) > 0:
            service_ids = [p["serviceId"] for p in providers]
            sla_metrics_by_id = fetch_sla_metrics_for_network(
                network=network,
                service_ids=service_ids,
                subgraph_url=subgraph_url,
                graph_api_key=graph_api_key,
            )

        enriched_data = enrich_network_data(
            network=network,
            original_data=original_data,
            verified_providers=providers,
            sla_metrics_by_id=sla_metrics_by_id,
        )

        if not check_schema_validation(schema_validator=SCHEMA_VALIDATOR, data=enriched_data):
            print(f"[{network}] ERROR: enriched data does not conform to schema, skipping write")
            continue

        if enriched_data != original_data:
            try:
                save_json_file(path, enriched_data)
                print(f"[{network}] JSON updated with verified metrics")
            except Exception as e:
                print(f"[{network}] ERROR: failed to write enriched JSON: {e}")


def main() -> None:
    try:
        process_all_networks()
    except EnrichmentConfigError as e:
        print(f"Configuration error: {e}")
        raise


if __name__ == "__main__":
    main()

