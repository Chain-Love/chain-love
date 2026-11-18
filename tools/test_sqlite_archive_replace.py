import os
from pathlib import Path
import sqlite3
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import create_sqlite as exporter


class SQLiteArchiveReplacementTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="sqlite archive ")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.db = self.root / "sample data.db"
        with sqlite3.connect(self.db) as conn:
            conn.execute("CREATE TABLE sample (value TEXT)")
            conn.execute("INSERT INTO sample VALUES ('old')")
        self.output = self.root / "output dir"
        self.output.mkdir()
        self.archive = self.output / (self.db.name + ".tar.gz")
        with tarfile.open(self.archive, "w:gz") as tar:
            tar.add(self.db, arcname=self.db.name)
        self.old = self.archive.read_bytes()
        self.other = self.output / "unrelated.txt"
        self.other.write_bytes(b"leave untouched")
        with sqlite3.connect(self.db) as conn:
            conn.execute("UPDATE sample SET value = 'new'")

    def assert_preserved(self, cleaned=True):
        self.assertTrue(self.archive.exists(), "previous archive was deleted")
        self.assertEqual(self.archive.read_bytes(), self.old)
        self.assertEqual(self.other.read_bytes(), b"leave untouched")
        if cleaned:
            self.assertEqual(set(self.output.iterdir()), {self.archive, self.other})

    def test_missing_tar_preserves_previous_archive(self):
        with patch.dict(os.environ, PATH=str(self.root / "no executables")):
            with self.assertRaises(FileNotFoundError):
                exporter.compress_db(self.db, self.output)
        self.assert_preserved()

    def test_real_tar_failure_after_writing_preserves_previous_archive(self):
        real_run = subprocess.run

        def fail_after_member(command, **kwargs):
            try:
                return real_run(command + ["missing-member"], **kwargs)
            finally:
                partial = Path(command[2])
                self.assertGreater(partial.stat().st_size, 0)

        with patch.object(exporter.subprocess, "run", fail_after_member):
            with self.assertRaises(subprocess.CalledProcessError) as error:
                exporter.compress_db(self.db, self.output)
        self.assertEqual(error.exception.returncode, 2)
        self.assert_preserved()

    def test_real_tar_missing_input_does_not_leave_first_archive(self):
        self.archive.unlink()
        self.db.unlink()
        with self.assertRaises(subprocess.CalledProcessError):
            exporter.compress_db(self.db, self.output)
        self.assertEqual(list(self.output.iterdir()), [self.other])

    def test_success_replaces_only_after_tar_and_preserves_normal_mode(self):
        real_run = subprocess.run

        def observe_before_install(command, **kwargs):
            result = real_run(command, **kwargs)
            self.assert_preserved(cleaned=False)
            return result

        old_umask = os.umask(0o022)
        self.addCleanup(os.umask, old_umask)
        self.archive.chmod(0o600)
        with patch.object(exporter.subprocess, "run", observe_before_install):
            exporter.compress_db(self.db, self.output)
        self.assertEqual(self.archive.stat().st_mode & 0o777, 0o644)
        with tarfile.open(self.archive) as tar:
            self.assertEqual(tar.getnames(), [self.db.name])
            self.assertEqual(tar.extractfile(self.db.name).read(), self.db.read_bytes())
        self.assertEqual(self.other.read_bytes(), b"leave untouched")
        self.assertEqual(set(self.output.iterdir()), {self.archive, self.other})


if __name__ == "__main__":
    unittest.main()
