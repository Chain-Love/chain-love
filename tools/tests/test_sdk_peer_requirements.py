"""Offline checks for DBIP #4151, using the production schema and converter."""
import copy
import csv
import io
import json
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
import csv_to_json as converter
import validate as validation
from jsonschema import Draft202012Validator

SCHEMA = json.loads((TOOLS / 'schema.json').read_text(encoding='utf-8'))
FIXTURES = json.loads((Path(__file__).parent / 'fixtures' / 'sdk-peer-requirements.json').read_text(encoding='utf-8'))


class PeerRequirementsTests(unittest.TestCase):
    def setUp(self):
        self.seed = copy.deepcopy(FIXTURES['abitype'])
        self.validator = Draft202012Validator(SCHEMA['$defs']['sdks']['properties']['peerRequirements'])

    def accepted(self, value):
        return self.validator.is_valid(value) and not converter.validate_sdk_peer_sources([{'slug':'fixture', 'peerRequirements':value}])

    def test_published_examples(self):
        Draft202012Validator.check_schema(SCHEMA)
        for value in FIXTURES.values():
            with self.subTest(package=value['package']):
                self.assertTrue(self.accepted(value))
        self.assertTrue(all(r['optional'] for r in FIXTURES['abitype']['requirements'].values()))
        self.assertTrue(all(not r['optional'] for r in FIXTURES['synapse-react']['requirements'].values()))

    def test_invalid_values(self):
        mutations = [
            lambda x: x.pop('package'),
            lambda x: x.update(extra='peer'),
            lambda x: x.update(requirements={}),
            lambda x: x['requirements']['zod'].pop('optional'),
            lambda x: x['requirements']['zod'].update(optional='true'),
            lambda x: x['requirements']['zod'].update(optional=1),
            lambda x: x['requirements']['zod'].update(constraint=' '),
            lambda x: x['requirements']['zod'].update(extra='peer'),
            lambda x: x['requirements'].update({'https://example.com':{'constraint':'*','optional':False}}),
            lambda x: x.update(source='https://registry.npmjs.org/abitype'),
            lambda x: x.update(source='https://registry.npmjs.org/abitype/1.2.3'),
            lambda x: x.update(source='https://registry.npmjs.org/viem/1.3.0'),
            lambda x: x.update(version='latest',source='https://registry.npmjs.org/abitype/latest'),
            lambda x: x.update(version=' '),
            lambda x: x.update(source=x['source']+'?latest=true'),
        ]
        for index, mutate in enumerate(mutations):
            value = copy.deepcopy(self.seed)
            mutate(value)
            with self.subTest(case=index):
                self.assertFalse(self.accepted(value))
        for value in ({}, [], 'true', True):
            self.assertFalse(self.accepted(value))
        self.assertTrue(self.accepted(None))

    def test_csv_normalization_and_duplicate_members(self):
        stream = io.StringIO(newline='')
        writer = csv.DictWriter(stream, fieldnames=['slug','peerRequirements'])
        writer.writeheader()
        writer.writerow({'slug':'abitype','peerRequirements':json.dumps(self.seed)})
        stream.seek(0)
        rows, errors = converter.normalize({'sdks':list(csv.DictReader(stream))})
        self.assertFalse(errors)
        self.assertEqual(rows['sdks'][0]['peerRequirements'],self.seed)
        for value in ('', 'null', 'NULL'):
            normalized, errors = converter.normalize({'sdks':[{'peerRequirements':value}]})
            self.assertFalse(errors)
            self.assertIsNone(normalized['sdks'][0]['peerRequirements'])
        for value in ('{"package":"a","package":"b"}', '{"requirements":{"zod":{"optional":true,"optional":false}}}'):
            _, errors = converter.normalize({'sdks':[{'peerRequirements':value}]})
            self.assertTrue(any('Duplicate peerRequirements member' in e for e in errors))
        _, errors = converter.normalize({'sdks':[{'peerRequirements':'{"broken"'}]})
        self.assertTrue(errors)

    def test_source_guard_is_used_by_normalization_and_json_validation(self):
        value = copy.deepcopy(self.seed)
        value['source']='https://registry.npmjs.org/viem/1.3.0'
        _, errors = converter.normalize({'sdks':[{'slug':'abitype','peerRequirements':json.dumps(value)}]})
        self.assertTrue(any('must match' in e for e in errors))
        # Exercise the real standalone-validator entry point, not just its helper.
        self.assertFalse(validation.check_rules_validation(validation.Validator(),{'sdks':[{'slug':'abitype','peerRequirements':value}]}))

    def test_inheritance_and_complete_object_override(self):
        offers={'sdks':[{'slug':'abitype','offer':'ABIType','peerRequirements':self.seed}]}
        for value in ('', 'null', None):
            rows, errors=converter.normalize({'sdks':[{'slug':'listing','offer':'!offer:abitype','peerRequirements':value}]})
            self.assertFalse(errors)
            resolved=converter.resolve_offers(rows,offers,network_name='filecoin')
            self.assertEqual(resolved['sdks'][0]['peerRequirements'],self.seed)
        replacement=FIXTURES['synapse-react']
        resolved=converter.resolve_offers({'sdks':[{'slug':'listing','offer':'!offer:abitype','peerRequirements':replacement}]},offers,network_name='filecoin')
        self.assertEqual(resolved['sdks'][0]['peerRequirements'],replacement)
        self.assertNotIn('zod', resolved['sdks'][0]['peerRequirements']['requirements'])
        self.assertFalse(self.accepted({}))  # Empty objects do not clear evidence.

    def test_legacy_row_schema_and_column_metadata(self):
        row={k:'' for k in SCHEMA['$defs']['sdks']['required']}
        row.update(trial=False,starred=False,tag=None,actionButtons=None,dependencies=None)
        validator=Draft202012Validator(SCHEMA['$defs']['sdks'])
        self.assertTrue(validator.is_valid(row))
        self.assertNotIn('peerRequirements',SCHEMA['$defs']['sdks']['required'])
        for value in (None,self.seed):
            self.assertTrue(validator.is_valid(dict(row,peerRequirements=value)))
        self.assertFalse(validator.is_valid(dict(row,peerRequirements={})))
        metadata=json.loads((TOOLS.parent/'meta/columns.json').read_text(encoding='utf-8'))
        self.assertEqual(metadata['peerRequirements']['key'],'peerRequirements')
        self.assertFalse(validation.rule_meta_columns_consistent({'columns':{'sdks':['peerRequirements']},'meta':{'columns':metadata}}))


if __name__ == '__main__':
    unittest.main()
