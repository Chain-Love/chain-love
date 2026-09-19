import tempfile
import unittest
from pathlib import Path

from validate_listing_headers import diff_header, main

CANON = ["slug", "provider", "offer", "actionButtons", "technology", "starred"]
POS = 4


class TestDiffHeader(unittest.TestCase):
    def test_clean_headers_pass(self):
        self.assertIsNone(diff_header(CANON, CANON, POS))
        self.assertIsNone(diff_header(CANON, CANON[:POS] + ["chain"] + CANON[POS:], POS))

    def test_missing_field(self):
        self.assertIn("missing ['technology']", diff_header(CANON, [c for c in CANON if c != "technology"], POS))

    def test_extra_field(self):
        self.assertIn("extra ['unwanted']", diff_header(CANON, CANON + ["unwanted"], POS))

    def test_order_only_mismatch(self):
        self.assertIn("order mismatch: column 0", diff_header(CANON, CANON[::-1], POS))


class TestMain(unittest.TestCase):
    def test_drift_non_blocking_then_strict(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "references" / "offers").mkdir(parents=True)
            (root / "references" / "offers" / "zeta.csv").write_text(",".join(CANON) + "\n")
            (root / "listings" / "all-networks").mkdir(parents=True)
            (root / "listings" / "all-networks" / "zeta.csv").write_text(",".join(CANON + ["x"]) + "\n")
            self.assertEqual(main(root, strict=False), 0)
            self.assertEqual(main(root, strict=True), 1)
