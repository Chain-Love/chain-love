"""Regression tests for sorting complete CSV records without rewriting fields."""

import csv
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


HOOK_PATH = Path(__file__).resolve().parents[1] / "pre-commit.py"
SPEC = importlib.util.spec_from_file_location("pre_commit", HOOK_PATH)
HOOK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HOOK)


class CsvSortingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "records.csv"
        self.git("init", "-q")
        self.git("config", "core.autocrlf", "false")

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.root)

    def sort(self, delimiter=","):
        previous = Path.cwd()
        try:
            os.chdir(self.root)
            HOOK.sort_csv_by_slug(self.root, delimiter)
        finally:
            os.chdir(previous)

    def check_sort(self, original, expected, delimiter=","):
        self.path.write_bytes(original.encode("utf-8"))
        self.sort(delimiter)
        actual = self.path.read_bytes()
        self.assertEqual(actual, expected.encode("utf-8"))
        self.assertEqual(self.git("show", ":records.csv"), actual)
        # The bytes being staged must still describe the original CSV records.
        before = list(csv.reader(io.StringIO(original, newline=""), delimiter=delimiter))
        after = list(csv.reader(io.StringIO(actual.decode("utf-8"), newline=""), delimiter=delimiter))
        self.assertEqual(before[0], after[0])
        self.assertCountEqual(before[1:], after[1:])
        self.sort(delimiter)
        self.assertEqual(self.path.read_bytes(), actual)
        self.assertEqual(self.git("show", ":records.csv"), actual)

    def test_multiline_fields_remain_one_record(self):
        self.check_sort(
            'slug,description\nz,"first\nlast"\na,plain\n',
            'slug,description\na,plain\nz,"first\nlast"\n',
        )

    def test_quoted_delimiter_before_slug(self):
        self.check_sort(
            'description,slug\n"first, a",z\n"second, z",a\n',
            'description,slug\n"second, z",a\n"first, a",z\n',
        )

    def test_escaped_quotes_and_unicode_are_preserved(self):
        self.check_sort(
            'slug,description\n"z","say ""hello""\n世界"\n"a",plain\n',
            'slug,description\n"a",plain\n"z","say ""hello""\n世界"\n',
        )

    def test_crlf_records_and_embedded_newlines_are_preserved(self):
        self.check_sort(
            'slug,description\r\nz,"one\r\ntwo\nthree"\r\na,plain\r\n',
            'slug,description\r\na,plain\r\nz,"one\r\ntwo\nthree"\r\n',
        )

    def test_no_terminal_newline_when_last_record_moves_first(self):
        self.check_sort(
            'slug,description\nz,"line\nend"\na,plain',
            'slug,description\na,plain\nz,"line\nend"',
        )

    def test_header_and_record_newline_styles_are_preserved(self):
        self.check_sort(
            '"slug",description\r\nz,last\na,first\r\n',
            '"slug",description\r\na,first\r\nz,last\n',
        )

    def test_single_line_and_equal_keys_keep_original_quoting_and_order(self):
        self.check_sort(
            'slug,description\nz,tail\na,"first"\n"a",second\n',
            'slug,description\na,"first"\n"a",second\nz,tail\n',
        )

    def test_reordered_empty_records_do_not_coalesce_cr_and_lf(self):
        self.check_sort(
            'slug,description\n\rz,last\n\na,first\n',
            'slug,description\n\r\n\na,first\nz,last\n',
        )

    def test_empty_record_does_not_coalesce_with_cr_header_ending(self):
        self.check_sort(
            'slug,description\rz,last\n\na,first\n',
            'slug,description\r\n\na,first\nz,last\n',
        )

    def test_custom_delimiter(self):
        self.check_sort(
            'description;slug\n"first; a";z\n"second; z";a\n',
            'description;slug\n"second; z";a\n"first; a";z\n',
            delimiter=";",
        )

    def test_empty_header_only_and_no_slug_files_are_unchanged(self):
        for content in ("", "slug,description\r\n", "name,description\nz,last\na,first\n"):
            with self.subTest(content=content):
                self.path.write_bytes(content.encode("utf-8"))
                self.git("add", "records.csv")
                self.sort()
                self.assertEqual(self.path.read_bytes(), content.encode("utf-8"))
                self.assertEqual(self.git("show", ":records.csv"), content.encode("utf-8"))

    def test_unterminated_quote_does_not_write_or_stage(self):
        staged = b"slug,description\na,valid\n"
        malformed = b'slug,description\nz,"unterminated\na,plain\n'
        self.path.write_bytes(staged)
        self.git("add", "records.csv")
        self.path.write_bytes(malformed)
        with self.assertRaises(csv.Error):
            self.sort()
        self.assertEqual(self.path.read_bytes(), malformed)
        self.assertEqual(self.git("show", ":records.csv"), staged)


if __name__ == "__main__":
    unittest.main()
