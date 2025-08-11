import os
import json
from jsonschema import Draft7Validator
from jsonpointer import resolve_pointer
from collections import deque

def path_to_json_pointer(path_deque):
    """Convert error.absolute_path (deque) to a JSON Pointer string"""
    parts = list(path_deque)
    if not parts:
        return "#"
    # Build pointer like "#/person/emails/1"
    return "#" + "".join("/" + str(p) for p in parts)

def main():
    schema = None
    with open("schema.json", "r") as f:
        schema = json.load(f)
    validator = Draft7Validator(schema)
    for network_spec in os.listdir("json"):
        print(f"Validating {network_spec}...")
        data = None
        with open(f"json/{network_spec}", "r") as f:
            data = json.load(f)
        errors = sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path))
        for err in errors:
            pointer = path_to_json_pointer(err.absolute_path)
            try:
                value = resolve_pointer(data, "/" + "/".join(map(str, err.absolute_path)))
            except Exception:
                # sometimes the error concerns parent structure (e.g., missing required key)
                value = None
            print("Error message :", err.message)
            print("JSON Pointer  :", pointer)
            print("Offending value:", json.dumps(value, ensure_ascii=False))
            print("Schema path   :", "/".join(map(str, err.absolute_schema_path)))
            print("---")
if __name__ == "__main__":
    main()
