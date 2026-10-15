"""Unit tests for provider aliases propagation and collision detection.

Run: python -m unittest discover -s tools/tests -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from csv_to_json import (
    build_provider_meta_from_names,
    check_provider_alias_collisions,
    parse_provider_aliases,
)


def provider_row(slug, name, aliases=None):
    return {
        "slug": slug,
        "name": name,
        "logoPath": None,
        "description": None,
        "website": None,
        "docs": None,
        "x": None,
        "github": None,
        "discord": None,
        "telegram": None,
        "linkedin": None,
        "supportEmail": None,
        "starred": False,
        "tag": None,
        "aliases": aliases,
    }


class ParseAliasesTest(unittest.TestCase):
    def test_json_list_cell(self):
        self.assertEqual(
            parse_provider_aliases('["Matic Network"]', "polygon"),
            ["Matic Network"],
        )

    def test_parsed_list_passthrough(self):
        self.assertEqual(
            parse_provider_aliases(["Fantom"], "sonic"), ["Fantom"]
        )

    def test_empty_cell(self):
        self.assertEqual(parse_provider_aliases(None, "x"), [])
        self.assertEqual(parse_provider_aliases("", "x"), [])
        self.assertEqual(parse_provider_aliases("   ", "x"), [])

    def test_bare_name(self):
        self.assertEqual(
            parse_provider_aliases("Matic Network", "polygon"),
            ["Matic Network"],
        )

    def test_invalid_json_rejected(self):
        with self.assertRaises(ValueError):
            parse_provider_aliases('["oops"', "polygon")

    def test_non_list_rejected(self):
        with self.assertRaises(ValueError):
            parse_provider_aliases('{"a": 1}', "polygon")

    def test_empty_entry_rejected(self):
        with self.assertRaises(ValueError):
            parse_provider_aliases('[""]', "polygon")

    def test_duplicate_entry_rejected(self):
        with self.assertRaises(ValueError):
            parse_provider_aliases('["A", "A"]', "polygon")


class PropagationTest(unittest.TestCase):
    def test_aliases_land_in_meta(self):
        providers = [
            provider_row("polygon", "Polygon", ["Matic Network"]),
            provider_row("sonic", "Sonic", ["Fantom"]),
        ]
        by_name = {p["name"]: p for p in providers}
        meta = build_provider_meta_from_names(
            by_name, {"Polygon": {"apis"}, "Sonic": {"apis"}}, "ethereum"
        )
        self.assertEqual(meta["polygon"]["aliases"], ["Matic Network"])
        self.assertEqual(meta["sonic"]["aliases"], ["Fantom"])

    def test_missing_aliases_default_to_empty(self):
        providers = [provider_row("foo", "Foo")]
        by_name = {p["name"]: p for p in providers}
        meta = build_provider_meta_from_names(
            by_name, {"Foo": {"apis"}}, "ethereum"
        )
        self.assertEqual(meta["foo"]["aliases"], [])


class CollisionTest(unittest.TestCase):
    def test_alias_matching_another_name_rejected(self):
        providers = [
            provider_row("matic", "Matic", None),
            provider_row("polygon", "Polygon", ["Matic"]),
        ]
        with self.assertRaises(ValueError):
            check_provider_alias_collisions(
                {p["name"]: p for p in providers}
            )

    def test_alias_matching_another_slug_rejected(self):
        providers = [
            provider_row("fantom", "Fantom", None),
            provider_row("sonic", "Sonic", ["FANTOM"]),
        ]
        with self.assertRaises(ValueError):
            check_provider_alias_collisions(
                {p["name"]: p for p in providers}
            )

    def test_same_alias_twice_rejected(self):
        providers = [
            provider_row("a", "A", ["Dup"]),
            provider_row("b", "B", ["dup"]),
        ]
        with self.assertRaises(ValueError):
            check_provider_alias_collisions(
                {p["name"]: p for p in providers}
            )

    def test_distinct_aliases_pass(self):
        providers = [
            provider_row("polygon", "Polygon", ["Matic Network"]),
            provider_row("sonic", "Sonic", ["Fantom"]),
        ]
        check_provider_alias_collisions(
            {p["name"]: p for p in providers}
        )

    def test_self_alias_allowed(self):
        providers = [provider_row("matic", "Matic", ["Matic"])]
        check_provider_alias_collisions(
            {p["name"]: p for p in providers}
        )


if __name__ == "__main__":
    unittest.main()
