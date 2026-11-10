import copy
import importlib.util
import io
import json
from pathlib import Path
import stat
import tempfile
import unittest
import warnings
import zipfile

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
spec = importlib.util.spec_from_file_location('artifact', SCRIPTS / 'link-check-artifact.py')
artifact = importlib.util.module_from_spec(spec)
spec.loader.exec_module(artifact)
# Upstream EXPECTED_JSON from lychee-bin/src/formatters/stats/json.rs,
# https://github.com/lycheeverse/lychee/tree/lychee-v0.24.2
FIXTURE = json.loads((Path(__file__).parent / 'fixtures/lychee-v0.24.2.json').read_text())


class ArtifactTests(unittest.TestCase):
    def read(self, entries=None, event='pull_request', data=None):
        if entries is None:
            entries = [('pr-number.txt', b'4813\n'), ('lychee/out.json', json.dumps(data or FIXTURE).encode())]
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'report.zip'
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', UserWarning)
                with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
                    for name, value in entries:
                        archive.writestr(name, value)
            return artifact.read_artifact(target, event)

    def test_upstream_fixture(self):
        report = self.read()
        self.assertEqual(report['number'], 4813)
        self.assertIn('| Errors | 1 |', report['body'])
        self.assertIn('HTTP 404', report['body'])
        self.assertIn('Timeout:', report['body'])
        self.assertNotIn('Request timed out', report['body'])
        self.assertNotIn('https://example.com/', report['body'])

    def test_zero_links(self):
        data = dict(FIXTURE, **{key: 0 for key in artifact.COUNTERS}, error_map={}, timeout_map={})
        self.assertIn('| Total | 0 |', self.read(data=data)['body'])

    def test_manual_without_number(self):
        result = self.read([('lychee/out.json', json.dumps(FIXTURE))], 'workflow_dispatch')
        self.assertIsNone(result['number'])

    def test_manual_rejects_number(self):
        with self.assertRaises(ValueError):
            self.read(event='workflow_dispatch')

    def test_invalid_numbers(self):
        for value in ['', '0', '-1', '1.0', '1e2', ' 1', '1 ', '1\nnumber=2', '9007199254740992', '１', '1\n\n']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.read([('pr-number.txt', value), ('lychee/out.json', json.dumps(FIXTURE))])

    def test_missing_files(self):
        for entries in [[], [('pr-number.txt', '1')], [('lychee/out.json', json.dumps(FIXTURE))]]:
            with self.subTest(entries=len(entries)), self.assertRaises((ValueError, KeyError)):
                self.read(entries)

    def test_unsafe_paths_and_duplicates(self):
        for name in ['../outside', '/absolute', 'lychee\\out.json', 'extra', 'pr-number.txt', 'lychee/../out.json']:
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.read([('pr-number.txt', '1'), ('lychee/out.json', json.dumps(FIXTURE)), (name, 'x')])

    def test_file_types(self):
        for kind in [stat.S_IFLNK, stat.S_IFIFO, stat.S_IFDIR, stat.S_IFSOCK]:
            info = zipfile.ZipInfo('lychee/out.json')
            info.create_system = 3
            info.external_attr = (kind | 0o644) << 16
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                self.read([('pr-number.txt', '1'), (info, json.dumps(FIXTURE))])

    def test_directory_entry(self):
        self.assertEqual(self.read([('lychee/', ''), ('pr-number.txt', '1'),
                                   ('lychee/out.json', json.dumps(FIXTURE))])['number'], 1)

    def test_size_limits(self):
        with self.assertRaises(ValueError):
            self.read([('pr-number.txt', '1' * 33)])
        with self.assertRaises(ValueError):
            self.read([('lychee/out.json', ' ' * (artifact.MAX_JSON + 1))])
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'large.zip'
            with target.open('wb') as stream:
                stream.truncate(artifact.MAX_ZIP + 1)
            with self.assertRaises(ValueError):
                artifact.read_artifact(target, 'pull_request')

    def test_bad_json_and_utf8(self):
        for raw in [b'\xff', b'null', b'[]', b'{', b'{"total":1,"total":2}', b'{"x":NaN}']:
            with self.subTest(raw=raw), self.assertRaises((ValueError, UnicodeError)):
                self.read([('pr-number.txt', '1'), ('lychee/out.json', raw)])

    def test_bad_schema(self):
        for key, value in [('total', True), ('total', -1), ('errors', '1'), ('error_map', []),
                           ('timeout_map', None), ('total', 2**53)]:
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                self.read(data=dict(FIXTURE, **{key: value}))

    def test_url_injection_is_inert(self):
        data = copy.deepcopy(FIXTURE)
        url = 'https://example.org/`</code><img src=x>@everyone[claim](https://evil.org)'
        entry = next(iter(data['error_map'].values()))[0]
        entry['url'] = url
        entry['status']['text'] = 'Reward approved @everyone'
        body = self.read(data=data)['body']
        for forbidden in ['<img', '@everyone', '[claim]', 'Reward approved', 'https://evil.org']:
            self.assertNotIn(forbidden, body)

    def test_bad_url_and_status(self):
        for field, value in [('url', 'javascript:alert(1)'), ('url', 'https://example.org/\nattack'),
                             ('url', 'https://'), ('status', {'code': True}), ('status', {'code': 999})]:
            data = copy.deepcopy(FIXTURE)
            next(iter(data['error_map'].values()))[0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                self.read(data=data)

    def test_report_size(self):
        data = copy.deepcopy(FIXTURE)
        entry = next(iter(data['error_map'].values()))[0]
        entry['url'] = 'https://example.org/' + 'a' * 8000
        data['error_map'] = {'source': [entry] * 100}
        report = self.read(data=data)
        self.assertLess(len(report['body']), 48000)
        self.assertIn('Details omitted', report['body'])


if __name__ == '__main__':
    unittest.main()
