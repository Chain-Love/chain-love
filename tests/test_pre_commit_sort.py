import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).parents[1] / "git-hooks" / "pre-commit.py"
SPEC = importlib.util.spec_from_file_location("pre_commit", MODULE_PATH)
pre_commit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pre_commit)


class SortCsvBySlugTests(unittest.TestCase):
    def sort_bytes(self, source: bytes) -> bytes:
        with tempfile.TemporaryDirectory() as directory:
            csv_file = Path(directory) / "records.csv"
            csv_file.write_bytes(source)
            with patch.object(pre_commit, "iter_csv", return_value=[csv_file]), \
                    patch.object(pre_commit.subprocess, "run"):
                pre_commit.sort_csv_by_slug(Path(directory))
            return csv_file.read_bytes()

    def test_preserves_multiline_quoted_record(self):
        source = (
            b"slug,notes\n"
            b"zulu,\"line one\ncontinuation\"\n"
            b"alpha,single\n"
        )
        self.assertEqual(
            self.sort_bytes(source),
            b"slug,notes\nalpha,single\nzulu,\"line one\ncontinuation\"\n",
        )

    def test_parses_quoted_comma_before_slug(self):
        source = b"notes,slug\n\"has,comma\",zulu\nplain,alpha\n"
        self.assertEqual(
            self.sort_bytes(source),
            b"notes,slug\nplain,alpha\n\"has,comma\",zulu\n",
        )

    def test_keeps_duplicate_slug_order_and_crlf(self):
        source = b"slug,value\r\nz,one\r\na,two\r\na,three\r\n"
        self.assertEqual(
            self.sort_bytes(source),
            b"slug,value\r\na,two\r\na,three\r\nz,one\r\n",
        )

    def test_keeps_missing_final_newline(self):
        source = b"slug,value\nz,one\na,two"
        self.assertEqual(
            self.sort_bytes(source), b"slug,value\na,two\nz,one\n"
        )


if __name__ == "__main__":
    unittest.main()
