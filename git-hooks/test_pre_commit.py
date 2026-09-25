"""Regression coverage for the interpreter used by the local validation hook."""

import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location(
    "pre_commit_hook", Path(__file__).with_name("pre-commit.py")
)
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)


class VirtualEnvironmentInterpreterTest(unittest.TestCase):
    def test_venv_python_path_covers_windows_and_posix(self):
        venv_dir = Path("workspace") / ".venv"

        with patch.object(hook.os, "name", "nt"):
            self.assertEqual(
                hook.venv_python_path(venv_dir),
                venv_dir / "Scripts" / "python.exe",
            )

        with patch.object(hook.os, "name", "posix"):
            self.assertEqual(
                hook.venv_python_path(venv_dir),
                venv_dir / "bin" / "python",
            )

    def test_main_runs_pip_and_validators_with_created_interpreter(self):
        commands = []

        def overlay(_url, destination, _subpath):
            (destination / "requirements.txt").write_text("", encoding="utf-8")
            for script in hook.SCRIPTS:
                (destination / script).write_text("", encoding="utf-8")

        def run(command, *, cwd=None):
            commands.append(command)
            if command[1:3] == ["-m", "venv"]:
                # Create a real virtual environment without downloading packages.
                subprocess.run(command + ["--without-pip"], check=True)
            else:
                self.assertTrue(Path(command[0]).is_file(), command[0])
                result = subprocess.run(
                    [command[0], "-c", "import sys; print(sys.prefix)"],
                    check=True, capture_output=True, text=True,
                )
                self.assertEqual(Path(result.stdout.strip()), Path(command[0]).parent.parent)

        with tempfile.TemporaryDirectory() as root:
            with patch.object(hook, "ensure_tool_exists"), \
                 patch.object(hook, "get_repo_root", return_value=Path(root)), \
                 patch.object(hook, "sort_csv_by_slug"), \
                 patch.object(hook, "checkout_index_tree"), \
                 patch.object(hook, "download_and_extract", side_effect=overlay), \
                 patch.object(hook, "run", side_effect=run):
                hook.main()

        self.assertEqual(len(commands), 2 + len(hook.SCRIPTS))
        expected = (
            Path("Scripts/python.exe") if os.name == "nt" else Path("bin/python")
        )
        interpreter = Path(commands[1][0])
        self.assertEqual(Path(*interpreter.parts[-2:]), expected)
        self.assertTrue(all(command[0] == str(interpreter) for command in commands[1:]))


if __name__ == "__main__":
    unittest.main()
