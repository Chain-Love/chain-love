"""Opt-in DBIP schema evolution; the default export remains 2.0.0."""
import copy
from pathlib import Path

from jsonschema import Draft202012Validator

VERSIONS = ('2.0.0', '2.1.0')
RENAMES = {
    'explorers': {'pricing': 'price'},
    'wallets': {'audit': 'auditsPerformed'},
    'bridges': {'economicalSecurity': 'economicSecurity',
                'economicalSecurityNote': 'economicSecurityNote'},
    'oracles': {'economicalSecurity': 'economicSecurity',
                'economicalSecurityNote': 'economicSecurityNote'},
}
TRIAL = {'type': ['boolean', 'null']}
ROUTES = {
    'type': ['array', 'null'], 'minItems': 1, 'uniqueItems': True,
    'items': {
        'type': 'object', 'additionalProperties': False,
        'required': ['sourceChain', 'destinationChain'],
        'properties': {
            'sourceChain': {'type': 'string', 'pattern': '^[a-z0-9]+(?:-[a-z0-9]+)*$'},
            'destinationChain': {'type': 'string', 'pattern': '^[a-z0-9]+(?:-[a-z0-9]+)*$'},
            'assetSymbols': {'type': 'array', 'minItems': 1, 'uniqueItems': True,
                             'items': {'type': 'string', 'minLength': 1}},
        },
    },
}


def check_version(version):
    if version not in VERSIONS:
        raise ValueError(f'Unsupported schema version: {version}')


def schema_for_version(base, version):
    check_version(version)
    schema = copy.deepcopy(base)
    if version == '2.0.0':
        return schema
    schema['$id'] = 'https://chain.love/schemas/infrastructure/2.1.0'
    schema['properties']['schemaVersion']['const'] = version
    for category, names in RENAMES.items():
        definition = schema['$defs'][category]
        for old, new in names.items():
            definition['properties'][new] = definition['properties'].pop(old)
            definition['required'] = [new if key == old else key for key in definition['required']]
    schema['$defs']['storages']['properties']['trial'] = copy.deepcopy(TRIAL)
    schema['$defs']['bridges']['properties']['supportedRoutes'] = copy.deepcopy(ROUTES)
    return schema


def route_errors(rows, networks=None):
    """Validate ordered routes without inferring reverse routes or asset coverage."""
    errors = []
    validator = Draft202012Validator(ROUTES)
    for row in rows:
        routes = row.get('supportedRoutes')
        problems = list(validator.iter_errors(routes))
        prefix = f"Bridge {row.get('slug', '<unknown>')}: "
        if problems:
            errors.extend(prefix + problem.message for problem in problems)
            continue
        if routes is None:
            continue
        pairs = []
        for route in routes:
            source, destination = route['sourceChain'], route['destinationChain']
            pairs.append((source, destination))
            if source == destination:
                errors.append(prefix + 'route endpoints must differ')
            if networks is not None and not {source, destination} <= networks:
                errors.append(prefix + 'route endpoint is not a network folder slug')
            chains = row.get('supportedChains')
            if chains and (source not in chains or destination not in chains):
                errors.append(prefix + 'route endpoints must appear in supportedChains')
            assets = route.get('assetSymbols', [])
            if any(not asset.strip() or asset != asset.strip() for asset in assets) or assets != sorted(assets):
                errors.append(prefix + 'assetSymbols must be trimmed and sorted')
        if pairs != sorted(pairs) or len(pairs) != len(set(pairs)):
            errors.append(prefix + 'routes must be sorted and unique by ordered endpoints')
    return errors


def project_data(data, version, legacy_metadata=None, networks=None):
    """Project normalized, resolved rows and their presentation metadata together."""
    check_version(version)
    result = copy.deepcopy(data)
    errors = route_errors(result.get('bridges', []), networks)
    for row in result.get('storages', []):
        errors.extend(error.message for error in Draft202012Validator(TRIAL).iter_errors(row.get('trial')))
    if errors:
        raise ValueError('\n'.join(errors))
    for category, names in RENAMES.items():
        for row in result.get(category, []):
            for old, new in names.items():
                if old in row and new in row and row[old] != row[new]:
                    raise ValueError(f'{category}: conflicting {old}/{new} values')
                source, target = (old, new) if version == '2.1.0' else (new, old)
                if source in row:
                    row[target] = row.pop(source)
        columns = result.get('columns', {}).get(category)
        if columns is not None:
            mapping = names if version == '2.1.0' else {v: k for k, v in names.items()}
            result['columns'][category] = list(dict.fromkeys(mapping.get(key, key) for key in columns))
    if version == '2.0.0':
        for category, key in [('storages', 'trial'), ('bridges', 'supportedRoutes')]:
            for row in result.get(category, []):
                row.pop(key, None)
            if category in result.get('columns', {}):
                result['columns'][category] = [col for col in result['columns'][category] if col != key]
    if 'schemaVersion' in result:
        result['schemaVersion'] = version
    if 'columns' in result.get('meta', {}):
        metadata = result['meta']['columns']
        if version == '2.0.0' and legacy_metadata is not None:
            result['meta']['columns'] = copy.deepcopy(legacy_metadata)
        elif version == '2.1.0':
            for names in RENAMES.values():
                for old, new in names.items():
                    if old in metadata:
                        entry = metadata.pop(old)
                        entry['key'] = new
                        metadata.setdefault(new, entry)
            metadata['supportedRoutes'] = {
                'key': 'supportedRoutes', 'label': 'Supported Routes',
                'description': 'Verified ordered routes; chain membership does not imply a route.',
                'filter': None, 'sorting': None, 'pinning': None, 'cellType': None,
                'group': 'serviceDetails', 'icon': None,
            }
    return result


def canonicalize_fields(data):
    """Unify aliases before inheritance; defer route checks until after resolution."""
    result = copy.deepcopy(data)
    for category, names in RENAMES.items():
        for row in result.get(category, []):
            for old, new in names.items():
                if old in row and new in row and row[old] != row[new]:
                    raise ValueError(f'{category}: conflicting {old}/{new} values')
                if old in row:
                    row[new] = row.pop(old)
    return result


def network_slugs(root='listings/specific-networks'):
    path = Path(root)
    return {entry.name for entry in path.iterdir() if entry.is_dir()}
