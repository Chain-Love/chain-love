import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "tools" / "validate.py"
SPEC = importlib.util.spec_from_file_location("validate", MODULE_PATH)
validate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validate)


class MarkdownValidationTests(unittest.TestCase):
    def test_detects_single_star_after_bold(self):
        self.assertTrue(validate.has_unclosed_markdown("**bold** and *unclosed"))

    def test_underscore_in_url_is_not_markdown(self):
        self.assertFalse(
            validate.has_unclosed_markdown(
                "https://subquery.network/doc/subquery_network/introduction"
            )
        )

    def test_detects_unclosed_underscore_emphasis(self):
        self.assertTrue(validate.has_unclosed_markdown("_unclosed emphasis"))


class MarkdownLinkValidationTests(unittest.TestCase):
    def test_accepts_balanced_parentheses_in_url(self):
        self.assertTrue(
            validate.is_markdown_link(
                "[Docs](https://en.wikipedia.org/wiki/Chain_(blockchain))"
            )
        )

    def test_rejects_trailing_text_and_unbalanced_url(self):
        self.assertFalse(validate.is_markdown_link("[Docs](https://example.test) trailing"))
        self.assertFalse(validate.is_markdown_link("[Docs](https://example.test/(broken)"))


class ProviderSchemaTests(unittest.TestCase):
    def test_provider_schema_targets_providers_table(self):
        schema = validate.make_providers_schema({"$defs": {"providerMeta": {}}})
        self.assertEqual(schema["required"], ["providers"])
        self.assertEqual(schema["properties"]["providers"]["type"], "array")
        self.assertEqual(
            schema["properties"]["providers"]["items"],
            {"$ref": "#/$defs/providerMeta"},
        )


if __name__ == "__main__":
    unittest.main()
