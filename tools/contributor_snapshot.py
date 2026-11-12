"""Build and verify a Contributor release from the CSV blobs of one Git commit."""

import argparse
import csv
import gzip
import hashlib
import io
import json
import re
import subprocess
import tarfile
from pathlib import Path


SCHEMA_VERSION = 1
GENERATOR_VERSION = 1
PROVIDERS_PATH = "references/providers/providers.csv"
OFFER_PREFIX = "!offer:"
INDEX_NAME = "contributor-index.json"
ARCHIVE_NAME = "contributor-sources.tar.gz"
MANIFEST_NAME = "manifest.json"


def file_context(path):
    parts = path.removesuffix(".csv").split("/")
    match parts:
        case ["references", "providers", "providers"]:
            return "provider", None, None
        case ["references", "offers", category]:
            return "offer", category, None
        case ["listings", "all-networks", category]:
            return "all-networks", category, None
        case ["listings", "specific-networks", network, category]:
            return "specific-network", category, network
        case _:
            raise ValueError(f"Unexpected source CSV path: {path}")


def read_sources(source_sha):
    if not re.fullmatch(r"[0-9a-f]{40}", source_sha):
        raise ValueError("Expected a full, lowercase source commit SHA")

    commit = subprocess.check_output(
        ["git", "rev-parse", "--verify", f"{source_sha}^{{commit}}"], text=True
    ).strip()
    if commit != source_sha:
        raise ValueError(f"{source_sha} is not the source commit itself")

    tree = subprocess.check_output(
        ["git", "ls-tree", "-r", "-z", source_sha, "--", "references/", "listings/"]
    )
    files = {}
    for entry in tree.rstrip(b"\0").split(b"\0") if tree else []:
        metadata, name = entry.split(b"\t", 1)
        if not name.endswith(b".csv"):
            continue
        path = name.decode("utf-8")
        mode, kind, blob_sha = metadata.decode("ascii").split()
        if mode not in {"100644", "100755"} or kind != "blob":
            raise ValueError(f"{path}: expected a regular CSV file")
        file_context(path)
        files[path] = blob_sha

    if PROVIDERS_PATH not in files:
        raise ValueError(f"Missing {PROVIDERS_PATH} in {source_sha}")

    # Batch reads preserve the exact Git bytes without one process per CSV.
    batch = subprocess.run(
        ["git", "cat-file", "--batch"],
        input="".join(f"{sha}\n" for sha in files.values()).encode("ascii"),
        stdout=subprocess.PIPE,
        check=True,
    )
    stream = io.BytesIO(batch.stdout)
    sources = {}
    for path, blob_sha in files.items():
        header = stream.readline().decode("ascii").split()
        if len(header) != 3 or header[:2] != [blob_sha, "blob"]:
            raise ValueError(f"{path}: Git did not return blob {blob_sha}")
        size = int(header[2])
        data = stream.read(size)
        if len(data) != size or stream.read(1) != b"\n":
            raise ValueError(f"{path}: incomplete Git blob {blob_sha}")
        sources[path] = data
    return files, sources


def value(row, column):
    cell = row.get(column, "").strip()
    return cell if cell.lower() != "null" else ""


def read_rows(path, data, required):
    reader = csv.reader(io.StringIO(data.decode("utf-8-sig"), newline=""), strict=True)
    header = next(reader, [])
    if (
        any(not name.strip() for name in header)
        or len(set(header)) != len(header)
        or not required.issubset(header)
    ):
        raise ValueError(f"{path}: invalid CSV header, expected at least {sorted(required)}")

    slugs = set()
    line = reader.line_num + 1
    try:
        for cells in reader:
            if cells:
                if len(cells) != len(header):
                    raise ValueError(f"{path}:{line}: expected {len(header)} columns, got {len(cells)}")
                row = dict(zip(header, cells))
                slug = value(row, "slug")
                if not slug or slug in slugs:
                    raise ValueError(f"{path}:{line}: missing or duplicate slug {slug!r}")
                slugs.add(slug)
                yield line, slug, row
            line = reader.line_num + 1
    except csv.Error as error:
        raise ValueError(f"{path}:{line}: {error}") from error


def build_index(source_sha, files, sources):
    providers, offers, listings = [], [], []
    file_table = []
    file_ids = {}
    for path in sorted(files):
        kind, category, network = file_context(path)
        file_ids[path] = len(file_table)
        file_table.append({
            "path": path, "blobSha": files[path], "kind": kind,
            "category": category, "network": network,
        })

    provider_keys = {}
    offer_by_id = {}

    for line, slug, row in read_rows(PROVIDERS_PATH, sources[PROVIDERS_PATH], {"slug", "name"}):
        name = value(row, "name")
        if not name:
            raise ValueError(f"{PROVIDERS_PATH}:{line}: missing provider name")
        for key in dict.fromkeys((name, slug)):
            if key in provider_keys:
                raise ValueError(f"{PROVIDERS_PATH}:{line}: ambiguous provider {key!r}")
            provider_keys[key] = slug
        providers.append({"file": file_ids[PROVIDERS_PATH], "slug": slug, "line": line, "name": name})

    def resolve_provider(key, path, line):
        if key not in provider_keys:
            raise ValueError(f"{path}:{line}: unknown provider {key!r}")
        return provider_keys[key]

    for file, info in enumerate(file_table):
        if info["kind"] != "offer":
            continue
        path = info["path"]
        for line, slug, row in read_rows(path, sources[path], {"slug", "provider", "offer"}):
            offer = {
                "file": file,
                "slug": slug,
                "line": line,
                "providerSlug": resolve_provider(value(row, "provider"), path, line),
                "name": value(row, "offer"),
            }
            offers.append(offer)
            offer_by_id[path, slug] = offer

    for file, info in enumerate(file_table):
        if info["kind"] not in {"all-networks", "specific-network"}:
            continue
        path = info["path"]
        for line, slug, row in read_rows(path, sources[path], {"slug", "provider", "offer"}):
            offer_value = value(row, "offer")
            provider_key = value(row, "provider")
            offer_id = None
            if offer_value.startswith(OFFER_PREFIX):
                offer_path = f"references/offers/{info['category']}.csv"
                offer_slug = offer_value.removeprefix(OFFER_PREFIX)
                offer = offer_by_id.get((offer_path, offer_slug))
                if offer is None:
                    raise ValueError(f"{path}:{line}: unknown offer {offer_value!r} in {offer_path}")
                offer_id = {"file": offer["file"], "slug": offer_slug}
            else:
                offer = None

            provider_slug = (
                resolve_provider(provider_key, path, line)
                if provider_key or offer is None
                else offer["providerSlug"]
            )
            listings.append({
                "file": file,
                "slug": slug,
                "line": line,
                "providerSlug": provider_slug,
                "offerId": offer_id,
                "offerLabel": (offer_value or None) if offer is None else None,
                "chain": value(row, "chain") or None,
            })

    return {
        "schemaVersion": SCHEMA_VERSION,
        "sourceSha": source_sha,
        "generatorVersion": GENERATOR_VERSION,
        "files": file_table,
        "providers": providers,
        "offers": offers,
        "listings": listings,
    }


def json_bytes(data):
    return (json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def make_manifest(source_sha, output):
    assets = {}
    for name in (INDEX_NAME, ARCHIVE_NAME):
        path = output / name
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        assets[name] = {"sha256": digest, "size": path.stat().st_size}
    return {
        "schemaVersion": SCHEMA_VERSION,
        "sourceSha": source_sha,
        "generatorVersion": GENERATOR_VERSION,
        "assets": assets,
    }


def write_snapshot(source_sha, output, index, sources):
    output.mkdir(parents=True)
    (output / INDEX_NAME).write_bytes(json_bytes(index))
    with (output / ARCHIVE_NAME).open("wb") as archive_file:
        with gzip.GzipFile(filename="", mode="wb", fileobj=archive_file, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w|") as archive:
                for path, data in sorted(sources.items()):
                    member = tarfile.TarInfo(path)
                    member.size = len(data)
                    archive.addfile(member, io.BytesIO(data))
    (output / MANIFEST_NAME).write_bytes(json_bytes(make_manifest(source_sha, output)))


def verify_snapshot(source_sha, output, index, sources):
    if {path.name for path in output.iterdir()} != {INDEX_NAME, ARCHIVE_NAME, MANIFEST_NAME}:
        raise ValueError("Expected exactly the index, CSV archive, and manifest")
    if json.loads((output / MANIFEST_NAME).read_bytes()) != make_manifest(source_sha, output):
        raise ValueError("Manifest does not match the source SHA, version, or asset digests")
    if json.loads((output / INDEX_NAME).read_bytes()) != index:
        raise ValueError("Index does not match the source CSV records")

    remaining = sources.copy()
    with tarfile.open(output / ARCHIVE_NAME, mode="r|gz") as archive:
        for member in archive:
            data = remaining.pop(member.name, None)
            if data is None or not member.isfile() or member.size != len(data):
                raise ValueError(f"Unexpected archive member {member.name!r}")
            with archive.extractfile(member) as entry:
                if entry.read() != data:
                    raise ValueError(f"Archive bytes do not match Git for {member.name}")
    if remaining:
        raise ValueError(f"Missing archived CSV files: {', '.join(sorted(remaining))}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "verify"))
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        files, sources = read_sources(args.source_sha)
        index = build_index(args.source_sha, files, sources)
        if args.command == "build":
            write_snapshot(args.source_sha, args.output, index, sources)
        verify_snapshot(args.source_sha, args.output, index, sources)
    except (ValueError, OSError, csv.Error, tarfile.TarError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Contributor snapshot: {error}\n")
    print(
        f"{args.source_sha}: verified {len(files)} CSV files, "
        f"{len(index['providers'])} providers, {len(index['offers'])} offers, "
        f"{len(index['listings'])} listings"
    )


if __name__ == "__main__":
    main()
