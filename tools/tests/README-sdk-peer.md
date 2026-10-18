# SDK peer requirements — DBIP #4151

This implements the tooling portion of [DBIP #4151](https://github.com/Chain-Love/chain-love/issues/4151). Approval of the proposed model is still pending. It adds no production data rows or headers and requests no separate data reward.

`peerRequirements` is an optional SDK-only object containing `package`, `version`, `source`, and a nonempty `requirements` map. Each peer has its original npm constraint expression and a mandatory boolean `optional`. Record published `peerDependencies` only; `optional` is true only when `peerDependenciesMeta` explicitly marks that peer optional. This is declared compatibility metadata, not a compatibility test or a semver resolver.

The `source` must equal `https://registry.npmjs.org/` + the fully URL-encoded package name + `/` + the fully URL-encoded fixed version. Mutable tags, queries and package/version mismatches are rejected. The nested version identifies the evidence artifact; it does not change the automation-owned release/license fields. Validators check structure and source identity offline; they do not fetch the manifest or prove every recorded constraint matches it.

Blank and whole-cell null normalize to null. Under existing `!offer:` semantics they inherit a non-null canonical declaration. A non-null listing override replaces the complete declaration; peer maps are not merged. Empty objects/maps are invalid, and null must never be interpreted as “the SDK has no peers.”

The fixtures reproduce these published manifests:

- [abitype 1.3.0](https://registry.npmjs.org/abitype/1.3.0): optional TypeScript `>=5.0.4` and zod `^3.22.0 || ^4.0.0`.
- [@filoz/synapse-react 0.5.0](https://registry.npmjs.org/%40filoz%2Fsynapse-react/0.5.0): four peers with no optional peer metadata, therefore explicit `optional: false`.

Run offline production-schema/converter checks from this checkout:

```sh
python -m unittest discover -s tools/tests -p test_sdk_peer_requirements.py
```

For a full pipeline check against an existing public main checkout:

```sh
python tools/tests/check_sdk_peer_pipeline.py --data-repo /path/to/chain-love-main --data-ref d63e7e438588aff29c2b819ff6c34abb7ed6a0ac --verify-sources
```

This extracts disposable data snapshots with `git archive`, runs the real CSV → JSON → full-schema pipeline on unchanged data and a two-offer pilot, checks Filecoin/Somnia inheritance and preservation of prior SDK values, and requires invalid listing and generated-JSON sources to fail. It does not write into the supplied checkout. Logs and a JSON report are placed in a temporary directory, or a fresh directory supplied by `--output`. `--verify-sources` adds fixed-version manifest fetches; without it the check is offline.

Use the existing validation dependencies in `tools/requirements.txt`. No upstream SDK is installed or executed by the tests. The source-fixture values were checked against the version-specific published manifests during preparation.

After model approval, the separate main-branch migration should add the optional SDK headers and backfill the two existing examples. Existing dependencies and all reserved automation fields are preserved. No automatic extraction or database-wide dependency rewrite is introduced here.

The paragraphs above can be used as proposed SDK wiki documentation after acceptance; this branch does not change the wiki.
