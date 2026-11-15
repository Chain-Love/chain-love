"""Read the v2 artifact without extracting attacker-controlled ZIP paths."""
import json
import re
import stat
import sys
import zipfile
from pathlib import Path
from urllib.parse import urlsplit

MAX_ZIP = 10 * 1024 * 1024
MAX_JSON = 5 * 1024 * 1024
COUNTERS = {
    'total': '🔍 Total',
    'unique': '🔗 Unique',
    'successful': '✅ Successful',
    'unknown': '❓ Unknown',
    'unsupported': '⛔ Unsupported',
    'timeouts': '⏳ Timeouts',
    'redirects': '🔀 Redirects',
    'remaps': '🔁 Remaps',
    'excludes': '👻 Excludes',
    'errors': '🚫 Errors',
    'cached': '💾 Cached',
}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key] = value
    return result


def render(data):
    if not isinstance(data, dict):
        raise ValueError('Expected a JSON object')
    for key in COUNTERS:
        if type(data.get(key)) is not int or not 0 <= data[key] <= 2**53 - 1:
            raise ValueError('Invalid report counter')
    lines = ['## Link check report', '', '| Status | Count |', '| --- | ---: |']
    lines.extend(f'| {label} | {data[key]} |' for key, label in COUNTERS.items())
    failures = []
    for field, label in [('error_map', 'Error'), ('timeout_map', 'Timeout')]:
        mapping = data.get(field)
        if not isinstance(mapping, dict):
            raise ValueError('Invalid result map')
        for entries in mapping.values():
            if not isinstance(entries, list):
                raise ValueError('Invalid result list')
            for entry in entries:
                if not isinstance(entry, dict):
                    raise ValueError('Invalid result')
                url = entry.get('url')
                if not isinstance(url, str) or len(url) > 8192:
                    raise ValueError('Invalid URL')
                if any(ord(c) < 32 or ord(c) == 127 for c in url):
                    raise ValueError('Control character in URL')
                parsed = urlsplit(url)
                if parsed.scheme not in ('http', 'https') or not parsed.hostname:
                    raise ValueError('Expected HTTP(S) URL')
                status = entry.get('status')
                if not isinstance(status, dict):
                    raise ValueError('Invalid status')
                code = status.get('code')
                if code is not None and (type(code) is not int or not 100 <= code <= 599):
                    raise ValueError('Invalid HTTP status')
                # Never publish status.text/details, map keys or other free text.
                if len(failures) < 100:
                    text = url[:500] + ('…' if len(url) > 500 else '')
                    # Entities are decoded after Markdown/mention parsing. No active links.
                    safe = ''.join(f'&#{ord(c)};' for c in text)
                    failures.append(f'- {label}{f" (HTTP {code})" if code else ""}: <code>{safe}</code>')
    if failures:
        lines += ['', 'Failed URLs (up to 100; URL text comes from the PR):', *failures]
    body = '\n'.join(lines)
    if len(body) > 48000:
        body = '\n'.join(lines[:len(COUNTERS) + 4]) + '\n\nDetails omitted: report is too large. See the analysis artifact.'
    return body


def read_artifact(path, event):
    if event not in ('pull_request', 'workflow_dispatch'):
        raise ValueError('Unsupported event')
    if Path(path).stat().st_size > MAX_ZIP:
        raise ValueError('Archive too large')
    with zipfile.ZipFile(path) as archive:
        seen = set()
        values = {}
        for info in archive.infolist():
            name = info.filename
            if info.orig_filename != name or name in seen or name not in ('pr-number.txt', 'lychee/out.json', 'lychee/'):
                raise ValueError('Unexpected or duplicate ZIP entry')
            seen.add(name)
            mode = info.external_attr >> 16
            kind = stat.S_IFMT(mode)
            if name == 'lychee/':
                if not info.is_dir() or kind not in (0, stat.S_IFDIR) or info.file_size:
                    raise ValueError('Invalid directory')
                continue
            if info.is_dir() or kind not in (0, stat.S_IFREG) or info.flag_bits & 1:
                raise ValueError('Expected an unencrypted regular file')
            limit = 32 if name == 'pr-number.txt' else MAX_JSON
            if info.file_size > limit:
                raise ValueError('Artifact file too large')
            with archive.open(info) as stream:
                raw = stream.read(limit + 1)
            if len(raw) > limit:
                raise ValueError('Artifact file too large')
            values[name] = raw.decode('utf-8', errors='strict')
    number = None
    raw_number = values.get('pr-number.txt')
    if event == 'pull_request' or raw_number is not None:
        if raw_number is None or not re.fullmatch(r'[1-9][0-9]*(?:\r?\n)?', raw_number):
            raise ValueError('Invalid PR number')
        number = int(raw_number)
        if number > 2**53 - 1:
            raise ValueError('PR number out of range')
    if event == 'workflow_dispatch' and number is not None:
        raise ValueError('Unexpected PR metadata in manual report')
    def invalid_constant(_value):
        raise ValueError('Non-finite JSON number')

    data = json.loads(values['lychee/out.json'], object_pairs_hook=unique_object,
                      parse_constant=invalid_constant)
    return {'number': number, 'body': render(data)}


if __name__ == '__main__':
    try:
        print(json.dumps(read_artifact(sys.argv[1], sys.argv[2])))
    except Exception:
        # Do not echo attacker-controlled content or paths to workflow commands/logs.
        sys.exit('Invalid link-check artifact')
