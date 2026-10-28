# Opt-in schema 2.1.0 (DBIPs #2481, #2681, #2682, #2561, #2624)

The default export and `tools/schema.json` remain 2.0.0. No current consumer
has to migrate. The converter accepts both old and new CSV headers, resolves
aliases before offer inheritance, and rejects conflicting values.

Opt in from a data checkout with the tools and meta files available:

```
python csv_to_json.py --schema-version 2.1.0
python validate.py --schema-version 2.1.0
```

Generate the exact schema with `schema_for_version(base_schema, '2.1.0')` from
`schema_versions.py`. This derives the new contract from the unchanged 2.0.0
schema; the new document has its own `$id` and `schemaVersion`. The new `$id`
is an identifier, not a claim that a schema has been hosted at that URL.

| Category | 2.0.0 | 2.1.0 |
|---|---|---|
| explorers | pricing | price |
| bridges, oracles | economicalSecurity / economicalSecurityNote | economicSecurity / economicSecurityNote |
| wallets | audit | auditsPerformed |
| storages | no trial field | optional boolean or null trial |
| bridges | no route field | optional supportedRoutes array or null |

Legacy projection removes the new optional fields and restores the old field
names, column order and column metadata. API trial fields and other categories
are unchanged. Both versions validate new input values before projection.

## Storage trial

`TRUE` means this specific offer is a time-bounded trial. `FALSE` means a verified
ongoing free or paid offer. An ongoing paid plan does not become a trial offer
just because new customers receive introductory trial access. Blank/null means
unknown; it inherits the canonical offer value in listings. Do not infer FALSE
from missing documentation. This intentionally refines the DBIP's proposed
default to comply with the repository's no-guessing rule.

## Bridge routes

`supportedRoutes` is a nonempty JSON array or null. Every object requires
`sourceChain` and `destinationChain`, using exact network folder slugs. The
endpoints must differ and, if supportedChains is populated, appear there too.
Optional `assetSymbols` is a nonempty sorted array of unique trimmed strings.
Sort routes by source then destination. Record one object per ordered pair;
combine documented assets for that pair. Do not infer reverse routes or the
Cartesian product of supportedChains. Missing routes mean unknown, not unsupported.
Listing overrides replace the route array; null/blank inherits it.

## Rollout

1. Merge tools support first. Existing workflows can find the helper in their
   `json-tools/tools` checkout even before they copy it alongside the entrypoints.
2. Merge the paired header/data migration and workflow copy updates.
3. Consumers may explicitly request 2.1.0 after adopting the renamed fields.
   Default releases still use 2.0.0. Publish/version any new release separately;
   this change does not switch scheduled releases or promise a hosted endpoint.
4. Update the Explorers, Bridges, Oracles, Wallets, Storages and common-column
   wiki guidance using the definitions above. Wiki edits require maintainer access.

Validation: `python -m unittest discover -s tools -p 'test_schema_versions.py' -v`.
