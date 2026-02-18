import csv
import json
import os
import string
import unicodedata
import warnings

OFFER_REF_PREFIX = "!offer:"

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
        result = chr(ord("A") + (idx % 26)) + result
        idx = idx // 26 - 1
    return result


def try_parse_json(value):
    if not isinstance(value, str):
        return value
    value = value.strip()
    if not (
        (value.startswith("[") and value.endswith("]"))
        or (value.startswith("{") and value.endswith("}"))
    ):
        return value
    return json.loads(value)


def is_nullish(value: str) -> bool:
    return isinstance(value, str) and (
        value.strip().lower() == "null" or value.strip() == ""
    )


def is_boolish(value: str) -> bool:
    return isinstance(value, str) and (
        value.strip().lower() == "true" or value.strip().lower() == "false"
    )


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
            errors.append(f'  - Duplicate: "{name}" appears in columns {cols}')

    if errors:
        header_with_positions = ", ".join(
            f"{col_letter(i)}:{header[i]}" for i in range(len(header))
        )
        msg = (
            f"{file_path}: Header validation failed:\n"
            + "\n".join(errors)
            + f"\nFull header: {header_with_positions}"
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
    "\u00a0",  # NON-BREAKING SPACE (NBSP)
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
    if file_path is None:
        return None
    if not os.path.exists(file_path):
        return None

    validate_utf8_with_position(file_path)
    scan_for_unexpected_unicode(file_path)

    with open(file_path, "r", newline="", encoding="utf-8") as file:
        reader = csv.reader(file)

        try:
            header = next(reader)
        except StopIteration:
            raise Exception(f"File {file_path} is empty")

        validate_header(file_path, header)

        expected_cols = len(header)
        rows = []
        errors = []
        row_number = 2  # header is row 1

        for raw_row in reader:
            if len(raw_row) != expected_cols:
                errors.append(
                    f"{file_path}: Row {row_number} has {len(raw_row)} columns, expected {expected_cols}"
                )
                row_number += 1
                continue

            row_dict = dict(zip(header, raw_row))
            rows.append(row_dict)
            row_number += 1

        if errors:
            raise ValueError(
                f"CSV validation failed for {file_path}:\n" + "\n".join(errors)
            )

        return rows


def is_offer_ref(s: str) -> bool:
    return isinstance(s, str) and s.strip().startswith(OFFER_REF_PREFIX)


def get_ref_slug(string: str, prefix: str) -> str:
    s = string.strip()
    if not s.startswith(prefix):
        raise ValueError(f"Expected reference starting with '{prefix}', got '{string}'")
    return s[len(prefix) :]


def load_categories_from_folder(folder: str) -> dict:
    """
    Loads all *.csv in a folder into {category_name: [rows...]} and normalizes them.

    NOTE: category_name == filename without extension.
    """
    if not os.path.exists(folder):
        print(f"No '{folder}' directory found")
        return {}

    data = {}
    for category_file_name in os.listdir(folder):
        if not category_file_name.endswith(".csv"):
            continue
        category_name = category_file_name[:-4]
        data[category_name] = (
            load_csv_to_dict_list(os.path.join(folder, category_file_name)) or []
        )

    result, errors = normalize(data)
    if errors:
        print(f"Errors normalizing CSV data from '{folder}':")
        for err in errors:
            print(err)
        exit(1)
    return result


def load_providers(file_path: str) -> list[dict]:
    providers = load_csv_to_dict_list(file_path)
    if providers is None:
        raise FileNotFoundError(f"Providers file not found: {file_path}")
    providers, errors = normalize({"providers": providers})
    if errors:
        raise ValueError("Errors normalizing providers.csv:\n" + "\n".join(errors))
    return providers["providers"]


def build_index_by_slug(items: list[dict], *, label: str) -> dict[str, dict]:
    idx = {}
    dupes = []
    for item in items:
        slug = item.get("slug")
        if not isinstance(slug, str) or not slug.strip():
            continue
        if slug in idx:
            dupes.append(slug)
        else:
            idx[slug] = item
    if dupes:
        raise ValueError(f"Duplicate slugs in {label}: {', '.join(sorted(set(dupes)))}")
    return idx


def get_column_order(data_by_category: dict[str, list[dict]]) -> dict[str, list[str]]:
    categories = data_by_category.keys()
    column_order = {category: [] for category in categories}

    for category in categories:
        items = data_by_category[category]
        if items:
            first_row = items[0]
            column_order[category] = list(first_row.keys())

    return column_order


def resolve_offers(
    data_by_category: dict[str, list[dict]],
    offers_by_category: dict[str, list[dict]],
) -> dict[str, list[dict]]:
    """
    Replaces listing rows that contain offer refs with merged offer data.

    Expected listing convention:
      row["offer"] == "!offer:<offer_slug>"

    Offers come from:
      references/offers/<category>.csv
    where <category> matches the current category being resolved.
    """
    # Build offer indexes per category: {category: {offer_slug: offer_row}}
    offer_idx_by_category: dict[str, dict[str, dict]] = {}
    for cat, offers in offers_by_category.items():
        offer_idx_by_category[cat] = build_index_by_slug(
            offers, label=f"offers/{cat}.csv"
        )

    resolved = {}
    for category, items in data_by_category.items():
        out_items = []
        for item in items:
            if not isinstance(item, dict):
                out_items.append(item)
                continue

            offer_field = item.get("offer")
            if isinstance(offer_field, str) and is_offer_ref(offer_field):
                offer_slug = get_ref_slug(offer_field, OFFER_REF_PREFIX)

                cat_offers = offer_idx_by_category.get(category)
                if cat_offers is None:
                    raise ValueError(
                        f"Category '{category}' uses !offer reference but references/offers/{category}.csv is missing"
                    )

                offer_row = cat_offers.get(offer_slug)
                if offer_row is None:
                    raise ValueError(
                        f"Offer '{offer_slug}' not found in references/offers/{category}.csv "
                        f"(referenced from listing '{item.get('slug')}')"
                    )

                # Merge: offer base -> listing overrides (listing wins for non-nullish values)
                merged = dict(offer_row)

                for k, v in item.items():
                    # keep listing's slug, chain overrides, etc.
                    # if listing has empty value, do not overwrite offer value
                    if v is None:
                        continue
                    if isinstance(v, str) and v.strip() == "":
                        continue
                    merged[k] = v

                out_items.append(merged)
            else:
                out_items.append(item)

        resolved[category] = out_items

    return resolved


def get_schema_version(
    schema_path: str = "schema.json", fallback: str = "1.0.0"
) -> str:
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


def drop_field(
    data_by_category: dict[str, list[dict]], field: str
) -> dict[str, list[dict]]:
    cleaned = {}

    for category, items in data_by_category.items():
        out_items = []
        for item in items:
            if isinstance(item, dict) and field in item:
                new_item = dict(item)
                new_item.pop(field, None)
                out_items.append(new_item)
            else:
                out_items.append(item)
        cleaned[category] = out_items

    return cleaned


def load_json_file(path: str) -> dict:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Meta file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_provider_index_by_name(providers: list[dict]) -> dict[str, dict]:
    idx = {}
    for p in providers:
        name = p.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        if name in idx:
            raise ValueError(f"Duplicate provider name in providers.csv: '{name}'")
        idx[name] = p
    return idx


def collect_used_provider_names(data_by_category: dict[str, list[dict]]) -> set[str]:
    names = set()

    for items in data_by_category.values():
        for item in items:
            if not isinstance(item, dict):
                continue
            p = item.get("provider")
            if isinstance(p, str) and p.strip():
                names.add(p.strip())

    return names


def build_provider_meta_from_names(
    provider_by_name: dict[str, dict],
    provider_categories: dict[str, set[str]],
) -> dict[str, dict]:
    meta = {}

    for name, categories in provider_categories.items():
        p = provider_by_name.get(name)

        categories_list = sorted(categories)

        # ─────────────────────────────
        # Case 1: provider is present in CSV
        # ─────────────────────────────
        if p:
            slug = p.get("slug") or name
            starred = p.get("starred")
            if not isinstance(starred, bool):
                starred = False

            meta[slug] = {
                "slug": slug,
                "name": name,
                "logoPath": p.get("logoPath"),
                "description": p.get("description"),
                "website": p.get("website"),
                "docs": p.get("docs"),
                "x": p.get("x"),
                "github": p.get("github"),
                "discord": p.get("discord"),
                "telegram": p.get("telegram"),
                "linkedin": p.get("linkedin"),
                "supportEmail": p.get("supportEmail"),
                "starred": starred,
                "tag": p.get("tag"),
                "categories": categories_list,
            }

        # ─────────────────────────────
        # Case 2: provider is not in CSV
        # ─────────────────────────────
        else:
            warnings.warn(
                f"Provider '{name}' is used in categories {categories_list} "
                f"but is missing from references/providers/providers.csv",
                RuntimeWarning,
            )

            slug = name.lower().replace(" ", "-")

            meta[slug] = {
                "slug": slug,
                "name": name,
                "logoPath": None,
                "description": None,
                "website": None,
                "docs": None,
                "x": None,
                "github": None,
                "discord": None,
                "telegram": None,
                "linkedin": None,
                "supportEmail": None,
                "starred": False,
                "tag": None,
                "categories": categories_list,
            }

    return meta


def collect_provider_categories(
    data_by_category: dict[str, list[dict]]
) -> dict[str, set[str]]:
    """
    Returns mapping: provider_name -> set(categories)
    """
    mapping: dict[str, set[str]] = {}

    for category, items in data_by_category.items():
        for item in items:
            if not isinstance(item, dict):
                continue

            provider = item.get("provider")
            if isinstance(provider, str) and provider.strip():
                mapping.setdefault(provider.strip(), set()).add(category)

    return mapping


def main():
    base_dir = "listings"
    all_networks_dir = os.path.join(base_dir, "all-networks")
    specific_networks_dir = os.path.join(base_dir, "specific-networks")

    if not os.path.exists(specific_networks_dir):
        print("No 'listings/specific-networks' directory found")
        return

    schema_version = get_schema_version("schema.json", fallback="1.0.0")

    # References
    providers = load_providers("references/providers/providers.csv")
    provider_by_name = build_provider_index_by_name(providers)
    category_meta = load_json_file("meta/categories.json")
    column_meta = load_json_file("meta/columns.json")
    offers_by_category = load_categories_from_folder("references/offers")

    # Global listings (apply to every network)
    global_listings = load_categories_from_folder(all_networks_dir)

    for network_name in os.listdir(specific_networks_dir):
        network_dir = os.path.join(specific_networks_dir, network_name)
        if not os.path.isdir(network_dir):
            continue

        result: dict[str, list[dict]] = {}

        # 1) Start from all-networks listings (copy lists)
        for category, entities in global_listings.items():
            result[category] = list(entities)

        # 2) Merge/replace with network-specific listings per category
        for category_file in os.listdir(network_dir):
            path = os.path.join(network_dir, category_file)
            if not os.path.isfile(path):
                continue
            if not category_file.endswith(".csv"):
                continue

            category = category_file[:-4]

            # If category already exists from all-networks, append; else create.
            rows = load_csv_to_dict_list(path) or []
            if category in result:
                result[category].extend(rows)
            else:
                result[category] = rows

        # 3) Resolve !offer:<slug> (category-scoped)
        result = resolve_offers(result, offers_by_category)

        # 4) Normalize values (null/bool/json fields)
        result, errors = normalize(result)
        if errors:
            print(f"Errors while normalizing {network_name} JSON:")
            for e in errors:
                print(e)
            exit(1)

        # DROP TECHNICAL FIELDS
        result = drop_field(result, "offer")

        ensure_sdks_tbd_fields(result)

        result["columns"] = get_column_order(result)
        result["schemaVersion"] = schema_version

        provider_categories = collect_provider_categories(result)

        provider_meta = build_provider_meta_from_names(
            provider_by_name,
            provider_categories,
        )

        result["meta"] = {
            "categories": category_meta,
            "columns": column_meta,
            "providers": provider_meta,
        }

        os.makedirs("json", exist_ok=True)
        with open(f"json/{network_name}.json", "w+", encoding="utf-8") as f:
            json.dump(result, f, indent=4, ensure_ascii=False)


if __name__ == "__main__":
    main()
