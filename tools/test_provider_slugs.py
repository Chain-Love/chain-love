"""
Unit tests for provider slug uniqueness validation.

Tests the build_index_by_slug() function used in csv_to_json.py
to enforce that no two providers share the same slug.
"""
import os
import sys
import tempfile
import csv
import pytest

sys.path.insert(0, os.path.dirname(__file__))
from csv_to_json import build_index_by_slug, load_providers


class TestBuildIndexBySlug:
    """Tests for the existing build_index_by_slug() function."""

    def test_unique_slugs_pass(self):
        items = [
            {"slug": "provider-a", "name": "Provider A"},
            {"slug": "provider-b", "name": "Provider B"},
            {"slug": "provider-c", "name": "Provider C"},
        ]
        idx = build_index_by_slug(items, label="test")
        assert len(idx) == 3
        assert "provider-a" in idx
        assert "provider-b" in idx
        assert "provider-c" in idx

    def test_empty_list_passes(self):
        idx = build_index_by_slug([], label="test")
        assert idx == {}

    def test_single_item_passes(self):
        items = [{"slug": "only-one", "name": "Only"}]
        idx = build_index_by_slug(items, label="test")
        assert len(idx) == 1

    def test_duplicate_slugs_rejected(self):
        items = [
            {"slug": "provider-a", "name": "Provider A"},
            {"slug": "provider-a", "name": "Provider A (duplicate)"},
        ]
        with pytest.raises(ValueError, match="Duplicate slugs"):
            build_index_by_slug(items, label="test")

    def test_duplicate_slugs_error_lists_duplicates(self):
        items = [
            {"slug": "dup-one", "name": "A"},
            {"slug": "unique", "name": "B"},
            {"slug": "dup-one", "name": "C"},
        ]
        with pytest.raises(ValueError, match="dup-one"):
            build_index_by_slug(items, label="test")

    def test_multiple_duplicates_rejected(self):
        items = [
            {"slug": "dup-x", "name": "A"},
            {"slug": "dup-y", "name": "B"},
            {"slug": "dup-x", "name": "C"},
            {"slug": "dup-y", "name": "D"},
        ]
        with pytest.raises(ValueError, match="Duplicate slugs"):
            build_index_by_slug(items, label="test")

    def test_empty_slugs_skipped(self):
        items = [
            {"slug": "", "name": "Empty slug"},
            {"slug": None, "name": "None slug"},
            {"slug": "", "name": "Another empty"},
            {"slug": "valid", "name": "Valid"},
        ]
        idx = build_index_by_slug(items, label="test")
        assert len(idx) == 1
        assert "valid" in idx

    def test_whitespace_only_slugs_skipped(self):
        items = [
            {"slug": "   ", "name": "Whitespace"},
            {"slug": "valid", "name": "Valid"},
        ]
        idx = build_index_by_slug(items, label="test")
        assert len(idx) == 1

    def test_label_in_error_message(self):
        items = [
            {"slug": "dup", "name": "A"},
            {"slug": "dup", "name": "B"},
        ]
        with pytest.raises(ValueError, match="providers/providers.csv"):
            build_index_by_slug(items, label="providers/providers.csv")


class TestProviderSlugUniqueness:
    """Integration tests using load_providers() and temporary CSV files."""

    def _make_providers_csv(self, rows):
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, newline="", encoding="utf-8"
        )
        header = [
            "slug", "name", "logoPath", "description", "website", "docs",
            "x", "github", "discord", "telegram", "linkedin",
            "supportEmail", "starred", "tag",
        ]
        writer = csv.DictWriter(tmp, fieldnames=header)
        writer.writeheader()
        for row in rows:
            full_row = {h: "" for h in header}
            full_row.update(row)
            writer.writerow(full_row)
        tmp.close()
        return tmp.name

    def test_unique_provider_slugs_accepted(self):
        csv_path = self._make_providers_csv([
            {"slug": "alpha", "name": "Alpha"},
            {"slug": "beta", "name": "Beta"},
        ])
        try:
            providers = load_providers(csv_path)
            idx = build_index_by_slug(providers, label="providers/providers.csv")
            assert len(idx) == 2
        finally:
            os.unlink(csv_path)

    def test_duplicate_provider_slugs_rejected(self):
        csv_path = self._make_providers_csv([
            {"slug": "same-slug", "name": "First"},
            {"slug": "same-slug", "name": "Second"},
        ])
        try:
            providers = load_providers(csv_path)
            with pytest.raises(ValueError, match="Duplicate slugs"):
                build_index_by_slug(providers, label="providers/providers.csv")
        finally:
            os.unlink(csv_path)

    def test_real_providers_csv_loads(self):
        """Verify the real providers.csv loads without duplicate slugs."""
        real_path = os.path.join(
            os.path.dirname(__file__), "..", "references", "providers", "providers.csv"
        )
        if not os.path.exists(real_path):
            pytest.skip("real providers.csv not found")
        providers = load_providers(real_path)
        idx = build_index_by_slug(providers, label="providers/providers.csv")
        assert len(idx) > 0


class TestMainIntegration:
    """Integration tests that run csv_to_json.py against real data."""

    def test_csv_to_json_runs_without_error(self):
        """csv_to_json.py main() should complete without error."""
        import subprocess
        result = subprocess.run(
            [sys.executable, "csv_to_json.py"],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(__file__),
        )
        assert result.returncode == 0, (
            f"csv_to_json.py failed with return code {result.returncode}\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
