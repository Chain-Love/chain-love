import os
import re
import json
from jsonschema import Draft202012Validator
from jsonpointer import resolve_pointer
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

def rule_chain_is_lowercase(data):
    errors = []
    for idx, item in enumerate(data):
        if "chain" not in item.keys():
            # chain is optional
            continue
        if not item["chain"].islower():
            errors.append(f"Item {idx}: chain must be lowercase: want '{item['chain'].lower()}', got '{item['chain']}'. Please check all categories for the current network.")
    return errors

# A URL is data, not markup. Underscores (subquery_network) inside one must not
# be counted as markdown (issue #3656 finding 4). The target may carry one level
# of balanced parentheses, so https://en.wikipedia.org/wiki/Chain_(blockchain)
# is consumed whole and does not leave an unbalanced ")" behind.
#
# A URL body also stops at the characters markdown uses as delimiters, so a
# URL can no longer swallow the markup that follows it: the previous revision
# consumed the "**" of "https://example.com/**unclosed" and the cell was
# reported clean (review on #3657). Whitespace and parentheses stay excluded so
# the balanced-paren alternative can do its job.
URL_BODY = r"[^\s()*`\[\]]"
URL_RE = re.compile(rf"https?://(?:{URL_BODY}+|\((?:{URL_BODY}*)?\))*")

# Underscore runs as delimiters, in the only form this heuristic needs: a run
# can close when a non-space precedes it and no word character follows, and can
# open when no word character precedes it and a non-space follows. Mirrors
# CommonMark's flanking rules without the punctuation subtleties.
_UNDERSCORE = re.compile(r"_")


def _word_char(ch: str) -> bool:
    return ch.isascii() and ch.isalnum()


def _unclosed_underscore_span(t: str) -> bool:
    """True when a ``_`` opens emphasis that nothing later in ``t`` closes.

    A run with a word character on both sides sits inside a word -- a snake_case
    identifier such as ``latest_known_version``, or a handle such as ``0xppl_``
    -- and cannot be a delimiter, so it is not counted at all.

    A run that can close is only paired against a span already open. That
    asymmetry is deliberate: an orphan closer (``0xppl_``, ``handle_``) is data,
    while an opener with no closer after it (``_unclosed``, ``broken _italic``)
    is the unclosed span this rule exists to report.
    """
    depth = 0
    for match in _UNDERSCORE.finditer(t):
        at = match.start()
        before = t[at - 1] if at > 0 else ""
        after = t[at + 1] if at + 1 < len(t) else ""
        can_close = bool(before) and not before.isspace() and not (after and _word_char(after))
        can_open = bool(after) and not after.isspace() and not (before and _word_char(before))
        if can_close and depth:
            depth -= 1
        elif can_open:
            depth += 1
    return depth > 0


def has_unclosed_markdown(s: str) -> bool:
    if type(s) != str:
        return False

    if len(s) == 0:
        return False

    # Everything below is counted on the cell with its URLs removed.
    t = URL_RE.sub("", s)

    # Pairs that must be closed: **, *, _, `, [ ]( )
    # Check bold/italic/code
    if t.count("**") % 2 != 0:
        return True
    # Count non-bold asterisks: subtract the stars consumed by ** spans, so a
    # stray single-* span is caught even when the cell also contains **bold**.
    if (t.count("*") - 2 * t.count("**")) % 2 != 0:  # single * for italic
        return True
    # Underscores inside a URL are already gone with the URL, and ones inside a
    # word are data. Anywhere else an underscore is an emphasis delimiter, so
    # report a cell that opens an `_` span nothing closes. Deciding this from
    # the delimiter's position -- rather than counting underscores whenever the
    # cell happens to contain unrelated markup -- is what keeps "_unclosed" and
    # "broken _italic" flagged (review on #3657) while a trailing handle
    # underscore stays clean, and stops a cell that mixes snake_case with real
    # markdown from being flagged for the identifier.
    if _unclosed_underscore_span(t):
        return True
    if t.count("`") % 2 != 0:
        return True

    # Check link brackets [text](url)
    # Must have same count of [ and ] and ( and )
    if t.count("[") != t.count("]"):
        return True
    if t.count("(") != t.count(")"):
        return True

    return False

# A markdown link must be the whole cell (`fullmatch`, so trailing junk is no
# longer swallowed) and its target may carry one level of balanced parentheses,
# e.g. https://en.wikipedia.org/wiki/Chain_(blockchain). The previous
# non-greedy `(?P<link>.*?)\)` stopped at the first `)`, so that URL was
# captured - and validated - as ".../Chain_(blockchain".
# Kept at module scope so tests can assert the captured target is intact.
MARKDOWN_LINK_RE = re.compile(r"\[(?P<text>.*?)\]\((?P<link>(?:[^()]|\([^()]*\))*)\)")


def is_markdown_link(s: str) -> bool:
    if type(s) != str:
        return False

    if len(s) == 0:
        return False

    return MARKDOWN_LINK_RE.fullmatch(s) is not None

def _data_categories(data):
    return {k for k in data.keys() if k not in ("columns", "meta", "schemaVersion")}


def rule_meta_categories_consistent(data):
    errors = []

    meta_categories = data.get("meta", {}).get("categories", {})
    data_categories = _data_categories(data)

    for cat in data_categories:
        if cat not in meta_categories:
            errors.append(
                f"Meta error: category '{cat}' exists in data but missing in meta.categories"
            )

    for key, meta in meta_categories.items():
        if meta.get("key") != key:
            errors.append(
                f"Meta error: meta.categories['{key}'].key = '{meta.get('key')}', expected '{key}'"
            )

    return errors

def rule_meta_columns_consistent(data):
    errors = []

    meta_columns = data.get("meta", {}).get("columns", {})
    columns_by_category = data.get("columns", {})

    for category, cols in columns_by_category.items():
        for col in cols:
            if col not in meta_columns:
                errors.append(
                    f"Meta error: column '{col}' used in columns.{category} but missing in meta.columns"
                )

    for key, meta in meta_columns.items():
        if meta.get("key") != key:
            errors.append(
                f"Meta error: meta.columns['{key}'].key = '{meta.get('key')}', expected '{key}'"
            )

    return errors

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
        if category in ("columns", "schemaVersion", "meta"):
            continue
        errors = rules_validator.validate(data[category])
        for err in errors:
            had_errors = True
            print(f"Error validating {category}: {err}")
            print("---")

    # root-level meta rules
    meta_errors = []
    if "meta" in data:
        meta_errors.extend(rule_meta_categories_consistent(data))
        meta_errors.extend(rule_meta_columns_consistent(data))

    for err in meta_errors:
        had_errors = True
        print(err)
        print("---")

    return not had_errors

def check_validation(data, schema_validator, rules_validator) -> bool:
    # Run both phases unconditionally and aggregate, so schema failures no
    # longer hide rule errors from the same CI run.
    schema_ok = check_schema_validation(schema_validator, data)
    rules_ok = check_rules_validation(rules_validator, data)
    return schema_ok and rules_ok

def load_csv_folder(folder) -> dict:
    from csv_to_json import load_csv_to_dict_list, normalize

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
    rules.add_rule(rule_chain_is_lowercase)

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
    providers_data = load_csv_folder("references/offers")
    providers_schema = make_providers_schema(network_schema=schema)
    providers_validator = Draft202012Validator(providers_schema)
    if not check_validation(data=providers_data, schema_validator=providers_validator, rules_validator=rules):
        had_errors = True

    if had_errors:
        exit(1)

if __name__ == "__main__":
    main()
