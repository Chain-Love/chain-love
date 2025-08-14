import os
import json
from jsonschema import Draft7Validator
from jsonpointer import resolve_pointer

class Validator:
    def __init__(self):
        self.rules = []

    def add_rule(self, rule_func):
        """Add a new validation rule function."""
        self.rules.append(rule_func)

    def validate(self, data):
        """Run all registered validation rules."""
        errors = []
        for rule in self.rules:
            errors.extend(rule(data))
        return errors

def rule_slug_unique(data):
    errors = []
    seen = set()
    for idx, item in enumerate(data):
        slug = item.get("slug")
        if slug in seen:
            errors.append(f"Item {idx}: Duplicate slug '{slug}'")
        else:
            seen.add(slug)
    return errors

def path_to_json_pointer(path_deque):
    """Convert error.absolute_path (deque) to a JSON Pointer string"""
    parts = list(path_deque)
    if not parts:
        return "#"
    # Build pointer like "#/person/emails/1"
    return "#" + "".join("/" + str(p) for p in parts)

def main():
    had_errors = False

    schema = None
    with open("schema.json", "r") as f:
        schema = json.load(f)

    rules = Validator()
    rules.add_rule(rule_slug_unique)

    validator = Draft7Validator(schema)
    for network_spec in os.listdir("json"):
        print(f"Validating {network_spec}...")
        data = None
        with open(f"json/{network_spec}", "r") as f:
            data = json.load(f)
        
        # Validate data against schema
        errors = sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path))
        for err in errors:
            had_errors = True
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
        
        # Validate data against rules
        for category in data.keys():
            errors = rules.validate(data[category])
            for err in errors:
                had_errors = True
                print(f"Error validating {category}: {err}")
                print("---")
        

    if had_errors:
        exit(1)

if __name__ == "__main__":
    main()
