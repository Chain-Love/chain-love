
import os
import json
import requests
from typing import NewType, Dict, Any

from jsonschema import Draft202012Validator
from validate import check_schema_validation  # type: ignore


NetworkName = NewType("NetworkName", str)
Config = Dict[NetworkName, Any]

def load_config() -> Config:
    CONFIG_ENV_NAME = "ERC8004_SUBGRAPH_IDS"
    if CONFIG_ENV_NAME not in os.environ:
        raise ValueError(f"Missing config environment variable: {CONFIG_ENV_NAME}")
    
    config_json = json.loads(os.environ[CONFIG_ENV_NAME])

    config: Config = {}
    config = {NetworkName(network_name): config_json[network_name] for network_name in config_json}
    
    return config

def fetch_agents(network_name: NetworkName) -> Any:
    url: str = f"https://app.chain.love/agents-json?network={network_name}"
    res = requests.get(url)
    res.raise_for_status()
    return res.json()

def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
    
def save_json(path: str, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def main() -> None:
    config: Config = load_config()

    schema_path = "schema.json"
    if not os.path.exists(schema_path):
        raise FileNotFoundError(f"Schema file not found: {schema_path}")
    
    schema = load_json(schema_path)
    validator = Draft202012Validator(schema)
    
    for network_name in config:
        print(f"Processing network: {network_name}")
        network_json_path = f"json/{network_name}.json"
        if not os.path.exists(network_json_path):
            raise FileNotFoundError(f"JSON file not found: {network_json_path}")

        network_json: Any = load_json(network_json_path)
        agents: Any = fetch_agents(network_name)
        network_json["agents"] = agents
        if not check_schema_validation(validator, network_json):
            raise ValueError(f"Schema validation failed for network: {network_name}")
        save_json(network_json_path, network_json)


if __name__ == "__main__":
    main()
