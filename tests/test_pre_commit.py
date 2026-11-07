"""Regression tests for git-hooks/pre-commit.py (run with python -m unittest discover -s tests)."""
import importlib.util
import io
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HOOK = Path(__file__).resolve().parents[1] / "git-hooks" / "pre-commit.py"
spec = importlib.util.spec_from_file_location("chain_love_pre_commit", HOOK)
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)


class TestUtf8CsvSort(unittest.TestCase):
    def test_non_ascii_rows_preserve_utf8_and_crlf(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            csv = root / "sample.csv"
            csv.write_bytes("slug,name\r\nzeta,Café\r\nalpha,東京\r\n".encode("utf-8"))
            with patch.object(hook.subprocess, "run") as git_add:
                hook.sort_csv_by_slug(root)
            self.assertEqual(csv.read_bytes(), "slug,name\r\nalpha,東京\r\nzeta,Café\r\n".encode("utf-8"))
            git_add.assert_called_once()

    def test_files_without_slug_are_not_modified(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            csv = root / "sample.csv"
            content = "name,value\nCafé,1\n"
            csv.write_bytes(content.encode("utf-8"))
            with patch.object(hook.subprocess, "run") as git_add:
                hook.sort_csv_by_slug(root)
            self.assertEqual(csv.read_bytes(), content.encode("utf-8"))
            git_add.assert_not_called()
