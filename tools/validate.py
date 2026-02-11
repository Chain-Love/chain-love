import os
import re
import json
from jsonschema import Draft202012Validator
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

def check_schema_validation(schema_validator, data) -> bool:
    """
    Validate data against a JSON schema.

    Args:
        schema_validator (Draft202012Validator): Validator for the JSON schema.
        data (dict): Data to be validated.

    Returns:
        bool: True if data is valid, False otherwise.
    """
    errors = sorted(schema_validator.iter_errors(data), key=lambda e: list(e.absolute_path))
    for err in errors:
        pointer = path_to_json_pointer(err.absolute_path)
        try:
            value = resolve_pointer(data, "/" + "/".join(map(str, err.absolute_path)))
        except Exception:
            value = None
        print("Error message :", err.message)
        print("JSON Pointer  :", pointer)
        print("Offending value:", json.dumps(value, ensure_ascii=False))
        print("Schema path   :", "/".join(map(str, err.absolute_schema_path)))
        print("---")

    return len(errors) == 0

def check_rules_validation(rules_validator, data) -> bool:
    """
    Validate a given set of data against a set of rules.

    Args:
        rules_validator: A RulesValidator object
        data: A dictionary containing the data to validate

    Returns:
        bool: True if all rules pass, False otherwise
    """
    had_errors = False
    for category in data.keys():
        if category in ("columns", "schemaVersion"):
            continue
        errors = rules_validator.validate(data[category])
        for err in errors:
            had_errors = True
            print(f"Error validating {category}: {err}")
            print("---")
    return not had_errors

def check_validation(data, schema_validator, rules_validator) -> bool:
    return check_schema_validation(schema_validator, data) and check_rules_validation(rules_validator, data)

def load_csv_folder(folder) -> dict:
    data = {}
    for category_file_name in os.listdir(folder):
        if not category_file_name.endswith(".csv"):
            continue
        category_name = category_file_name[:-4]
        data[category_name] = load_csv_to_dict_list(f"{folder}/{category_file_name}")

    data, errors = normalize(data)
    if len(errors) > 0:
        print(f"Errors normalizing CSV data from '{folder}':")
        for err in errors:
            print(err)
        exit(1)

    return data

def make_providers_schema(network_schema) -> dict:
    providers_schema = copy.deepcopy(network_schema)
    for definition in providers_schema['$defs'].keys():
        if definition == "columns":
            continue
        if "chain" in providers_schema['$defs'][definition]['required']:
            index = providers_schema['$defs'][definition]['required'].index("chain")
            del providers_schema['$defs'][definition]['required'][index]
    return providers_schema

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

    # Validate networks
    validator = Draft202012Validator(schema)
    for network_spec in os.listdir("json"):
        print(f"Validating {network_spec}...")
        data = None
        with open(f"json/{network_spec}", "r") as f:
            data = json.load(f)
        if not check_validation(data=data, schema_validator=validator, rules_validator=rules):
            had_errors = True

    # Validate providers
    providers_data = load_csv_folder("providers")
    providers_schema = make_providers_schema(network_schema=schema)
    providers_validator = Draft202012Validator(providers_schema)
    if not check_validation(data=providers_data, schema_validator=providers_validator, rules_validator=rules):
        had_errors = True

    if had_errors:
        exit(1)

if __name__ == "__main__":
    main()