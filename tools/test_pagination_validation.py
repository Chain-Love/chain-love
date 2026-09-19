"""
Regression tests for DBIP #3792 pagination metadata validation in csv_to_json.py.

These tests reproduce the gap flagged by the USS-Supervisor review of PR #3811:
pagination used to be validated only on the *post-resolution* per-network result,
so a malformed canonical offer in references/offers/*.csv that is never referenced
by any listing slipped through (the script still exited 0).

The fix validates pagination on the normalized *source* datasets (canonical offers
and listings, incl. overrides) BEFORE offer resolution. These tests lock that in.

Run with:  python3 tools/test_pagination_validation.py
Exits non-zero on any failure.
"""

import csv
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
CSV_TO_JSON = os.path.join(SCRIPT_DIR, "csv_to_json.py")
SCHEMA_SRC = os.path.join(SCRIPT_DIR, "schema.json")
META_COLUMNS_SRC = os.path.join(REPO_ROOT, "meta", "columns.json")
META_CATEGORIES_SRC = os.path.join(REPO_ROOT, "meta", "categories.json")

# Minimal column set shared by the offer + listing fixtures. `pagination` is the
# DBIP #3792 column under test; the rest are required so the pipeline runs.
COLUMNS = [
    "slug", "provider", "offer", "actionButtons", "planName", "planType",
    "historicalData", "apiType", "technology", "accessPrice", "queryPrice",
    "starred", "trial", "availableApis", "limitations", "securityImprovements",
    "monitoringAndAnalytics", "regions", "additionalFeatures", "address", "tag",
    "uptimeSla", "blocksBehindSla", "bandwidthSla", "supportSla", "pagination",
]

VALID_PAGINATION = (
    '[{"endpoint":"/v1/accounts","mode":"page",'
    '"positionParameter":"page","sourceUrl":"https://docs.example.com/pagination"}]'
)
# Valid JSON but semantically invalid: missing mode / positionParameter / sourceUrl.
BROKEN_PAGINATION = '[{"endpoint":"GET /broken"}]'


def _write_csv(path, header, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        for row in rows:
            w.writerow(row)


def _blank_row(slug, provider="Validation Cloud", offer="", pagination=""):
    return {
        "slug": slug,
        "provider": provider,
        "offer": offer,
        "actionButtons": "",
        "planName": "",
        "planType": "",
        "historicalData": "",
        "apiType": "",
        "technology": "",
        "accessPrice": "",
        "queryPrice": "",
        "starred": "FALSE",
        "trial": "",
        "availableApis": "",
        "limitations": "",
        "securityImprovements": "",
        "monitoringAndAnalytics": "",
        "regions": "",
        "additionalFeatures": "",
        "address": "",
        "tag": "",
        "uptimeSla": "",
        "blocksBehindSla": "",
        "bandwidthSla": "",
        "supportSla": "",
        "pagination": pagination,
    }


def build_fixture(root, offer_pagination="", listing_pagination="",
                 reference_offer=False):
    """Create a minimal but valid dataset under `root` and return it.

    The canonical offer `validation-cloud-free-full-archive` carries
    `offer_pagination`. The network listing row optionally references that offer
    (reference_offer=True) or stands alone; it carries `listing_pagination`.
    """
    # Tooling / schema / meta (copied from the repo, as CI does).
    shutil.copyfile(SCHEMA_SRC, os.path.join(root, "schema.json"))
    os.makedirs(os.path.join(root, "meta"), exist_ok=True)
    shutil.copyfile(META_COLUMNS_SRC, os.path.join(root, "meta", "columns.json"))
    shutil.copyfile(META_CATEGORIES_SRC, os.path.join(root, "meta", "categories.json"))

    # A single provider used by both the offer and the listing.
    _write_csv(
        os.path.join(root, "references", "providers", "providers.csv"),
        ["slug", "name", "logoPath", "description", "website", "docs", "x",
         "github", "discord", "telegram", "linkedin", "supportEmail",
         "starred", "tag"],
        [{
            "slug": "validation-cloud", "name": "Validation Cloud",
            "logoPath": "vc.png", "description": "desc", "website": "",
            "docs": "", "x": "", "github": "", "discord": "", "telegram": "",
            "linkedin": "", "supportEmail": "", "starred": "FALSE", "tag": "",
        }],
    )

    # Canonical offer (references/offers/apis.csv) with the pagination column.
    offer_row = _blank_row(
        "validation-cloud-free-full-archive", pagination=offer_pagination
    )
    _write_csv(
        os.path.join(root, "references", "offers", "apis.csv"),
        COLUMNS,
        [offer_row],
    )

    # All-networks listing (one valid standalone row).
    _write_csv(
        os.path.join(root, "listings", "all-networks", "apis.csv"),
        COLUMNS,
        [_blank_row("all-networks-api")],
    )

    # Per-network listing.
    if reference_offer:
        listing_offer = "!offer:validation-cloud-free-full-archive"
    else:
        listing_offer = ""
    listing_row = _blank_row("testnet-api", offer=listing_offer,
                             pagination=listing_pagination)
    _write_csv(
        os.path.join(root, "listings", "specific-networks", "testnet", "apis.csv"),
        COLUMNS,
        [listing_row],
    )


def run_csv_to_json(root):
    """Run csv_to_json.py with cwd=root. Returns (returncode, stdout, stderr)."""
    proc = subprocess.run(
        [sys.executable, CSV_TO_JSON],
        cwd=root,
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout, proc.stderr


class TestPaginationSourceValidation(unittest.TestCase):

    def _scenario(self, **kwargs):
        tmp = tempfile.mkdtemp(prefix="pagtest_")
        try:
            build_fixture(tmp, **kwargs)
            return run_csv_to_json(tmp)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_unreferenced_malformed_offer_is_caught(self):
        """The exact gap: an unreferenced canonical offer with broken pagination
        must now fail (previously exited 0 because it never entered a result)."""
        code, out, err = self._scenario(offer_pagination=BROKEN_PAGINATION)
        self.assertNotEqual(
            0, code,
            "Unreferenced malformed offer should fail validation, but script exited 0.\n"
            f"STDOUT:\n{out}\nSTDERR:\n{err}",
        )
        self.assertIn("Pagination metadata validation failed", err + out)

    def test_unreferenced_valid_offer_passes(self):
        code, out, err = self._scenario(offer_pagination=VALID_PAGINATION)
        self.assertEqual(
            0, code,
            f"Valid pagination should pass, but script failed.\n"
            f"STDOUT:\n{out}\nSTDERR:\n{err}",
        )

    def test_referenced_malformed_offer_is_caught(self):
        """A referenced malformed offer must also be caught at the source."""
        code, out, err = self._scenario(
            offer_pagination=BROKEN_PAGINATION, reference_offer=True
        )
        self.assertNotEqual(0, code)
        self.assertIn("Pagination metadata validation failed", err + out)

    def test_listing_override_malformed_is_caught(self):
        """Malformed pagination supplied directly by a listing row (no offer ref)
        must be caught before offer resolution."""
        code, out, err = self._scenario(listing_pagination=BROKEN_PAGINATION)
        self.assertNotEqual(0, code)
        self.assertIn("Pagination metadata validation failed", err + out)

    def test_blank_pagination_is_valid(self):
        """Constraint 1: a blank pagination cell means 'unverified', not invalid."""
        code, out, err = self._scenario()  # no pagination anywhere
        self.assertEqual(
            0, code,
            f"Blank pagination should be valid, but script failed.\n"
            f"STDOUT:\n{out}\nSTDERR:\n{err}",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
