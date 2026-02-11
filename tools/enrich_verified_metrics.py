import json
import os
from copy import deepcopy
from typing import Any, Dict, List, Optional

import requests


VERIFIED_API_TOKEN_ENV = "VERIFIED_API_TOKEN"
SLA_MONITORING_SUBGRAPH_URL_ENV = "SLA_MONITORING_SUBGRAPH_URL"
GRAPH_API_KEY_ENV = "GRAPH_API_KEY"

VERIFIED_CATEGORIES = ["apis"]
BPS_DENOMINATOR = 10000


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


def fetch_verified_providers(network: str, token: str) -> Optional[List[Dict[str, Any]]]:
    """
    Returns a list of { slug, serviceId } for the given network, or:
      - None if the API call failed (network/error case)
      - []  if the API returned 200 OK with an empty list (valid 'no providers verified' state)
    """
    url = f"https://{network}.chain.love/toolbox/api/verified-providers"
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

    # Expect either a bare array or an object with 'providers' – support both defensively.
    if isinstance(data, list):
        providers = data
    else:
        providers = data.get("providers", [])

    if not isinstance(providers, list):
        print(f"[{network}] WARNING: verified-providers response has unexpected shape")
        return None

    # Normalize entries to dicts
    normalized: List[Dict[str, Any]] = []
    for entry in providers:
        if not isinstance(entry, dict):
            continue
        slug = entry.get("slug")
        service_id = entry.get("serviceId")
        if isinstance(slug, str) and isinstance(service_id, str) and slug and service_id:
            normalized.append({"slug": slug, "serviceId": service_id})

    return normalized


def fetch_sla_metrics_for_network(
    network: str,
    service_ids: List[str],
    subgraph_url: str,
    graph_api_key: str,
) -> Optional[Dict[str, Any]]:
    """
    Fetch SLA metrics for a single network in one GraphQL batch.

    Returns a mapping { serviceId -> metrics_dict } or:
      - None if the request failed (we must preserve existing verified fields)
    """
    if not service_ids:
        return {}

    # De-duplicate while preserving order
    seen = set()
    unique_ids: List[str] = []
    for sid in service_ids:
        if sid not in seen:
            seen.add(sid)
            unique_ids.append(sid)

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
        # UI sends: Authorization: Bearer <GRAPH_API_KEY>.
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

    data = payload.get("data") or {}
    metrics_list = data.get("serviceHealthMetrics") or []

    if not isinstance(metrics_list, list):
        print(f"[{network}] WARNING: SLA subgraph response has unexpected shape")
        return None

    metrics_by_id: Dict[str, Any] = {}
    for m in metrics_list:
        if not isinstance(m, dict):
            continue
        # Apply the same filter as UI:
        # keep only entries where totalProofs > 0 or consensusExecutions > 0
        total_proofs = m.get("totalProofs") or 0
        consensus_exec = m.get("consensusExecutions") or 0
        try:
            total_proofs_num = int(total_proofs)
        except (TypeError, ValueError):
            total_proofs_num = 0
        try:
            consensus_exec_num = int(consensus_exec)
        except (TypeError, ValueError):
            consensus_exec_num = 0

        if total_proofs_num <= 0 and consensus_exec_num <= 0:
            continue

        sid = m.get("id")
        if isinstance(sid, str) and sid:
            metrics_by_id[sid] = m

    return metrics_by_id


def normalize_metrics(metric: Dict[str, Any]) -> Dict[str, Any]:
    """
    Approximate port of the UI's normalizeMetrics logic.

    NOTE: This is meant to be semantically equivalent to the UI. If the UI logic
    changes, this function should be updated in lockstep.
    """
    def _to_int(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    total_proofs = _to_int(metric.get("totalProofs"))
    downtime_count = _to_int(metric.get("downtimeCount"))
    latency_count = _to_int(metric.get("latencyCount"))
    consensus_exec = _to_int(metric.get("consensusExecutions"))
    violations = _to_int(metric.get("violations"))

    # Proof-based downtime in basis points
    proof_downtime_bps = 0
    if total_proofs > 0:
        # UI uses (downtimeCount + latencyCount) and integer division with BigInt.
        # Mirror that semantics here with pure integer math.
        total_events = downtime_count + latency_count
        if total_events < 0:
            total_events = 0
        proof_downtime_bps = (total_events * BPS_DENOMINATOR) // total_proofs

    # Consensus-based downtime in basis points
    consensus_downtime_bps = 0
    if consensus_exec > 0:
        # Keep integer division to stay close to UI BigInt behavior.
        consensus_downtime_bps = (violations * BPS_DENOMINATOR) // consensus_exec

    if proof_downtime_bps and consensus_downtime_bps:
        downtime_bps = int((proof_downtime_bps + consensus_downtime_bps) / 2)
    elif proof_downtime_bps:
        downtime_bps = proof_downtime_bps
    else:
        downtime_bps = consensus_downtime_bps

    downtime_bps = max(0, min(BPS_DENOMINATOR, downtime_bps))
    verified_uptime = BPS_DENOMINATOR - downtime_bps

    # Latency metrics – mirror UI shape: strings in JSON
    block_latency_avg = metric.get("blockLatencyAvg")
    time_latency_avg = metric.get("timeLatencyAvg")

    # Prefer time-based latency when available, fall back to block latency.
    # Both are stored as strings in JSON to match UI's BigInt→string behavior.
    latency_value: Optional[str] = None
    if time_latency_avg is not None:
        latency_value = str(time_latency_avg)
    elif latency_count > 0 and block_latency_avg is not None:
        latency_value = str(block_latency_avg)

    blocks_behind_avg: Optional[str] = None
    if block_latency_avg is not None:
        blocks_behind_avg = str(block_latency_avg)

    return {
        "verifiedUptime": verified_uptime,
        "verifiedLatency": latency_value,
        "verifiedBlocksBehindAvg": blocks_behind_avg,
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

    # No verified providers -> explicitly null out all verified* in apis.
    if len(verified_providers) == 0:
        apis = enriched.get("apis")
        if isinstance(apis, list):
            for item in apis:
                if isinstance(item, dict):
                    item["verifiedUptime"] = None
                    item["verifiedLatency"] = None
                    item["verifiedBlocksBehindAvg"] = None
        return enriched

    # Non-empty verified_providers but SLA failed -> keep everything as-is.
    if sla_metrics_by_id is None:
        return enriched

    # Build join maps
    slug_to_service_id: Dict[str, str] = {}
    current_verified_slugs = set()
    for entry in verified_providers:
        slug = entry.get("slug")
        service_id = entry.get("serviceId")
        if isinstance(slug, str) and isinstance(service_id, str) and slug and service_id:
            slug_to_service_id[slug] = service_id
            current_verified_slugs.add(slug)

    for category in VERIFIED_CATEGORIES:
        items = enriched.get(category)
        if not isinstance(items, list):
            continue

        for item in items:
            if not isinstance(item, dict):
                continue

            slug = item.get("slug")
            if not isinstance(slug, str) or not slug:
                # No join key – leave verified fields as-is.
                continue

            # Currently verified provider?
            service_id = slug_to_service_id.get(slug)
            if service_id:
                metric = sla_metrics_by_id.get(service_id)
                if metric is None:
                    # SLA subgraph had no record for this serviceId despite 200 OK.
                    # Treat as "no data yet" and preserve existing verified fields.
                    continue

                normalized = normalize_metrics(metric)
                item["verifiedUptime"] = normalized["verifiedUptime"]
                # Ensure latency-related fields are stored as strings.
                item["verifiedLatency"] = (
                    None if normalized["verifiedLatency"] is None else str(normalized["verifiedLatency"])
                )
                item["verifiedBlocksBehindAvg"] = (
                    None
                    if normalized["verifiedBlocksBehindAvg"] is None
                    else str(normalized["verifiedBlocksBehindAvg"])
                )
                continue

            # Not in current verified set -> provider no longer verified.
            item["verifiedUptime"] = None
            item["verifiedLatency"] = None
            item["verifiedBlocksBehindAvg"] = None

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

        providers = fetch_verified_providers(network, verified_api_token)
        if providers is None:
            # External API down / invalid – skip this network.
            continue

        # If providers is an empty list, enrich_network_data will null out verified*.
        sla_metrics_by_id: Optional[Dict[str, Any]] = None
        if len(providers) > 0:
            service_ids = [p["serviceId"] for p in providers if isinstance(p.get("serviceId"), str)]
            sla_metrics_by_id = fetch_sla_metrics_for_network(
                network=network,
                service_ids=service_ids,
                subgraph_url=subgraph_url,
                graph_api_key=graph_api_key,
            )
            # If SLA failed (None), enrich_network_data will preserve verified* fields.

        enriched_data = enrich_network_data(
            network=network,
            original_data=original_data,
            verified_providers=providers,
            sla_metrics_by_id=sla_metrics_by_id,
        )

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
        # Fail fast on configuration errors so CI clearly shows misconfiguration.
        print(f"Configuration error: {e}")
        raise


if __name__ == "__main__":
    main()

