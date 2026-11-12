import gzip
import hashlib
import importlib.util
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().with_name("contributor_snapshot.py")
SPEC = importlib.util.spec_from_file_location("contributor_snapshot", SCRIPT)
snapshot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(snapshot)

SHA = "a" * 40
OFFERS = "references/offers/apis.csv"
OTHER_OFFERS = "references/offers/sdks.csv"
SPECIFIC = "listings/specific-networks/ethereum/apis.csv"
ALL_NETWORKS = "listings/all-networks/apis.csv"


class ContributorSnapshotTest(unittest.TestCase):
    def setUp(self):
        self.sources = {
            snapshot.PROVIDERS_PATH: b"slug,name\r\na,Provider A\r\nb,Provider B\r\n",
            OFFERS: b'slug,provider,offer\r\nshared,Provider A,"API, ""Pro"""\r\n',
            OTHER_OFFERS: b"slug,provider,offer\nshared,b,SDK\n",
            SPECIFIC: (
                b"slug,provider,offer,chain,description\r\n"
                b'\r\nsame,,!offer:shared,mainnet,"First\r\nsecond"\r\n'
                b"override,Provider B,!offer:shared,testnet,Text\r\n"
            ),
            ALL_NETWORKS: b"slug,provider,offer\nsame,a,!offer:shared\nsolo,b,Custom API\nblank,b,\n",
        }

    def build_index(self):
        files = {
            path: hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()
            for path, data in self.sources.items()
        }
        return snapshot.build_index(SHA, files, self.sources)

    def test_scope_and_provider_override_keep_canonical_dependency(self):
        index = self.build_index()
        files = index["files"]
        listings = index["listings"]
        inherited = next(row for row in listings if row["chain"] == "mainnet")
        override = next(row for row in listings if row["chain"] == "testnet")
        self.assertEqual(inherited["providerSlug"], "a")
        self.assertEqual(override["providerSlug"], "b")
        self.assertEqual(override["offerId"], inherited["offerId"])
        self.assertEqual(files[override["offerId"]["file"]]["path"], OFFERS)
        self.assertEqual(override["offerId"]["slug"], "shared")
        self.assertEqual(files[inherited["file"]]["network"], "ethereum")
        self.assertEqual((inherited["line"], override["line"]), (3, 5))
        self.assertEqual(index["offers"][0]["name"], 'API, "Pro"')

    def test_all_networks_and_standalone_rows_keep_source_identity(self):
        index = self.build_index()
        same_slug = [row for row in index["listings"] if row["slug"] == "same"]
        self.assertEqual(
            {index["files"][row["file"]]["path"] for row in same_slug},
            {ALL_NETWORKS, SPECIFIC},
        )
        standalone = [row for row in index["listings"] if row["offerId"] is None]
        self.assertEqual([(row["slug"], row["offerLabel"]) for row in standalone],
                         [("solo", "Custom API"), ("blank", None)])
        self.assertTrue(all(row["providerSlug"] == "b" for row in standalone))

    def test_invalid_sources_fail_without_an_index(self):
        for path, extra, error in (
            (OFFERS, b"shared,a,Duplicate\n", "duplicate slug"),
            (OFFERS, b"bad,missing,API\n", "unknown provider"),
            (ALL_NETWORKS, b"bad,a,!offer:missing\n", "unknown offer"),
            (ALL_NETWORKS, b"bad,a\n", "expected 3 columns"),
            (SPECIFIC, b'bad,a,,mainnet,"unfinished\n', "unexpected end of data"),
            (snapshot.PROVIDERS_PATH, b"c,a\n", "ambiguous provider"),
        ):
            with self.subTest(error=error):
                original = self.sources[path]
                self.sources[path] += extra
                try:
                    with self.assertRaisesRegex(ValueError, error):
                        self.build_index()
                finally:
                    self.sources[path] = original

    def test_snapshot_is_reproducible_and_archives_original_bytes(self):
        index = self.build_index()
        with tempfile.TemporaryDirectory() as directory:
            first, second = (Path(directory) / name for name in ("first", "second"))
            for output in (first, second):
                snapshot.write_snapshot(SHA, output, index, self.sources)
                snapshot.verify_snapshot(SHA, output, index, self.sources)
            for path in first.iterdir():
                self.assertEqual(path.read_bytes(), (second / path.name).read_bytes())
            with tarfile.open(first / snapshot.ARCHIVE_NAME) as archive:
                self.assertEqual(set(archive.getnames()), set(self.sources))
                self.assertEqual(archive.extractfile(SPECIFIC).read(), self.sources[SPECIFIC])

    def test_verification_checks_sha_and_csv_bytes_even_with_valid_digests(self):
        index = self.build_index()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "snapshot"
            snapshot.write_snapshot(SHA, output, index, self.sources)
            with self.assertRaisesRegex(ValueError, "Manifest"):
                snapshot.verify_snapshot("b" * 40, output, index, self.sources)

            # Re-sign an archive with changed content to exercise verification against Git.
            archive_path = output / snapshot.ARCHIVE_NAME
            with tarfile.open(fileobj=io.BytesIO(gzip.decompress(archive_path.read_bytes()))) as old:
                entries = {item.name: old.extractfile(item).read() for item in old}
            entries[SPECIFIC] = entries[SPECIFIC].replace(b"First", b"Other")
            with tarfile.open(archive_path, mode="w:gz") as archive:
                for name, data in entries.items():
                    member = tarfile.TarInfo(name)
                    member.size = len(data)
                    archive.addfile(member, io.BytesIO(data))
            manifest = snapshot.make_manifest(SHA, output)
            (output / snapshot.MANIFEST_NAME).write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Archive bytes do not match Git"):
                snapshot.verify_snapshot(SHA, output, index, self.sources)
