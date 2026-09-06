import contextlib
import csv
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("pre_commit", Path(__file__).with_name("pre-commit.py"))
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)


class SortCSVTests(unittest.TestCase):
    def sort_text(self, text):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "example.csv"
            path.write_bytes(text.encode())
            with patch.object(hook.subprocess, "run"), contextlib.redirect_stdout(io.StringIO()):
                hook.sort_csv_by_slug(Path(directory))
            return path.read_bytes().decode()

    def test_complete_records_preserve_quoted_values(self):
        for nl in ("\n", "\r\n"):
            with self.subTest(newline=repr(nl)):
                header = "slug,additionalNotes" + nl
                zulu = 'zulu,"line one' + nl + 'continuation, ""quoted"""' + nl
                alpha = '"alpha",single' + nl
                result = self.sort_text(header + zulu + alpha)
                self.assertEqual(result, header + alpha + zulu)
                self.assertEqual(list(csv.reader(io.StringIO(result, newline="")))[2][1],
                                 'line one' + nl + 'continuation, "quoted"')
                self.assertEqual(self.sort_text(result), result)

    def test_slug_after_a_quoted_comma(self):
        self.assertEqual(self.sort_text('notes,slug\n"a,b",zulu\n"z,y",alpha\n'),
                         'notes,slug\n"z,y",alpha\n"a,b",zulu\n')

    def test_single_line_rows_and_duplicate_keys(self):
        self.assertEqual(self.sort_text('slug,notes\nzulu,last\nalpha,first\nalpha,second'),
                         'slug,notes\nalpha,first\nalpha,second\nzulu,last\n')

    def test_empty_header_only_and_no_slug_files_are_unchanged(self):
        for text in ('', 'slug,notes\n', 'name,notes\nzulu,last\nalpha,first\n'):
            with self.subTest(text=text):
                self.assertEqual(self.sort_text(text), text)


if __name__ == "__main__":
    unittest.main()
