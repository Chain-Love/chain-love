import csv
import io
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import tempfile
import textwrap
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/link-check-analysis.yaml"
SOURCE = WORKFLOW.read_text(encoding="utf-8")
VALIDATION = (ROOT / ".github/workflows/validate.yaml").read_text(encoding="utf-8")
# Execute the exact inline Python bodies, not a test-only implementation.
SCRIPTS = [compile(textwrap.dedent(body), str(WORKFLOW), "exec")
           for body in re.findall(r"          python3 - <<'PY'\n(.*?)          PY\n",
                                  SOURCE, re.DOTALL)]
REAL_RUN = subprocess.run
REAL_CHECK_OUTPUT = subprocess.check_output


class LinkAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.env = {key: os.environ[key] for key in
                    ("PATH", "SYSTEMROOT", "TEMP", "TMP") if key in os.environ}
        self.env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
                        GIT_TERMINAL_PROMPT="0", GIT_CONFIG_COUNT="0",
                        GIT_ALLOW_PROTOCOL="", PYTHONDONTWRITEBYTECODE="1",
                        RUNNER_TEMP=str(self.root / "runner"),
                        GITHUB_OUTPUT=str(self.root / "github-output"),
                        GITHUB_STEP_SUMMARY=str(self.root / "summary"),
                        PR_NUMBER="3008", RUN_ID="fixture-run", LABEL_ACTOR="fixture-reviewer")
        self.git("init", "-q")
        self.git("config", "user.name", "Workflow Fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        self.write("README.md", "Fixture\n")
        self.base = self.commit()
        self.calls = []

    def git(self, *args, input=None):
        return REAL_CHECK_OUTPUT(["git", *args], cwd=self.repo, env=self.env,
                                 input=input, timeout=30).decode("utf-8").strip()

    def write(self, path, text):
        target = self.repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    def table(self, path, fields, rows):
        output = io.StringIO(newline="")
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
        self.write(path, output.getvalue())

    def commit(self, staged=False):
        if not staged:
            self.git("add", "--all")
        self.git("-c", "commit.gpgsign=false", "-c", "core.hooksPath=" + os.devnull,
                 "commit", "-qm", "fixture")
        return self.git("rev-parse", "HEAD")

    def blob(self, path, data, mode="100644"):
        oid = self.git("hash-object", "-w", "--stdin", input=data)
        self.git("update-index", "--add", "--cacheinfo", f"{mode},{oid},{path}")

    def execute(self, script=0, head=None, override=None, **variables):
        env = dict(self.env, BASE_SHA=self.base,
                   HEAD_SHA=head or self.git("rev-parse", "HEAD"))
        env.update(variables)

        def run(args, **kwargs):
            self.calls.append(args)
            if args[0] != "git" or args[1] not in (
                    "cat-file", "merge-base", "diff", "ls-tree", "show") or kwargs.get("shell"):
                raise RuntimeError("Non-local subprocess blocked")
            kwargs["timeout"] = 30
            return REAL_RUN(args, **kwargs)

        def check_output(args, **kwargs):
            if override is not None:
                result = override(args)
                if result is not None:
                    return result
            return REAL_CHECK_OUTPUT(args, **kwargs)

        previous = Path.cwd()
        try:
            os.chdir(self.repo)
            with patch.dict(os.environ, env, clear=True), \
                    patch("subprocess.run", side_effect=run), \
                    patch("subprocess.check_output", side_effect=check_output), \
                    patch.object(socket, "getaddrinfo", side_effect=AssertionError("DNS blocked")), \
                    patch.object(socket, "socket", side_effect=AssertionError("Network blocked")):
                exec(SCRIPTS[script], {"__name__": "__main__"})
        finally:
            os.chdir(previous)

    def scope(self):
        return json.loads((self.repo / "link-scope.json").read_text(encoding="utf-8"))

    def links(self):
        return (self.root / "runner/chain-love-link-input/links.txt").read_text(
            encoding="utf-8").splitlines()

    def assert_failure(self, error, message, **kwargs):
        with self.assertRaisesRegex(error, message):
            self.execute(**kwargs)
        for path in (self.repo / "link-scope.json", self.repo / "link-analysis/report.md",
                     self.root / "runner/chain-love-link-input/links.txt",
                     self.root / "github-output"):
            self.assertFalse(path.exists(), str(path))

    def test_workflows_keep_read_only_unprivileged_pr_execution(self):
        self.assertEqual(len(SCRIPTS), 2)
        for source in (SOURCE, VALIDATION):
            self.assertNotIn("pull_request_target", source)
            self.assertNotIn("secrets.", source)
            self.assertEqual(source.count("permissions:"), 1)
            self.assertIn("permissions:\n  contents: read\n", source)
            self.assertEqual(source.count("uses: actions/checkout@v4"),
                             source.count("persist-credentials: false"))
        self.assertIn("ref: ${{ github.event.pull_request.base.sha }}", SOURCE)
        self.assertIn("types: [labeled]", SOURCE)
        self.assertIn("github.event.label.name == 'check-links'", SOURCE)
        self.assertIn("types: [opened, synchronize, reopened]", VALIDATION)
        self.assertIn("--network=none", VALIDATION)
        self.assertIn("python -B -m unittest discover -s tools/tests -p test_link_analysis.py -v", VALIDATION)
        self.assertIn("python-version: '3.12'", VALIDATION)
        self.assertIn("-p test_provider_lifecycle.py", VALIDATION)
        self.assertIn("if: steps.links.outputs.count != '0'", SOURCE)
        self.assertIn("exit 1", SOURCE)
        self.assertIn("if: always() && steps.links.outcome == 'success'", SOURCE)
        self.assertIn("if-no-files-found: error", SOURCE)

    def test_no_csv_is_not_proof_of_link_validity(self):
        self.write("meta/columns.json", '{"url":"https://ignored.invalid"}\n')
        head = self.commit()
        self.execute(head=head)
        scope = self.scope()
        self.assertEqual(scope["scope_result"], "N/A_NO_CSV")
        self.assertEqual(scope["changed_csv_files"], [])
        self.assertEqual(scope["head_sha"], head)
        self.assertEqual(scope["base_sha"], self.base)
        self.assertEqual(scope["merge_base"], self.base)
        self.assertEqual(scope["run_id"], "fixture-run")
        self.assertEqual(scope["label_actor"], "fixture-reviewer")
        self.assertEqual(scope["pr_number"], 3008)
        self.assertEqual(self.links(), [])
        self.assertEqual((self.root / "github-output").read_text(), "count=0\n")
        self.assertIn("not proof", (self.repo / "link-analysis/report.md").read_text())

    def test_unchanged_urls_metadata_edits_and_deletions_are_not_new_links(self):
        path = "references/offers/example.csv"
        self.table(path, ["name", "url"], [{"name": "Old", "url": "https://old.invalid/"}])
        self.table("references/offers/deleted.csv", ["url"], [{"url": "https://deleted.invalid/"}])
        self.base = self.commit()
        self.table(path, ["name", "url"], [{"name": "New", "url": "https://old.invalid/"}])
        self.git("rm", "references/offers/deleted.csv")
        self.commit()
        self.execute()
        self.assertEqual(self.scope()["scope_result"], "N/A_NO_NEW_URLS")
        self.assertEqual(self.scope()["changed_csv_files"], [path])
        self.assertEqual(self.links(), [])

    def test_csv_json_action_buttons_and_social_handles_extract_exact_urls(self):
        providers = "references/providers/providers.csv"
        fields = ["website", "x", "github", "discord", "telegram", "linkedin"]
        self.table(providers, fields, [{"website": "https://unchanged.invalid/", "x": "old"}])
        self.base = self.commit()
        self.table(providers, fields, [{"website": "https://unchanged.invalid/", "x": "@new",
                                       "github": "https://github.com/new", "discord": "invite",
                                       "telegram": "@channel", "linkedin": "company/project"}])
        buttons = ["[Docs](https://docs.invalid/a?x=1&y=2#part)",
                   "[Buy](http://buy.invalid/)", "[Again](http://buy.invalid/)"]
        self.table("references/offers/apis.csv", ["actionButtons", "details"],
                   [{"actionButtons": json.dumps(buttons),
                     "details": json.dumps({"url": "https://json.invalid/path"})}])
        self.table("listings/all-networks/example.csv", ["url"],
                   [{"url": "http://buy.invalid/"}, {"url": "https://listing.invalid/"}])
        self.commit()
        self.execute()
        expected = sorted(["https://x.com/new", "https://github.com/new", "https://discord.gg/invite",
                           "https://t.me/channel", "https://www.linkedin.com/company/project",
                           "https://docs.invalid/a?x=1&y=2#part", "http://buy.invalid/",
                           "https://json.invalid/path", "https://listing.invalid/"])
        self.assertEqual(self.links(), expected)
        self.assertEqual(self.scope()["new_or_changed_url_count"], len(expected))
        self.assertEqual(self.scope()["scope_result"], "REQUIRES_TRUSTED_NETWORK_CHECK")
        self.assertIn("must not be treated as verified",
                      (self.repo / "link-analysis/report.md").read_text())
        self.assertEqual((self.root / "github-output").read_text(), f"count={len(expected)}\n")
        self.assertFalse(any(call[1] == "fetch" for call in self.calls))

    def test_git_blobs_not_dirty_worktree_or_candidate_scripts_are_read(self):
        path = "references/offers/example.csv"
        self.table(path, ["url"], [{"url": "https://committed.invalid/"}])
        self.write("tools/candidate.py", "raise AssertionError('must not run')\n")
        self.commit()
        self.write(path, "url\nhttps://dirty.invalid/\n")
        self.execute()
        self.assertEqual(self.links(), ["https://committed.invalid/"])
        self.assertIn("dirty.invalid", (self.repo / path).read_text())

    def test_rename_is_treated_as_added_csv(self):
        self.table("references/offers/old.csv", ["url"], [{"url": "https://renamed.invalid/"}])
        self.base = self.commit()
        self.git("mv", "references/offers/old.csv", "references/offers/new.csv")
        self.commit()
        self.execute()
        self.assertEqual(self.scope()["changed_csv_files"], ["references/offers/new.csv"])
        self.assertEqual(self.links(), ["https://renamed.invalid/"])

    def test_paths_and_url_shell_payloads_are_data_not_commands(self):
        path = "listings/all-networks/space ; $(touch INJECTED).csv"
        url = "https://example.invalid/;touch${IFS}INJECTED?x=1&y=2"
        self.table(path, ["url", "description"],
                   [{"url": url, "description": "++ b/../../outside.csv\n+payload"}])
        self.commit()
        self.execute()
        self.assertEqual(self.scope()["changed_csv_files"], [path])
        self.assertEqual(self.links(), [url])
        self.assertFalse((self.repo / "INJECTED").exists())
        self.assertFalse((self.root / "outside.csv").exists())

    def test_parent_traversal_from_git_diff_is_rejected(self):
        def traversal(args):
            if args[1] == "diff":
                return b"references/../outside.csv\0"
        self.assert_failure(ValueError, "Invalid CSV path", override=traversal)

    def test_diff_uses_merge_base_when_target_branch_has_advanced(self):
        ancestor = self.base
        self.table("references/offers/head.csv", ["url"], [{"url": "https://head.invalid/"}])
        head = self.commit()
        self.git("checkout", "-q", "-b", "target", ancestor)
        self.table("references/offers/base-only.csv", ["url"], [{"url": "https://base.invalid/"}])
        self.base = self.commit()
        self.execute(head=head)
        self.assertEqual(self.scope()["merge_base"], ancestor)
        self.assertEqual(self.scope()["base_sha"], self.base)
        self.assertEqual(self.scope()["changed_csv_files"], ["references/offers/head.csv"])
        self.assertEqual(self.links(), ["https://head.invalid/"])

    def test_symlink_addition_and_regular_to_symlink_fail_closed(self):
        path = "references/providers/providers.csv"
        for existing in (False, True):
            with self.subTest(existing=existing):
                if existing:
                    self.table(path, ["name"], [{"name": "Provider"}])
                    self.base = self.commit()
                self.blob(path, b"../../outside.csv", mode="120000")
                self.commit(staged=True)
                self.assert_failure(ValueError, "regular Git blobs")

    def test_symlink_to_regular_still_rejects_symlink_base(self):
        path = "references/offers/example.csv"
        self.blob(path, b"../../outside.csv", mode="120000")
        self.base = self.commit(staged=True)
        self.blob(path, b"url\nhttps://regular.invalid/\n")
        self.commit(staged=True)
        self.assert_failure(ValueError, "regular Git blobs")

    def test_executable_regular_git_blob_is_supported(self):
        self.blob("references/offers/example.csv", b"url\nhttps://regular.invalid/\n", mode="100755")
        self.commit(staged=True)
        self.execute()
        self.assertEqual(self.links(), ["https://regular.invalid/"])

    def test_invalid_identifiers_fail_before_git_or_output(self):
        for name, values in {"BASE_SHA": ["-bad", "a" * 39, "A" * 40],
                             "HEAD_SHA": ["x;echo injected", "a" * 41],
                             "PR_NUMBER": ["0", "-1", "3;echo injected", "01"]}.items():
            for value in values:
                with self.subTest(name=name, value=value):
                    self.calls.clear()
                    self.assert_failure(ValueError, "Invalid", **{name: value})
                    self.assertEqual(self.calls, [])

    def test_credential_urls_are_rejected_before_output(self):
        for url in ("https://user:fixture-password@example.invalid/", "https://user@example.invalid/",
                    "https://%75ser:pass@example.invalid/", "https://@example.invalid/"):
            with self.subTest(url=url):
                self.table("references/offers/example.csv", ["url"], [{"url": url}])
                self.commit()
                self.assert_failure(ValueError, "Credential-bearing")

    def test_malformed_urls_are_rejected_before_output(self):
        for url in ("https://", "https:///path", "https://?query", "https://[broken/",
                    "https://example.invalid:bad/", "https://example.invalid:65536/",
                    "https://example.invalid/\x00injected", "https://bad\\host.invalid/"):
            with self.subTest(url=url):
                self.table("references/offers/example.csv", ["url"], [{"url": url}])
                self.commit()
                self.assert_failure(ValueError, "Malformed|Invalid|Port")

    def test_https_case_ipv6_and_valid_ports_are_preserved(self):
        urls = ["HTTPS://example.invalid:443/path", "http://[::1]:8080/path"]
        self.table("references/providers/providers.csv", ["github"], [{"github": urls[0]}])
        self.table("references/offers/example.csv", ["url"], [{"url": urls[1]}])
        self.commit()
        self.execute()
        self.assertEqual(self.links(), sorted(urls))

    def test_credentials_inside_json_action_buttons_fail_closed(self):
        buttons = ["[Docs](https://fixture-user:fixture-password@example.invalid/)"]
        self.table("references/offers/example.csv", ["actionButtons"],
                   [{"actionButtons": json.dumps(buttons)}])
        self.commit()
        self.assert_failure(ValueError, "Credential-bearing")

    def test_invalid_utf8_fails_closed(self):
        self.blob("references/offers/example.csv", b"url\n\xff\n")
        self.commit(staged=True)
        self.assert_failure(UnicodeDecodeError, "utf-8")

    def test_git_failure_does_not_write_not_applicable_success(self):
        def failure(args):
            if args[1] == "diff":
                raise subprocess.CalledProcessError(1, args)
        self.assert_failure(subprocess.CalledProcessError, "non-zero", override=failure)

    def test_missing_head_cannot_fetch_network_in_test(self):
        self.assert_failure(RuntimeError, "Non-local", head="f" * 40)

    def test_unrelated_histories_fail_closed(self):
        self.git("checkout", "--orphan", "unrelated")
        self.git("rm", "-rf", ".")
        self.write("unrelated.md", "unrelated\n")
        self.commit()
        self.assert_failure(subprocess.CalledProcessError, "non-zero")

    def test_csv_file_limit_accepts_boundary_and_rejects_overflow(self):
        # Only aggregate Git responses are synthetic; the limit checks are the real script.
        def inputs(count):
            def override(args):
                if args[1] == "diff":
                    return "".join(f"references/offers/{index}.csv\0" for index in range(count)).encode()
                if args[1] == "ls-tree":
                    return b"100644\n" if args[3] != self.base else b""
                if args[1] == "cat-file" and args[2] == "-s":
                    return b"4\n"
                if args[1] == "show":
                    return b"url\n"
            return override
        self.assert_failure(ValueError, "1000 CSV", override=inputs(1001))
        self.execute(override=inputs(1000))
        self.assertEqual(len(self.scope()["changed_csv_files"]), 1000)
        self.assertEqual(self.scope()["scope_result"], "N/A_NO_NEW_URLS")

    def test_per_blob_byte_limit_accepts_boundary_and_rejects_overflow(self):
        path = "references/offers/example.csv"
        self.blob(path, b"url\n" + b"\n" * (8 * 1024 * 1024 - 3))
        self.commit(staged=True)
        self.assert_failure(ValueError, "8 MiB")
        self.blob(path, b"url\n" + b"\n" * (8 * 1024 * 1024 - 4))
        self.commit(staged=True)
        self.execute()
        self.assertEqual(self.scope()["scope_result"], "N/A_NO_NEW_URLS")

    def test_total_byte_limit_counts_both_base_and_head(self):
        self.table("references/offers/example.csv", ["url"], [{"url": "https://old.invalid/"}])
        self.base = self.commit()
        self.table("references/offers/example.csv", ["url"], [{"url": "https://new.invalid/"}])
        self.commit()
        def inputs(count):
            def override(args):
                if args[1] == "diff":
                    return "".join(f"references/offers/{index}.csv\0" for index in range(count)).encode()
                if args[1] == "ls-tree":
                    return b"100644\n"
                if args[1] == "cat-file" and args[2] == "-s":
                    return b"8388608\n"
                if args[1] == "show":
                    return b"url\nhttps://unchanged.invalid/\n"
            return override
        self.assert_failure(ValueError, "64 MiB", override=inputs(5))
        self.execute(override=inputs(4))
        self.assertEqual(len(self.scope()["changed_csv_files"]), 4)

    def test_url_limit_accepts_boundary_and_rejects_overflow(self):
        path = "references/offers/example.csv"
        for count in (10001, 10000):
            self.table(path, ["url"], [{"url": f"https://example.invalid/{index}"} for index in range(count)])
            self.commit()
            if count > 10000:
                self.assert_failure(ValueError, "10000 URL")
            else:
                self.execute()
                self.assertEqual(len(self.links()), count)
                self.assertEqual(self.scope()["new_or_changed_url_count"], count)

    def test_output_write_failure_does_not_create_scope_success(self):
        self.write("blocked", "not a directory\n")
        self.assert_failure(OSError, ".", RUNNER_TEMP=str(self.repo / "blocked"))

    def test_failed_github_output_write_does_not_publish_count_or_report(self):
        self.write("blocked", "not a directory\n")
        with self.assertRaises(OSError):
            self.execute(GITHUB_OUTPUT=str(self.repo / "blocked/output"))
        self.assertFalse((self.root / "github-output").exists())
        self.assertFalse((self.repo / "link-analysis/report.md").exists())
        self.assertFalse((self.root / "summary").exists())

    def test_summary_records_exact_scope_without_reporting_to_pr(self):
        self.execute()
        self.execute(script=1)
        report = (self.repo / "link-analysis/report.md").read_text(encoding="utf-8")
        self.assertEqual((self.root / "summary").read_text(encoding="utf-8"), report)
        self.assertIn(f"head `{self.base}`", report)
        self.assertIn("Scope result: `N/A_NO_CSV`", report)
        self.assertIn("no URL requests or privileged PR reporting", report)

    def test_missing_report_fails_summary_without_fabricating_success(self):
        self.execute()
        (self.repo / "link-analysis/report.md").unlink()
        with self.assertRaisesRegex(RuntimeError, "did not produce a report"):
            self.execute(script=1)
        self.assertFalse((self.root / "summary").exists())


if __name__ == "__main__":
    unittest.main()
