import copy
import json
from pathlib import Path
import unittest
import subprocess
import sys
import tempfile

from jsonschema import Draft202012Validator

try:
    import schema_versions as versions
except ImportError:
    versions = None


class SchemaVersionsTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(versions, 'versioned DBIP schema support is missing')
        self.base = json.loads(Path(__file__).with_name('schema.json').read_text())

    def test_legacy_schema_is_unchanged(self):
        self.assertEqual(versions.schema_for_version(self.base, '2.0.0'), self.base)

    def test_all_five_schema_changes(self):
        new = versions.schema_for_version(self.base, '2.1.0')
        Draft202012Validator.check_schema(new)
        for category, old, current in [
            ('explorers', 'pricing', 'price'),
            ('bridges', 'economicalSecurity', 'economicSecurity'),
            ('oracles', 'economicalSecurityNote', 'economicSecurityNote'),
            ('wallets', 'audit', 'auditsPerformed'),
        ]:
            definition = new['$defs'][category]
            self.assertNotIn(old, definition['properties'])
            self.assertIn(current, definition['properties'])
            self.assertIn(current, definition['required'])
        self.assertIn('trial', new['$defs']['storages']['properties'])
        self.assertIn('supportedRoutes', new['$defs']['bridges']['properties'])
        self.assertEqual(new['properties']['schemaVersion']['const'], '2.1.0')
        self.assertEqual(self.base['properties']['schemaVersion']['const'], '2.0.0')

    def test_projection_is_category_scoped_and_non_mutating(self):
        data = {'explorers': [{'pricing': 'Free'}], 'wallets': [{'audit': ['A']}],
                'bridges': [{'economicalSecurity': True, 'economicalSecurityNote': 'stake'}],
                'storages': [{'price': 'Free', 'trial': None}], 'apis': [{'trial': True}]}
        original = copy.deepcopy(data)
        new = versions.project_data(data, '2.1.0')
        self.assertEqual(new['explorers'], [{'price': 'Free'}])
        self.assertEqual(new['wallets'], [{'auditsPerformed': ['A']}])
        self.assertEqual(new['bridges'][0]['economicSecurity'], True)
        legacy = versions.project_data(new, '2.0.0')
        expected = copy.deepcopy(original)
        del expected['storages'][0]['trial']
        self.assertEqual(legacy, expected)
        self.assertEqual(data, original)

    def test_alias_conflicts_are_rejected(self):
        for version in ('2.0.0', '2.1.0'):
            with self.assertRaisesRegex(ValueError, 'conflict'):
                versions.project_data({'explorers': [{'price': 'Free', 'pricing': '$1'}]}, version)

    def test_metadata_and_columns_follow_version(self):
        data = {'schemaVersion': '2.0.0', 'columns': {'explorers': ['slug', 'pricing'],
                'storages': ['slug', 'trial'], 'bridges': ['slug', 'supportedRoutes']},
                'meta': {'columns': {'pricing': {'key': 'pricing'}, 'price': {'key': 'price'},
                                    'audit': {'key': 'audit'}, 'auditsPerformed': {'key': 'auditsPerformed'}}}}
        new = versions.project_data(data, '2.1.0')
        self.assertEqual(new['columns']['explorers'], ['slug', 'price'])
        self.assertNotIn('pricing', new['meta']['columns'])
        self.assertIn('supportedRoutes', new['meta']['columns'])
        old = versions.project_data(new, '2.0.0', legacy_metadata=data['meta']['columns'])
        self.assertEqual(old['meta']['columns'], data['meta']['columns'])
        self.assertEqual(old['columns']['bridges'], ['slug'])
        self.assertEqual(old['columns']['storages'], ['slug'])

    def test_trial_unknown_is_not_false(self):
        schema = versions.schema_for_version(self.base, '2.1.0')['$defs']['storages']['properties']['trial']
        v = Draft202012Validator(schema)
        for value in (None, True, False):
            self.assertTrue(v.is_valid(value))
        for value in ('FALSE', '', 0, []):
            self.assertFalse(v.is_valid(value))

    def test_routes_structure_and_semantics(self):
        schema = versions.schema_for_version(self.base, '2.1.0')['$defs']['bridges']['properties']['supportedRoutes']
        v = Draft202012Validator(schema)
        route = {'sourceChain': 'ethereum', 'destinationChain': 'linea', 'assetSymbols': ['ETH']}
        self.assertTrue(v.is_valid([route]))
        for value in ([], {}, [route, route], [{**route, 'extra': True}], [{**route, 'assetSymbols': []}]):
            self.assertFalse(v.is_valid(value))
        row = {'supportedChains': ['ethereum', 'linea'], 'supportedRoutes': [route]}
        self.assertEqual(versions.route_errors([row], {'ethereum', 'linea'}), [])
        for bad in (
            {**route, 'destinationChain': 'ethereum'},
            {**route, 'destinationChain': 'unknown'},
            {**route, 'assetSymbols': ['USDC', 'ETH']},
            {**route, 'assetSymbols': [' ETH']},
        ):
            self.assertTrue(versions.route_errors([{**row, 'supportedRoutes': [bad]}], {'ethereum', 'linea'}))
        self.assertTrue(versions.route_errors([{**row, 'supportedChains': ['linea']}], {'ethereum', 'linea'}))

    def test_invalid_new_values_cannot_hide_in_legacy_projection(self):
        for data in ({'storages': [{'trial': 'wrong'}]}, {'bridges': [{'supportedRoutes': []}]}):
            with self.assertRaises(ValueError):
                versions.project_data(data, '2.0.0')

    def test_unknown_version_rejected(self):
        with self.assertRaises(ValueError):
            versions.project_data({}, '9.0.0')

    def test_aliases_are_normalized_before_offer_inheritance(self):
        import csv_to_json as converter
        listings = {'explorers': [{'slug': 'listing', 'offer': '!offer:base', 'pricing': '$5'}]}
        offers = {'explorers': [{'slug': 'base', 'offer': 'Plan', 'price': '$10'}]}
        result = converter.resolve_offers(listings, offers, network_name='ethereum')
        self.assertEqual(versions.project_data(result, '2.1.0')['explorers'][0]['price'], '$5')

    def test_null_inherits_and_explicit_false_overrides(self):
        import csv_to_json as converter
        offers = {'storages': [{'slug': 'base', 'offer': 'Trial', 'trial': True}]}
        listings = {'storages': [{'slug': 'a', 'offer': '!offer:base', 'trial': None},
                                 {'slug': 'b', 'offer': '!offer:base', 'trial': False}]}
        result = converter.resolve_offers(listings, offers, network_name='ethereum')
        self.assertEqual([row['trial'] for row in result['storages']], [True, False])

    def test_real_export_and_validation_cli_both_versions(self):
        import csv
        tools = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'references/offers').mkdir(parents=True)
            (root / 'references/providers').mkdir()
            (root / 'listings/all-networks').mkdir(parents=True)
            (root / 'listings/specific-networks/ethereum').mkdir(parents=True)
            (root / 'meta').mkdir()
            (root / 'schema.json').write_text(json.dumps(self.base))
            for name in ('columns', 'categories'):
                (root / f'meta/{name}.json').write_bytes((tools.parent / f'meta/{name}.json').read_bytes())
            (root / 'references/providers/providers.csv').write_text('slug,name\nprovider,Provider\n')
            fields = ['slug', 'provider', 'offer', 'toolType', 'price', 'tag', 'description',
                      'starred', 'actionButtons', 'planType', 'trial']
            row = ['base', 'Provider', 'Plan', 'Storage', 'Free', '[]', 'Test',
                   'FALSE', '[]', 'Free', 'TRUE']
            for path, record in [('references/offers/storages.csv', row),
                                 ('listings/specific-networks/ethereum/storages.csv',
                                  ['listing', '', '!offer:base'] + [''] * (len(fields)-3))]:
                with (root / path).open('w', newline='') as stream:
                    writer = csv.writer(stream)
                    writer.writerow(fields)
                    writer.writerow(record)
            for version in versions.VERSIONS:
                for script in ('csv_to_json.py', 'validate.py'):
                    run = subprocess.run([sys.executable, str(tools / script), '--schema-version', version],
                                         cwd=root, capture_output=True, text=True)
                    self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
                data = json.loads((root / 'json/ethereum.json').read_text())
                self.assertEqual(data['schemaVersion'], version)
                if version == '2.1.0':
                    self.assertTrue(data['storages'][0]['trial'])
                else:
                    self.assertNotIn('trial', data['storages'][0])
                    self.assertNotIn('trial', data['columns']['storages'])


if __name__ == '__main__':
    unittest.main()
