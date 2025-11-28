import os
import re
import json
from jsonschema import Draft7Validator
from jsonpointer import resolve_pointer
from csv_to_json import load_csv_to_dict_list, normalize
import copy

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

def rule_slug_kebab_case(data):
    errors = []
    KEBAB_CASE_RE = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
    for idx, item in enumerate(data):
        slug = item.get("slug")
        if not bool(KEBAB_CASE_RE.match(slug)):
            errors.append(f"Item {idx}: slug '{slug}' must be kebab-case")
    return errors

def rule_provider_casing_consistent(data):
    return rule_template_casing_consistent(data, "provider")

def rule_template_casing_consistent(data, column_name):
    errors = []
    seen = {}
    for idx, item in enumerate(data):
        column_value = item.get(column_name)
        if column_value is None:
            continue
        normalized_spelling = column_value.lower().strip()
        if normalized_spelling in seen.keys():
            spellings_except_current = list(filter(lambda x: x != column_value, seen[normalized_spelling]))
            if len(spellings_except_current) == 0:
                continue
            quoted_spellings = list(map(lambda x: f"'{x}'", spellings_except_current))
            known_spellings = ", ".join(quoted_spellings)
            errors.append(f"Item {idx}: Inconsistent casing for {column_name} '{column_value}': got {known_spellings} and '{column_value}'")
        else:
            seen[normalized_spelling] = set()
        seen[normalized_spelling].add(column_value)
    return errors

def rule_action_buttons_is_list_of_links(data):
    errors = []
    for idx, item in enumerate(data):
        action_buttons = item.get("actionButtons")
        if action_buttons is None:
            continue
        if type(action_buttons) != list:
            errors.append(f"Item {idx}: action_buttons must be a list")
            continue
        for item_idx, button in enumerate(action_buttons):
            if not is_markdown_link(button):
                errors.append(f"Item {idx}: action_button[{item_idx}] must be a markdown link")
    return errors

def rule_no_unclosed_markdown(data):
    errors = []
    for idx, item in enumerate(data):
        for key, value in item.items():
            if has_unclosed_markdown(value):
                errors.append(f"Item {idx}: Markdown unclosed in field '{key}'")
    return errors

def has_unclosed_markdown(s: str) -> bool:
    if type(s) != str:
        return False

    if len(s) == 0:
        return False
    
    # Pairs that must be closed: **, *, _, `, [ ]( )
    # Check bold/italic/code
    if s.count("**") % 2 != 0:
        return True
    if s.count("*") % 2 != 0 and s.count("**") == 0:  # single * for italic
        return True
    if s.count("_") % 2 != 0:
        return True
    if s.count("`") % 2 != 0:
        return True
    
    # Check link brackets [text](url)
    # Must have same count of [ and ] and ( and )
    if s.count("[") != s.count("]"):
        return True
    if s.count("(") != s.count(")"):
        return True
    
    return False

def is_markdown_link(s: str) -> bool:
    if type(s) != str:
        return False
    
    if len(s) == 0:
        return False
    
    pattern = r"(?:\[(?P<text>.*?)\])\((?P<link>.*?)\)"
    return re.match(pattern, s) is not None

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
    rules.add_rule(rule_no_unclosed_markdown)
    rules.add_rule(rule_action_buttons_is_list_of_links)
    rules.add_rule(rule_provider_casing_consistent)
    rules.add_rule(rule_slug_kebab_case)

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
            if category == "columns":
                continue
            errors = rules.validate(data[category])
            for err in errors:
                had_errors = True
                print(f"Error validating {category}: {err}")
                print("---")

    # Create providers data
    providers_data = {}
    for category in os.listdir("providers"):
        if not category.endswith(".csv"):
            continue
        category_name = category[:-4]
        providers_data[category_name] = load_csv_to_dict_list(f"providers/{category}")

    # Normalize providers data
    providers_data, errors = normalize(providers_data)
    if len(errors) > 0:
        print(f"Errors while normalizing providers JSON:")
        for error in errors:
            print(error)
        exit(1)
    
    # Override provider schema so the chain field is not required
    provider_schema = copy.deepcopy(schema)
    for definition in provider_schema['$defs'].keys():
        if definition == "columns":
            continue
        if "chain" in provider_schema['$defs'][definition]['required']:
            index = provider_schema['$defs'][definition]['required'].index("chain")
            del provider_schema['$defs'][definition]['required'][index]
    provider_validator = Draft7Validator(provider_schema)

    # Validate providers data against schema
    errors = sorted(provider_validator.iter_errors(providers_data), key=lambda e: list(e.absolute_path))
    for err in errors:
        had_errors = True
        pointer = path_to_json_pointer(err.absolute_path)
        try:
            value = resolve_pointer(providers_data, "/" + "/".join(map(str, err.absolute_path)))
        except Exception:
            # sometimes the error concerns parent structure (e.g., missing required key)
            value = None
        print("Error message :", err.message)
        print("JSON Pointer  :", pointer)
        print("Offending value:", json.dumps(value, ensure_ascii=False))
        print("Schema path   :", "/".join(map(str, err.absolute_schema_path)))
        print("---")

    if had_errors:
        exit(1)

if __name__ == "__main__":
    main()
