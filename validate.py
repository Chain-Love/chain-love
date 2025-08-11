import os
import json
from jsonschema import validate

def main():
    schema = None
    with open("schema.json", "r") as f:
        schema = json.load(f)

    for network_spec in os.listdir("json"):
        print(f"Validating {network_spec}...")
        data = None
        with open(f"json/{network_spec}", "r") as f:
            data = json.load(f)
        validate(instance=data, schema=schema)

if __name__ == "__main__":
    main()
