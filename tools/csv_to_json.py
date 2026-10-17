import csv
import json
import os
import re
import string
import unicodedata
import warnings
from datetime import date

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


# ── DBIP #4514: documented asset identities ──────────────────────────────────
DOCUMENTED_ASSET_IDENTITIES_COLUMN = "documentedAssetIdentities"
ASSET_REPRESENTATIONS = ("issuer_native", "bridged", "wrapped")
ASSET_USAGES = ("origin", "destination", "both")
EIP155_NAMESPACE = "eip155"
ERC20_ASSET_NAMESPACE = "erc20"
EVM_ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
CHECKED_AT_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def parse_caip19_asset_id(asset_id):
    """Split a CAIP-19 asset id into its four components, or None when malformed.

    The structural check is namespace-agnostic:
    <chain namespace>:<chain reference>/<asset namespace>:<asset reference>.
    Namespace-specific profiles (today eip155 ERC-20) are enforced by their own
    parsers, so this helper stays usable for other namespaces without pretending
    to know their reference formats.
    """
    if not isinstance(asset_id, str):
        return None
    parts = asset_id.split("/")
    if len(parts) != 2:
        return None
    chain_part, asset_part = parts
    if chain_part.count(":") != 1 or asset_part.count(":") != 1:
        return None
    namespace, reference = chain_part.split(":")
    asset_namespace, asset_reference = asset_part.split(":")
    if not namespace or not reference or not asset_namespace or not asset_reference:
        return None
    return namespace, reference, asset_namespace, asset_reference


def parse_eip155_erc20_asset_id(asset_id):
    """Parse 'eip155:<numericChainId>/erc20:0x<40hex>' into (chain_id, address).

    Returns None when the value is not an exact EVM ERC-20 CAIP-19 asset type,
    which includes bare tickers such as 'USDC'.
    """
    if not isinstance(asset_id, str):
        return None
    parts = asset_id.split("/")
    if len(parts) != 2:
        return None
    chain_part, asset_part = parts
    if not chain_part.startswith(EIP155_NAMESPACE + ":"):
        return None
    chain_id = chain_part[len(EIP155_NAMESPACE) + 1:]
    # isdigit() alone also accepts unicode digits such as a superscript; int() would then fail.
    if not (chain_id.isascii() and chain_id.isdigit()):
        return None
    if not asset_part.startswith(ERC20_ASSET_NAMESPACE + ":"):
        return None
    address = asset_part[len(ERC20_ASSET_NAMESPACE) + 1:]
    if not EVM_ADDRESS_RE.match(address):
        return None
    return chain_id, address


def normalized_asset_id_key(parsed):
    """Case-insensitive identity used when testing duplicates.

    Addresses and namespaces compare case-insensitively; numeric eip155 chain
    references compare by value so '08453' and '8453' are the same chain. The
    spelling a contributor supplied is what callers report -- only the
    comparison is normalized.
    """
    namespace, reference, asset_namespace, asset_reference = parsed
    if namespace == EIP155_NAMESPACE and reference.isascii() and reference.isdigit():
        reference_key = str(int(reference))
    else:
        reference_key = reference.lower()
    return (
        namespace.lower(),
        reference_key,
        asset_namespace.lower(),
        asset_reference.lower(),
    )


def validate_documented_asset_identities(
    rows: list,
    network_name: str,
    category: str,
    network_chain_ids: dict | None = None,
) -> list[str]:
    """DBIP #4514: validate the optional documentedAssetIdentities column.

    Each record is a bridge-provider-documented asset the offer handles on this
    exact network. The checks implement the issue's acceptance criteria:

      1. eip155 ERC-20 values must parse exactly as
         eip155:<numericChainId>/erc20:0x<40hex>; bare tickers such as 'USDC'
         are rejected. Duplicate detection compares addresses case-insensitively
         while the supplied spelling is what gets reported.
      2. When the caller supplies a network_chain_ids registry
         (network -> {chain environment: chainId}), the asset chainId must match
         the row's network and chain environment. The repository carries no such
         registry today, so csv_to_json passes None and this criterion stays
         dormant until one exists -- inventing chain IDs here would be worse
         than not checking them.
      3. Every record needs an https sourceUrl. Whether that URL is the bridge
         provider's official support page cannot be decided from the data, so
         the check is structural (scheme + presence) and the editorial burden
         stays with the contributor.
      4. Duplicate normalized assetIds in one listing are rejected;
         representation/usage enums are validated only when present.
      5. Missing, blank or NULL values are skipped, so existing listings without
         the column produce byte-identical JSON.

    Returns a list of human-readable error strings (empty when valid).
    """
    errors = []
    for row_index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        value = row.get(DOCUMENTED_ASSET_IDENTITIES_COLUMN)
        if value is None:
            continue  # criterion 5: absent, blank or NULL
        slug = row.get("slug") or f"row {row_index}"
        where = f"{network_name}/{category}/{slug}"
        if not isinstance(value, list):
            errors.append(
                f"{where}: documentedAssetIdentities must be a JSON array, "
                f"got {type(value).__name__}"
            )
            continue
        seen = {}
        for record_index, record in enumerate(value):
            label = f"{where}: documentedAssetIdentities[{record_index}]"
            if not isinstance(record, dict):
                errors.append(
                    f"{label} must be a JSON object, got {type(record).__name__}"
                )
                continue

            # assetId (required) -- criterion 1
            asset_id = record.get("assetId")
            if not isinstance(asset_id, str) or not asset_id.strip():
                errors.append(f"{label} is missing the required assetId")
                continue
            asset_id = asset_id.strip()
            parsed = parse_caip19_asset_id(asset_id)
            if parsed is None:
                errors.append(
                    f"{label}: assetId '{asset_id}' is not a CAIP-19 asset id "
                    f"(expected <namespace>:<reference>/<asset_namespace>:<asset_reference>); "
                    f"a ticker such as 'USDC' alone is not an asset identity"
                )
                continue
            namespace, reference = parsed[0], parsed[1]
            if namespace == EIP155_NAMESPACE:
                if not (reference.isascii() and reference.isdigit()):
                    errors.append(
                        f"{label}: eip155 chain reference '{reference}' must be numeric"
                    )
                    continue
                if parse_eip155_erc20_asset_id(asset_id) is None:
                    errors.append(
                        f"{label}: '{asset_id}' is not an exact eip155 ERC-20 asset id "
                        f"(expected eip155:<numericChainId>/erc20:0x<40 hex>)"
                    )
                    continue
                # criterion 2, only when a network -> chainId registry is supplied
                if network_chain_ids is not None:
                    environment = (row.get("chain") or "").strip().lower()
                    expected = network_chain_ids.get(network_name, {}).get(environment)
                    if expected is not None and str(expected) != reference:
                        errors.append(
                            f"{label}: chainId {reference} does not match network "
                            f"'{network_name}' ({environment or 'mainnet'} expects {expected})"
                        )

            # representation / usage enums, validated only when present
            for field, allowed in (
                ("representation", ASSET_REPRESENTATIONS),
                ("usage", ASSET_USAGES),
            ):
                if field not in record or record[field] is None:
                    continue
                field_value = record[field]
                if field_value not in allowed:
                    errors.append(
                        f"{label}: {field} '{field_value}' is not one of {list(allowed)}"
                    )

            # sourceUrl (required, https) -- criterion 3
            source_url = record.get("sourceUrl")
            if not isinstance(source_url, str) or not source_url.strip():
                errors.append(f"{label} is missing the required sourceUrl")
            elif not source_url.strip().lower().startswith("https://"):
                errors.append(
                    f"{label}: sourceUrl '{source_url}' must be an https link to the "
                    f"bridge provider's official token/route support documentation"
                )

            # checkedAt, optional YYYY-MM-DD date
            if record.get("checkedAt") is not None:
                checked_at = record["checkedAt"]
                if not isinstance(checked_at, str) or not CHECKED_AT_RE.match(checked_at):
                    errors.append(
                        f"{label}: checkedAt '{checked_at}' must be a YYYY-MM-DD date"
                    )
                else:
                    try:
                        date.fromisoformat(checked_at)
                    except ValueError:
                        errors.append(
                            f"{label}: checkedAt '{checked_at}' is not a real calendar date"
                        )

            # criterion 4: duplicate normalized assetIds in one listing
            key = normalized_asset_id_key(parsed)
            if key in seen:
                errors.append(
                    f"{label}: assetId '{asset_id}' duplicates '{seen[key]}' in the same "
                    f"listing (compared case-insensitively)"
                )
            else:
                seen[key] = asset_id
    return errors


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


def validate_no_offer_reference_conflicts(
    category: str,
    network_name: str,
    network_entities: list[dict],
    all_network_entities: list[dict],
) -> None:
    network_entity_by_offer_and_chain = {}
    for entity in network_entities:
        offer_reference = entity.get("offer")
        if not is_offer_ref(offer_reference):
            continue

        chain = entity.get("chain")
        if isinstance(chain, str):
            chain = chain.strip().lower()
        key = (get_ref_slug(offer_reference, OFFER_REF_PREFIX), chain)
        network_entity_by_offer_and_chain[key] = entity

    conflicts = []
    for entity in all_network_entities:
        offer_reference = entity.get("offer")
        if not is_offer_ref(offer_reference):
            continue

        chain = entity.get("chain")
        if isinstance(chain, str):
            chain = chain.strip().lower()
        offer_slug = get_ref_slug(offer_reference, OFFER_REF_PREFIX)
        network_entity = network_entity_by_offer_and_chain.get((offer_slug, chain))
        if network_entity is None:
            continue

        conflicts.append(
            f"  - offer '{offer_slug}', chain {chain!r}: "
            f"network-specific slug '{network_entity.get('slug')}', "
            f"all-networks slug '{entity.get('slug')}'"
        )

    if conflicts:
        raise ValueError(
            f"Conflicting offer references for network '{network_name}', "
            f"category '{category}'. The same offer and chain cannot be listed in both "
            f"listings/specific-networks/{network_name}/{category}.csv and "
            f"listings/all-networks/{category}.csv:\n"
            + "\n".join(conflicts)
        )


def load_categories_from_folder(folder: str) -> dict:
    """
    Loads all *.csv in a folder into {category_name: [rows...]} and normalizes them.

    NOTE: category_name == filename without extension.
    """
    if not os.path.exists(folder):
        print(f"No '{folder}' directory found")
        return {}

    data = {}
    for category in list_categories(folder):
        data[category.name] = (
            load_csv_to_dict_list(file_path=category.path) or []
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

class Category:
    def __init__(self, name: str, path: str):
        self.name = name
        self.path = path

def list_categories(folder: str) -> list[Category]:
    categories = []

    for name in os.listdir(folder):
        path = os.path.join(folder, name)
        if not os.path.isfile(path):
            continue
        if not name.endswith(".csv"):
            continue

        categories.append(Category(name[:-4], path))

    return categories

def get_csv_headers(filename: str) -> list[str]:
    """
    Returns CSV headers as a list of strings
    in the exact order they appear in the file.

    Raises:
        ValueError: if the file is empty or has no header row.
    """
    with open(filename, mode="r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        try:
            headers = next(reader)
        except StopIteration:
            raise ValueError(f"CSV file '{filename}' is empty.")

        if not headers:
            raise ValueError(f"CSV file '{filename}' has no header row.")

        return headers


def get_column_order(base_categories: list[Category], extra_categories: list[Category]) -> dict[str, list[str]]:
    base_names = {c.name for c in base_categories}
    unique_extras = [
        c for c in extra_categories
        if c.name not in base_names
    ]

    category_columns: dict[str, list[str]] = {}
    
    for category in base_categories + unique_extras:
        headers = get_csv_headers(category.path)
        category_columns[category.name] = headers
    
    # Hardcode columns order for automatically generated agents category
    category_columns["agents"] = [
        "slug",
        "offer",
        "name",
        "rank",
        "agentId",
        "description",
        "registrationType",
        "averageRating",
        "image",
        "active",
        "supportedTrust",
        "creator",
        "creatorTx",
        "owner",
        "agentURI",
        "agentURIType",
        "agentWallet",
        "chain",
        "identityRegistry",
        "reputationRegistry",
        "totalFeedbackCount",
        "activeFeedbackCount",
        "registeredAt",
        "updatedAt",
        "starred",
    ]

    return category_columns


def resolve_offers(
    data_by_category: dict[str, list[dict]],
    offers_by_category: dict[str, list[dict]],
    network_name: str,
) -> dict[str, list[dict]]:
    """
    Replaces listing rows that contain offer refs with merged offer data.

    Behavior:
      - If row["offer"] == "!offer:<slug>"
            → merge offer row as base
            → listing overrides non-empty values
            → resulting row["offer"] = offer_row["offer"]
      - If no offer ref
            → ensure row["offer"] = None
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

            # ─────────────────────────────
            # Case 1: listing contains !offer:<slug>
            # ─────────────────────────────
            if isinstance(offer_field, str) and is_offer_ref(offer_field):
                offer_slug = get_ref_slug(offer_field, OFFER_REF_PREFIX)

                cat_offers = offer_idx_by_category.get(category)
                if cat_offers is None:
                    raise ValueError(
                        f"Category '{category}' uses !offer reference "
                        f"but references/offers/{category}.csv is missing"
                    )

                offer_row = cat_offers.get(offer_slug)
                if offer_row is None:
                    raise ValueError(
                        f"Offer '{offer_slug}' is missing in references/offers/{category}.csv.\n"
                        f"This offer is referenced from either:\n"
                        f"  - listings/all-networks/{category}.csv\n"
                        f"  - listings/specific-networks/{network_name}/{category}.csv\n\n"
                        f"Action required:\n"
                        f"  1. Add a row with slug '{offer_slug}' to references/offers/{category}.csv, or\n"
                        f"  2. Remove or correct the reference in the listings file.\n"
                    )

                # Base = offer row
                merged = dict(offer_row)

                # Listing overrides non-empty fields (except offer itself)
                for k, v in item.items():
                    if k == "offer":
                        continue  # never override final offer value

                    if v is None:
                        continue
                    if isinstance(v, str) and v.strip() == "":
                        continue

                    merged[k] = v

                # Final offer value comes from offers CSV (NOT slug)
                merged["offer"] = offer_row.get("offer")

                out_items.append(merged)

            # ─────────────────────────────
            # Case 2: no offer reference
            # ─────────────────────────────
            else:
                new_item = dict(item)
                new_item.setdefault("offer", None)
                out_items.append(new_item)

        # DBIP #4514: documented asset identities are evidence-gated, so a
        # malformed record fails the build instead of reaching the JSON. The
        # check runs on the merged rows (offer values included) with the
        # network and category context the error messages need.
        identity_errors = validate_documented_asset_identities(
            out_items,
            network_name=network_name,
            category=category,
        )
        if identity_errors:
            raise ValueError(
                f"Invalid documentedAssetIdentities for network '{network_name}', "
                f"category '{category}':\n" + "\n".join(identity_errors)
            )

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
    network: str,
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
            all_network_paths = "\n".join(
                f"  - listings/all-networks/{c}.csv" for c in categories_list
            )
            specific_network_paths = "\n".join(
                f"  - listings/specific-networks/{network}/{c}.csv" for c in categories_list
            )
            references_paths = "\n".join(
                f"  - references/offers/{c}.csv (most likely source)" for c in categories_list
            )
            raise ValueError(
                f"Provider '{name}' is missing in references/providers/providers.csv.\n"
                f"This provider is referenced in one of the following files:\n"
                f"{references_paths}\n"
                f"{all_network_paths}\n"
                f"{specific_network_paths}\n\n"
                f"Action required:\n"
                f"  1. Add a provider entry with name '{name}' to references/providers/providers.csv, or\n"
                f"  2. Remove or correct the provider name in the files listed above.\n"
            )

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
    global_listings_categories = list_categories(folder=all_networks_dir)

    for network_name in os.listdir(specific_networks_dir):
        network_dir = os.path.join(specific_networks_dir, network_name)
        if not os.path.isdir(network_dir):
            continue

        # 1) Start with network-specific listings
        result: dict[str, list[dict]] = load_categories_from_folder(network_dir)

        # 2) Merge/replace with all-networks listings
        chains = set()
        for category, entities in result.items():
            if not entities or "chain" not in entities[0]:
                continue
            for entity in entities:
                if not entity.get("chain"):
                    print(f"ERROR: Network-specific chain-aware offer has no populated 'chain' value. Offending offer: network '{network_name}', category '{category}', slug '{entity.get('slug')}'")
                    exit(1)
                chains.update([entity['chain'].lower()])

        chains = sorted(chains)

        for category, entities in global_listings.items():
            rows = list(entities)
            if len(entities) > 0 and "chain" in entities[0]:
                if len(chains) == 0:
                    print(
                        f"WARNING: Network '{network_name}' has no populated 'chain' values. "
                        f"'all-networks' offers in chain-aware category '{category}' cannot be applied. "
                        f"Add at least one entry with a non-empty 'chain' value to fix this."
                    )
                    continue

                chain_aware_entities = [
                    {
                        **entity,
                        "chain": chain,
                        "slug": f"{entity['slug']}-{chain}".lower(),
                    }
                    for chain in chains
                    for entity in entities
                ]
                rows = chain_aware_entities

            validate_no_offer_reference_conflicts(
                category,
                network_name,
                result.get(category, []),
                rows,
            )

            if category in result:
                result[category].extend(rows)
            else:
                result[category] = rows


        # 3) Resolve !offer:<slug> (category-scoped)
        result = resolve_offers(result, offers_by_category, network_name=network_name)

        # 4) Normalize values (null/bool/json fields)
        result, errors = normalize(result)
        if errors:
            print(f"Errors while normalizing {network_name} JSON:")
            for e in errors:
                print(e)
            exit(1)

        ensure_sdks_tbd_fields(result)

        result["columns"] = get_column_order(
            base_categories=list_categories(network_dir),
            extra_categories=global_listings_categories,
        )
        result["schemaVersion"] = schema_version

        provider_categories = collect_provider_categories(result)

        provider_meta = build_provider_meta_from_names(
            provider_by_name,
            provider_categories,
            network=network_name,
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
