"""Regression tests for the production release schema-validation gate.

Run after the JSON converter and the json-tools scripts are available at repo root.
No live network calls and no modifications to the production generated JSON.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/build-and-relese-json.yaml"


class ReleaseSchemaGateTests(unittest.TestCase):
    def test_release_validates_after_metadata_updates_before_archives(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        pipeline = text.split("      - name: Run full pipeline", 1)[1].split(
            "      - name: Prepare assets", 1
        )[0]
        steps = (
            "python csv_to_json.py",
            "python3 update_sdks_metadata_github.py",
            "python3 update_sdks_metadata_npm.py",
            "python3 update_sdks_metadata_gitlab.py",
            "python3 validate.py",
            "python3 create_ndjson.py",
            "python3 create_sqlite.py",
        )
        positions = [pipeline.index(step) for step in steps]
        self.assertEqual(positions, sorted(positions))

    def test_invalid_boolean_is_rejected_by_actual_release_validator(self):
        from csv_to_json import normalize

        result, errors = normalize({"apis": [{"starred": "MAYBE"}]})
        self.assertEqual(errors, [])
        self.assertEqual(result["apis"][0]["starred"], "MAYBE")

        with tempfile.TemporaryDirectory() as directory:
            isolated = Path(directory)
            json_dir = isolated / "json"
            json_dir.mkdir()
            shutil.copyfile(ROOT / "schema.json", isolated / "schema.json")
            (isolated / "references").mkdir()
            shutil.copytree(
                ROOT / "references/offers",
                isolated / "references/offers",
            )
            data = json.loads((ROOT / "json/ethereum.json").read_text(encoding="utf-8"))
            self.assertTrue(data["apis"])
            self.assertIsInstance(data["apis"][0]["starred"], bool)
            data["apis"][0]["starred"] = "MAYBE"
            (json_dir / "ethereum.json").write_text(
                json.dumps(data, ensure_ascii=False), encoding="utf-8"
            )
            completed = subprocess.run(
                [sys.executable, str(ROOT / "validate.py")],
                cwd=isolated,
                capture_output=True,
                text=True,
                timeout=90,
                check=False,
            )
            combined = completed.stdout + completed.stderr
            self.assertNotEqual(completed.returncode, 0, combined)
            self.assertIn("MAYBE", combined)
            self.assertIn("boolean", combined)


if __name__ == "__main__":
    unittest.main()
