import json
import unittest

from csv_to_json import normalize, resolve_offers
from validate import MAX_ACTION_BUTTONS, rule_action_buttons_max_count

DOCS = "[Docs](https://example.com/docs)"
WEBSITE = "[Website](https://example.com)"
BUY = "[Buy](https://example.com/pricing)"


def row(slug, action_buttons):
    return {"slug": slug, "actionButtons": action_buttons}


class TestActionButtonsMaxCount(unittest.TestCase):
    def test_limit_is_two(self):
        self.assertEqual(MAX_ACTION_BUTTONS, 2)

    def test_blank_and_short_lists_pass(self):
        data = [
            row("blank", None),
            {"slug": "missing-column"},
            row("empty", []),
            row("one", [DOCS]),
            row("two", [DOCS, WEBSITE]),
        ]
        self.assertEqual(rule_action_buttons_max_count(data), [])

    def test_three_buttons_fail(self):
        data = [row("ok", [DOCS]), row("too-many", [DOCS, WEBSITE, BUY])]
        errors = rule_action_buttons_max_count(data)
        self.assertEqual(
            errors,
            ["Item 1: slug 'too-many' has 3 actionButtons, maximum is 2"],
        )

    def test_repeated_labels_still_count(self):
        data = [row("dupes", [DOCS, DOCS.upper(), DOCS.lower()])]
        self.assertEqual(len(rule_action_buttons_max_count(data)), 1)

    def test_non_list_is_left_to_link_rule(self):
        # rule_action_buttons_is_list_of_links already reports non-list values
        data = [row("string", "[Docs](a), [Website](b), [Buy](c)")]
        self.assertEqual(rule_action_buttons_max_count(data), [])

    def test_csv_cell_is_parsed_as_json_list(self):
        raw = {"apis": [
            {"slug": "csv-two", "actionButtons": '["%s","%s"]' % (DOCS, WEBSITE)},
            {"slug": "csv-three", "actionButtons": '["%s","%s","%s"]' % (DOCS, WEBSITE, BUY)},
            {"slug": "csv-blank", "actionButtons": ""},
        ]}
        data, errors = normalize(raw)
        self.assertEqual(errors, [])
        found = rule_action_buttons_max_count(data["apis"])
        self.assertEqual(len(found), 1)
        self.assertIn("csv-three", found[0])


class TestActionButtonsMaxCountWithOverrides(unittest.TestCase):
    def hydrate(self, offer_buttons, listing_buttons):
        # Same order as csv_to_json.py: resolve_offers on raw CSV cells, then normalize
        offers = {"apis": [
            {"slug": "canon", "offer": "Canon", "actionButtons": json.dumps(offer_buttons)},
        ]}
        listings = {"apis": [
            {"slug": "canon-eth", "offer": "!offer:canon",
             "actionButtons": json.dumps(listing_buttons) if listing_buttons is not None else ""},
        ]}
        data, errors = normalize(resolve_offers(listings, offers, "ethereum"))
        self.assertEqual(errors, [])
        return data["apis"]

    def test_blank_override_inherits_canonical(self):
        rows = self.hydrate([DOCS, WEBSITE, BUY], None)
        self.assertEqual(len(rule_action_buttons_max_count(rows)), 1)

    def test_override_replaces_whole_list(self):
        rows = self.hydrate([DOCS, WEBSITE, BUY], [DOCS])
        self.assertEqual(rule_action_buttons_max_count(rows), [])

    def test_empty_override_clears_canonical_buttons(self):
        rows = self.hydrate([DOCS, WEBSITE, BUY], [])
        self.assertEqual(rows[0]["actionButtons"], [])
        self.assertEqual(rule_action_buttons_max_count(rows), [])

    def test_override_with_too_many_fails(self):
        rows = self.hydrate([DOCS], [DOCS, WEBSITE, BUY])
        errors = rule_action_buttons_max_count(rows)
        self.assertEqual(len(errors), 1)
        self.assertIn("canon-eth", errors[0])


if __name__ == "__main__":
    unittest.main()
