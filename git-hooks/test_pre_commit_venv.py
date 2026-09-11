"""Offline integration coverage for the hook's virtual environment interpreter."""
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


class PreCommitVirtualenvTest(unittest.TestCase):
    def test_dependency_install_and_validators_use_created_virtualenv(self):
        spec = importlib.util.spec_from_file_location(
            "pre_commit", Path(__file__).with_name("pre-commit.py")
        )
        hook = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(hook)
        completed = []
        real_run = hook.run

        def overlay(url, dest, subpath):
            (dest / "requirements.txt").write_text("", encoding="utf-8")
            for script in hook.SCRIPTS:
                (dest / script).write_text(
                    "import sys\nassert sys.prefix != sys.base_prefix\n",
                    encoding="utf-8",
                )

        def run(cmd, **kwargs):
            real_run(cmd, **kwargs)
            completed.append(list(cmd))

        with tempfile.TemporaryDirectory(prefix="precommit-venv-test-") as root:
            with (
                patch.object(hook, "get_repo_root", return_value=Path(root)),
                patch.object(hook, "checkout_index_tree"),
                patch.object(hook, "download_and_extract", side_effect=overlay),
                patch.object(hook, "run", side_effect=run),
                patch.dict(os.environ, {
                    "PIP_NO_INDEX": "1",
                    "PIP_DISABLE_PIP_VERSION_CHECK": "1",
                }),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                hook.main()

        self.assertEqual(len(completed), 5)
        self.assertEqual(completed[1][1:4], ["-m", "pip", "install"])
        self.assertEqual(
            [Path(cmd[1]).name for cmd in completed[-3:]], hook.SCRIPTS
        )
        self.assertTrue(all(cmd[0] == completed[1][0] for cmd in completed[-3:]))


if __name__ == "__main__":
    unittest.main()
