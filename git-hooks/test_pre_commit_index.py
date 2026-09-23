"""Offline regressions for preservation of the intended commit.

Run: python3 -m unittest discover -s git-hooks -p 'test_pre_commit_index.py'
The downstream validator download is replaced with local stub scripts.
"""
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('hook', Path(__file__).with_name('pre-commit.py'))
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)


class IndexPreservationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='hook-index-test-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.git('init', '-q')
        self.write('data.csv', 'slug,value\nalpha,original\n')
        self.git('add', 'data.csv')
        self.git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                 '-c', 'core.hooksPath=/dev/null', 'commit', '-qm', 'fixture')

    def git(self, *args):
        return subprocess.check_output(['git', *args], cwd=self.root, text=True)

    def write(self, name, value):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value)

    def snapshot(self):
        return (
            self.git('ls-files', '--stage'),
            {str(p.relative_to(self.root)): p.read_bytes()
             for p in self.root.rglob('*') if p.is_file() and '.git' not in p.parts},
        )

    def invoke(self, validator_fails=False):
        def fake_download(url, destination, subpath):
            for script in hook.SCRIPTS:
                (destination / script).write_text('raise SystemExit(1)\n' if validator_fails else 'pass\n')

        old_cwd = Path.cwd()
        try:
            os.chdir(self.root)
            with patch.object(hook, 'download_and_extract', side_effect=fake_download), \
                 contextlib.redirect_stdout(io.StringIO()), \
                 contextlib.redirect_stderr(io.StringIO()):
                hook.main()
        finally:
            os.chdir(old_cwd)

    def test_partial_staging_and_untracked_csv_are_preserved(self):
        self.write('data.csv', 'slug,value\nalpha,intended\n')
        self.git('add', 'data.csv')
        self.write('data.csv', 'slug,value\nalpha,not-ready\n')
        self.write('local-notes.csv', 'slug,value\nnotes,private-fixture\n')
        before = self.snapshot()
        self.invoke()
        self.assertEqual(before, self.snapshot())
        self.assertIn('alpha,intended', self.git('show', ':data.csv'))
        self.assertEqual('', self.git('ls-files', 'local-notes.csv'))

    def test_unsorted_index_is_rejected_without_mutation(self):
        self.write('data.csv', 'slug,value\nzulu,z\nalpha,a\n')
        self.git('add', 'data.csv')
        before = self.snapshot()
        with self.assertRaises(SystemExit) as error:
            self.invoke()
        self.assertEqual(1, error.exception.code)
        self.assertEqual(before, self.snapshot())

    def test_unstaged_unsorted_csv_does_not_change_staged_validation(self):
        self.write('data.csv', 'slug,value\nzulu,z\nalpha,a\n')
        before = self.snapshot()
        self.invoke()
        self.assertEqual(before, self.snapshot())

    def test_staged_addition_with_spaces_and_deletion(self):
        self.git('rm', '-q', 'data.csv')
        self.write('folder with spaces/new data.csv', 'slug,value\nalpha,added\n')
        self.git('add', 'folder with spaces/new data.csv')
        before = self.snapshot()
        self.invoke()
        self.assertEqual(before, self.snapshot())

    def test_downstream_validation_failure_preserves_index_and_worktree(self):
        self.write('local.csv', 'slug,value\nalpha,untracked\n')
        before = self.snapshot()
        with self.assertRaises(subprocess.CalledProcessError):
            self.invoke(validator_fails=True)
        self.assertEqual(before, self.snapshot())


if __name__ == '__main__':
    unittest.main()
