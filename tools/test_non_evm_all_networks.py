import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

from csv_to_json import all_networks_row_applies, load_non_evm_networks

SCRIPT = Path(__file__).resolve().parent / "csv_to_json.py"
META_FILE = Path(__file__).resolve().parent.parent / "meta" / "non-evm-networks.json"

OFFERS = {
    "evm-rpc": {"slug": "evm-rpc", "offer": "EVM RPC", "technology": "EVM JSON-RPC"},
    "rest-api": {"slug": "rest-api", "offer": "REST API", "technology": "REST"},
}
NON_EVM = {"cardano"}


def applies(category, entity, network):
    return all_networks_row_applies(category, entity, network, OFFERS, NON_EVM)


class TestAllNetworksRowApplies(unittest.TestCase):
    def test_evm_api_row_is_dropped_on_non_evm_network(self):
        self.assertFalse(applies("apis", {"slug": "own", "technology": "EVM JSON-RPC"}, "cardano"))

    def test_technology_inherited_from_canonical_offer(self):
        self.assertFalse(applies("apis", {"slug": "a", "offer": "!offer:evm-rpc", "technology": None}, "cardano"))
        self.assertTrue(applies("apis", {"slug": "b", "offer": "!offer:rest-api", "technology": None}, "cardano"))
        self.assertFalse(applies("apis", {"slug": "c", "offer": "!offer:evm-rpc", "technology": "  "}, "cardano"))

    def test_evm_api_row_stays_on_evm_network(self):
        self.assertTrue(applies("apis", {"slug": "a", "offer": "!offer:evm-rpc", "technology": None}, "ethereum"))

    def test_non_evm_technology_stays(self):
        self.assertTrue(applies("apis", {"slug": "own", "technology": "REST"}, "cardano"))
        # A listing override replaces the canonical technology
        self.assertTrue(applies("apis", {"slug": "a", "offer": "!offer:evm-rpc", "technology": "REST"}, "cardano"))
        self.assertTrue(applies("apis", {"slug": "blank", "technology": None}, "cardano"))

    def test_other_categories_are_not_filtered(self):
        self.assertTrue(applies("sdks", {"slug": "a", "technology": "EVM JSON-RPC"}, "cardano"))


class TestNonEvmNetworksFile(unittest.TestCase):
    def test_missing_file_means_no_filter(self):
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp, redirect_stderr(stderr):
            networks = load_non_evm_networks(str(Path(tmp) / "missing.json"))
        self.assertEqual(networks, set())
        self.assertIn("WARNING", stderr.getvalue())

    def test_file_must_be_a_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "non-evm-networks.json"
            path.write_text('{"cardano": true}', encoding="utf-8")
            with self.assertRaises(ValueError):
                load_non_evm_networks(str(path))

    def test_shipped_list_is_sorted_and_unique(self):
        names = json.loads(META_FILE.read_text(encoding="utf-8"))
        self.assertIsInstance(names, list)
        self.assertEqual(names, sorted(set(names)))
        self.assertEqual(names, [name.strip().lower() for name in names])
        self.assertIn("algorand", names)
        self.assertNotIn("ethereum", names)


def write(root, path, text):
    path = Path(root) / path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class TestScript(unittest.TestCase):
    def build(self, non_evm_networks):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "references/providers/providers.csv", "slug,name\n")
            write(tmp, "references/offers/apis.csv",
                  "slug,offer,technology\nevm-rpc,EVM RPC,EVM JSON-RPC\nrest-api,REST API,REST\n")
            write(tmp, "listings/all-networks/apis.csv",
                  "slug,offer,chain,technology\n"
                  "evm-rpc,!offer:evm-rpc,,\n"
                  "own-evm,,,EVM JSON-RPC\n"
                  "rest-api,!offer:rest-api,,\n"
                  "rest-override,!offer:evm-rpc,,REST\n")
            write(tmp, "listings/all-networks/sdks.csv", "slug,technology\nevm-sdk,EVM JSON-RPC\n")
            write(tmp, "listings/specific-networks/cardano/apis.csv",
                  "slug,offer,chain,technology\ncardano-mainnet,,mainnet,Ogmios\ncardano-preprod,,preprod,Ogmios\n")
            write(tmp, "listings/specific-networks/ethereum/apis.csv",
                  "slug,offer,chain,technology\neth-mainnet,,mainnet,EVM JSON-RPC\n")
            write(tmp, "meta/categories.json", "{}")
            write(tmp, "meta/columns.json", "{}")
            if non_evm_networks is not None:
                write(tmp, "meta/non-evm-networks.json", json.dumps(non_evm_networks))
            result = subprocess.run([sys.executable, str(SCRIPT)], cwd=tmp, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            out = {}
            for network in ("cardano", "ethereum"):
                data = json.loads((Path(tmp) / "json" / f"{network}.json").read_text(encoding="utf-8"))
                out[network] = {c: sorted(row["slug"] for row in data[c]) for c in ("apis", "sdks")}
            return out, result.stderr

    def test_evm_rows_skip_listed_networks_only(self):
        out, stderr = self.build(["cardano", "not-a-folder"])
        self.assertEqual(out["cardano"]["apis"], [
            "cardano-mainnet", "cardano-preprod",
            "rest-api-mainnet", "rest-api-preprod",
            "rest-override-mainnet", "rest-override-preprod",
        ])
        self.assertEqual(out["ethereum"]["apis"], [
            "eth-mainnet", "evm-rpc-mainnet", "own-evm-mainnet", "rest-api-mainnet", "rest-override-mainnet",
        ])
        self.assertEqual(out["cardano"]["sdks"], ["evm-sdk"])
        self.assertEqual(out["ethereum"]["sdks"], ["evm-sdk"])
        self.assertIn("not-a-folder", stderr)

    def test_without_meta_file_nothing_is_filtered(self):
        out, stderr = self.build(None)
        self.assertEqual(len(out["cardano"]["apis"]), 2 + 4 * 2)
        self.assertIn("evm-rpc-preprod", out["cardano"]["apis"])
        self.assertIn("meta/non-evm-networks.json not found", stderr)

    def test_no_empty_category_when_every_row_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "references/providers/providers.csv", "slug,name\n")
            write(tmp, "references/offers/apis.csv", "slug,offer,technology\nevm-rpc,EVM RPC,EVM JSON-RPC\n")
            write(tmp, "listings/all-networks/apis.csv", "slug,offer,chain,technology\nevm-rpc,!offer:evm-rpc,,\n")
            # The network has chains (from another category) but no API rows of its own
            write(tmp, "listings/specific-networks/cardano/analytics.csv", "slug,chain\ncardano-analytics,mainnet\n")
            write(tmp, "meta/categories.json", "{}")
            write(tmp, "meta/columns.json", "{}")
            write(tmp, "meta/non-evm-networks.json", json.dumps(["cardano"]))
            result = subprocess.run([sys.executable, str(SCRIPT)], cwd=tmp, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            data = json.loads((Path(tmp) / "json" / "cardano.json").read_text(encoding="utf-8"))
            self.assertNotIn("apis", data)
            self.assertEqual([row["slug"] for row in data["analytics"]], ["cardano-analytics"])


if __name__ == "__main__":
    unittest.main()
