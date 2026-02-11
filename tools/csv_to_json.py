import csv
import json
import os
import string
import unicodedata

PROVIDER_REF_PREFIX = "!provider:"

SDK_TBD_FIELDS = (
    "latestKnownVersion",
    "latestKnownReleaseDate",
    "maintainer",
    "license",
)

def col_letter(idx: int) -> str:
    """Convert 0-based index to Excel column letters."""
    result = ""
    while idx >= 0:
        result = chr(ord('A') + (idx % 26)) + result
        idx = idx // 26 - 1
    return result

def try_parse_json(value):
    if not isinstance(value, str):
        return value
    value = value.strip()
    if not ((value.startswith("[") and value.endswith("]")) or (value.startswith("{") and value.endswith("}"))):
        return value
    return json.loads(value)


def is_nullish(value: str) -> bool:
    return isinstance(value, str) and (value.strip().lower() == "null" or value.strip() == "")


def is_boolish(value: str) -> bool:
    return isinstance(value, str) and (value.strip().lower() == "true" or value.strip().lower() == "false")


def is_trueish(value: str) -> bool:
    return isinstance(value, str) and value.strip().lower() == "true"


def normalize(data_by_category: dict):
    result = {}
    errors = []
    for category, items in data_by_category.items():
        result[category] = []
        for item in items:
            new_item = {}
            for key, value in item.items():
                new_item[key] = value
                if is_nullish(value):
                    new_item[key] = None
                if is_boolish(value):
                    new_item[key] = is_trueish(value)
                try:
                    new_item[key] = try_parse_json(new_item[key])
                except Exception as e:
                    errors.append(
                        f"Failed to parse value '{value}' for key '{key}' in category '{category}' as JSON: {e}"
                    )
            result[category].append(new_item)
    return result, errors

def validate_header(file_path: str, header: list[str]):
    errors = []

    # Check for empty header names
    for i, h in enumerate(header):
        if h is None or h.strip() == "":
            errors.append(
                f"{file_path}: Header column {col_letter(i)} exists but is empty"
            )

    # Check for duplicates
    seen = {}
    for idx, name in enumerate(header):
        if name not in seen:
            seen[name] = [idx]
        else:
            seen[name].append(idx)

    for name, idxs in seen.items():
        if len(idxs) > 1:
            cols = ", ".join(col_letter(i) for i in idxs)
            errors.append(
                f'  - Duplicate: "{name}" appears in columns {cols}'
            )

    if errors:
        header_with_positions = ", ".join(
            f"{col_letter(i)}:{header[i]}" for i in range(len(header))
        )
        msg = (
            f"{file_path}: Header validation failed:\n" +
            "\n".join(errors) +
            f"\nFull header: {header_with_positions}"
        )
        raise ValueError(msg)

def validate_utf8_with_position(file_path: str):
    """
    Reads the file in binary mode and decodes line by line,
    so we can pinpoint the exact UTF-8 failure.
    """
    with open(file_path, "rb") as f:
        line_number = 1
        byte_offset = 0

        for raw_line in f:
            try:
                raw_line.decode("utf-8")
            except UnicodeDecodeError as e:
                bad_byte = raw_line[e.start]
                column_number = e.start + 1  # make it human-friendly (1-based)

                raise ValueError(
                    f"File {file_path} is not valid UTF-8:\n"
                    f"  Invalid byte 0x{bad_byte:02X} at global byte offset {byte_offset + e.start}\n"
                    f"  Line {line_number}, column {column_number}\n"
                    f"  Decoder error: {e}"
                ) from None

            byte_offset += len(raw_line)
            line_number += 1

# Allowed ASCII baseline
BASE_ALLOWED = set(string.printable)
EXTRA_ALLOWED = {
    "\u2013",  # EN DASH –
    "\u2014",  # EM DASH —
    "\u2011",  # NON-BREAKING HYPHEN -
    "\u00A0",  # NON-BREAKING SPACE (NBSP)
}

def is_currency_symbol(ch: str) -> bool:
    return unicodedata.category(ch) == "Sc"

def is_superscript(ch: str) -> bool:
    return unicodedata.category(ch) == "No"

def is_arrow(ch: str) -> bool:
    name = unicodedata.name(ch, "")
    return "ARROW" in name

def scan_for_unexpected_unicode(file_path: str):
    """
    Allowed:
      - ASCII printable
      - Currency symbols
      - Dashes and NBSP
      - Superscripts
      - Any Unicode arrow
    Everything else rejected.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            for col, ch in enumerate(line, start=1):

                if ch in BASE_ALLOWED:
                    continue

                if ch in EXTRA_ALLOWED:
                    continue

                if is_currency_symbol(ch):
                    continue

                if is_superscript(ch):
                    continue

                if is_arrow(ch):
                    continue

                # → Not allowed
                code = ord(ch)
                name = unicodedata.name(ch, "UNKNOWN")
                raise ValueError(
                    f"Unexpected unicode character in {file_path}:\n"
                    f"  '{ch}' (U+{code:04X}, {name})\n"
                    f"  Line {lineno}, column {col}"
                )

def load_csv_to_dict_list(file_path: str) -> list[dict] | None:
    if not os.path.exists(file_path):
        return None

    # Validate non-unicode characters
    validate_utf8_with_position(file_path)
    scan_for_unexpected_unicode(file_path)

    with open(file_path, "r", newline="") as file:
        reader = csv.reader(file)

        try:
            header = next(reader)
        except StopIteration:
            raise Exception(f"File {file_path} is empty")

        # Validate header (multi-error)
        validate_header(file_path, header)

        expected_cols = len(header)
        rows = []
        errors = []
        row_number = 2  # header is row 1

        for raw_row in reader:
            if len(raw_row) != expected_cols:
                errors.append(f"{file_path}: Row {row_number} has {len(raw_row)} columns, expected {expected_cols}")
                row_number += 1
                continue

            row_dict = dict(zip(header, raw_row))
            rows.append(row_dict)
            row_number += 1

        if errors:
            raise ValueError(
                f"CSV validation failed for {file_path}:\n" +
                "\n".join(errors)
            )

        return rows


def find_one_by_slug(dict_list: list[dict], slug: str) -> dict | None:
    for item in dict_list:
        if item["slug"] == slug:
            return item
    return None


def is_provider_ref(string: str) -> bool:
    return string.strip().startswith(PROVIDER_REF_PREFIX)


def get_ref_slug(string: str) -> str:
    return string.strip()[len(PROVIDER_REF_PREFIX) :]


def override(item: dict, providers: list[dict]):
    if not is_provider_ref(item["provider"]):
        # If the provider is not a reference, return the item unchanged
        return item

    provider_slug = get_ref_slug(item["provider"])
    provider = find_one_by_slug(providers, provider_slug)

    if provider is None:
        print(f"Failed to find provider with slug {provider_slug}")
        return item

    # Keys we never copy from the provider
    skipped_keys = {"slug"}
    # Keys we always copy, even if item has a value
    always_copy_keys = {"provider"}

    for key in item.keys():
        if key in skipped_keys:
            continue

        v = item.get(key)
        if key in always_copy_keys or (v is None or v.strip() == ""):
            if key not in provider:
                continue
            item[key] = provider[key]

    return item


def process_category(
    data_by_category: dict,
    network_data_file_path: str,
    provider_data_file_path: str,
    property_name: str,
) -> dict:
    network_data = load_csv_to_dict_list(network_data_file_path)
    if network_data is None:
        # No network data - skip adding this category
        print(f"Failed to load network data from {network_data_file_path}, skipping {property_name}")
        return data_by_category.copy()

    provider_data = load_csv_to_dict_list(provider_data_file_path)
    if provider_data is not None:
        # Run overrides
        processed_data = [override(item, provider_data) for item in network_data]
    else:
        # No overrides - use network data as-is
        print(f"Failed to load provider data from {provider_data_file_path}, using network data as-is")
        processed_data = network_data

    # Return a new dict containing all previous entries in `data_by_category`,
    # plus (or replacing) one entry with key = `property_name` and value = `processed_data`.
    return {**data_by_category, property_name: processed_data}


def get_column_order(
    data_by_category: dict[str, list[dict]],
) -> dict[str, list[str]]:
    categories = data_by_category.keys()
    column_order = dict.fromkeys(categories, [])

    # Save original CSV column order of each category
    for category in categories:
        items = data_by_category[category]
        if len(items) > 0:
            first_row = items[0]
            # dict keys order is preserved by default since python 3.7
            column_order[category] = list(first_row.keys())

    return column_order

def load_categories_from_folder(folder) -> dict:
    if not os.path.exists(folder):
        print(f"No '{folder}' directory found")
        return {}

    data = {}
    for category_file_name in os.listdir(folder):
        if not category_file_name.endswith(".csv"):
            continue
        category_name = category_file_name[:-4]
        data[category_name] = load_csv_to_dict_list(f"offchain/{category_file_name}")

    result, errors = normalize(data)
    if len(errors) > 0:
        print(f"Errors normalizing CSV data from 'offchain':")
        for err in errors:
            print(err)
        exit(1)
    return result

# read version from schema.json
def get_schema_version(schema_path: str = "schema.json", fallback: str = "1.0.0") -> str:
    """
    Returns properties.schemaVersion.const from schema.json.
    If schema.json is missing/invalid or const is absent, returns fallback.
    """
    try:
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
        v = schema.get("properties", {}).get("schemaVersion", {}).get("const")
        return v if isinstance(v, str) and v else fallback
    except Exception:
        return fallback

def ensure_sdks_tbd_fields(result: dict):
    sdks = result.get("sdks")
    if not isinstance(sdks, list):
        return

    for item in sdks:
        if not isinstance(item, dict):
            continue
        for k in SDK_TBD_FIELDS:
            if k not in item:
                item[k] = "TBD"
                continue
            v = item.get(k)
            if v is None or (isinstance(v, str) and v.strip() == ""):
                item[k] = "TBD"

def load_meta():
    categories = load_csv_to_dict_list("meta/categories.csv")
    columns = load_csv_to_dict_list("meta/columns.csv")

    if categories is None or columns is None:
        print("Meta files missing (meta/categories.csv, meta/columns.csv)")
        exit(1)

    categories, errors1 = normalize({"categories": categories})
    columns, errors2 = normalize({"columns": columns})

    if errors1 or errors2:
        for e in errors1 + errors2:
            print(e)
        exit(1)

    return {
        "categories": {c["key"]: c for c in categories["categories"]},
        "columns": {c["key"]: c for c in columns["columns"]},
    }


def main():
    if not os.path.exists("networks"):
        print("No 'networks' directory found")
        return
    
    offchain_categories = load_categories_from_folder("offchain")

    schema_version = get_schema_version("schema.json", fallback="1.0.0")
    meta = load_meta()

    for network_name in os.listdir("networks"):
        network_dir_full_path = os.path.join("networks", network_name)
        # We're not interested in anything that's not a directory
        if not os.path.isdir(network_dir_full_path):
            continue

        result = {}

        # Assumptions:
        # - Network-specific data is located at: os.path.join(network_dir_full_path, "<category>.csv")
        # - Provider-specific data is located at: "providers/<category>.csv"
        # - Category names match both the filename (without extension) and the dictionary key in the result
        for category_file_name in os.listdir(network_dir_full_path):
            category_file_full_path = os.path.join(network_dir_full_path, category_file_name)
            # Skip non-files
            if not os.path.isfile(category_file_full_path):
                continue
            category = category_file_name.split(".")[0]
            result = process_category(
                data_by_category=result,
                property_name=category,
                network_data_file_path=category_file_full_path,
                provider_data_file_path=f"providers/{category}.csv",
            )

        # Incorporate offchain data
        for offchain_category_name in offchain_categories.keys():
            if offchain_category_name in result:
                result[offchain_category_name].extend(offchain_categories[offchain_category_name])
            else:
                result[offchain_category_name] = offchain_categories[offchain_category_name]

        result, errors = normalize(result)
        if len(errors) > 0:
            print(f"Errors while normalizing {network_name} JSON:")
            for error in errors:
                print(error)
            exit(1)

        ensure_sdks_tbd_fields(result)

        result["columns"] = get_column_order(result)
        # set from schema.json const
        result["schemaVersion"] = schema_version
        result["meta"] = meta


        os.makedirs("json", exist_ok=True)
        with open(f"json/{network_name}.json", "w+") as f:
            json.dump(result, f, indent=4, ensure_ascii=False)


if __name__ == "__main__":
    main()
