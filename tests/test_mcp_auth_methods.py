import sys
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

from validate import rule_mcp_auth_methods


class McpAuthMethodsRuleTests(unittest.TestCase):
    def test_null_is_allowed_for_unreviewed_rows(self):
        self.assertEqual(rule_mcp_auth_methods([{"authMethods": None}]), [])

    def test_canonical_order_is_allowed(self):
        rows = [{"authMethods": ["OAuth", "Personal Access Token", "API Key"]}]
        self.assertEqual(rule_mcp_auth_methods(rows), [])

    def test_duplicates_are_rejected(self):
        errors = rule_mcp_auth_methods([{"authMethods": ["OAuth", "OAuth"]}])
        self.assertTrue(any("duplicates" in error for error in errors))

    def test_unknown_and_noncanonical_values_are_rejected(self):
        errors = rule_mcp_auth_methods(
            [{"authMethods": ["API Key", "OAuth", "Unsupported"]}]
        )
        self.assertTrue(any("unsupported" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
