"""Test complete embedded link-check Python stages, using local Git only."""
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import textwrap
import unittest

WORKFLOW = Path(__file__).resolve().parents[2] / ".github/workflows/link-check-analysis.yaml"
HEADER = "slug,github,linkedin\n"
ROW = "acme,acme,company/acme\n"
LINKS = {"https://github.com/acme", "https://www.linkedin.com/company/acme"}


class LinkCheckHeaders(unittest.TestCase):
    def check_links(self, before, after, expected):
        blocks = re.findall(r"          python3 - <<'PY'\n(.*?)          PY", WORKFLOW.read_text(), re.S)
        self.assertEqual(len(blocks), 2)
        with tempfile.TemporaryDirectory(dir=os.environ.get("LINK_CHECK_FIXTURE_ROOT")) as tmp:
            root = Path(tmp)
            repo = root / "repo"
            repo.mkdir()
            env = {
                "PATH": os.environ["PATH"], "GITHUB_BASE_REF": "main",
                "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
                "GIT_ALLOW_PROTOCOL": "file", "GIT_TERMINAL_PROMPT": "0",
            }

            def git(*args):
                subprocess.run(
                    ["git", "-c", "user.name=Fixture", "-c",
                     "user.email=fixture@example.invalid", *args],
                    cwd=repo, env=env, check=True, capture_output=True, text=True,
                )

            table = repo / "references/providers/providers.csv"
            table.parent.mkdir(parents=True)
            git("init", "-b", "main")
            if before is not None:
                table.write_text(before)
                git("add", ".")
            git("commit", "--allow-empty", "-m", "base")
            origin = root / "origin.git"
            git("clone", "--bare", ".", str(origin))
            git("remote", "add", "origin", str(origin))
            git("checkout", "-b", "change")
            table.write_text(after)
            git("add", ".")
            git("commit", "-m", "change")
            for index, block in enumerate(blocks):
                subprocess.run(
                    [sys.executable, "-c", textwrap.dedent(block)],
                    cwd=repo, env=env, check=True, capture_output=True, text=True,
                )
            content = table.read_text() if table.exists() else ""
            self.assertEqual(set(content.splitlines()), expected)

    def test_changed_header(self):
        self.check_links(
            'slug,name,github,linkedin\nacme,"Acme, Inc.",acme,company/acme\n',
            'slug,name,github,linkedin,privacyPolicyUrl\nacme,"Acme, Inc.",acme,company/acme,\n',
            LINKS,
        )

    def test_new_csv(self):
        self.check_links(None, HEADER + ROW, LINKS)

    def test_added_data_row(self):
        self.check_links(
            HEADER + "old,old,company/old\n", HEADER + "old,old,company/old\n" + ROW, LINKS,
        )

    def test_non_header_edit(self):
        untouched = "untouched,untouched,company/untouched\n"
        self.check_links(
            HEADER + untouched + "old,old,company/old\n",
            HEADER + untouched + ROW,
            LINKS,
        )

    def test_header_shaped_data_is_preserved(self):
        self.check_links(
            HEADER + ROW, HEADER + HEADER,
            {"https://github.com/github", "https://www.linkedin.com/linkedin"},
        )


if __name__ == "__main__":
    unittest.main()
