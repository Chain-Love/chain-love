# Contributor snapshot

Each `contributor-v1-<sourceSha>` release is tagged at the exact source commit
and has three assets. The release is excluded from `releases/latest`.

| Asset | Contract |
| --- | --- |
| `manifest.json` | `schemaVersion`, `generatorVersion`, `sourceSha`, and an `assets` map keyed by filename with lowercase hex `sha256` and byte `size` |
| `contributor-index.json` | The same version and source fields plus the four arrays below |
| `contributor-sources.tar.gz` | Regular files with the original CSV bytes at the repo-relative paths in `files` |

The index arrays are:

- `files` — `path`, `blobSha`, `kind`, `category`, `network`. The kind is
  `provider`, `offer`, `all-networks`, or `specific-network`. Category and
  network are nullable.
- `providers` — `file`, `slug`, `line`, `name`.
- `offers` — `file`, `slug`, `line`, `providerSlug`, `name`.
- `listings` — `file`, `slug`, `line`, `providerSlug`, `offerId`, `offerLabel`,
  `chain`. Chain is the source CSV cell, or null when absent. Standalone
  listings have a null `offerId` and may have a plain-text `offerLabel`.

`file` is a zero-based index into `files` within this snapshot. A source record
is identified by its resolved path and trimmed slug. `line` is its one-based
physical start line for display. An `offerId` is a `{file, slug}` reference to
the canonical offer in the listing's category. The listing's `providerSlug`
is its effective provider after applying the CSV override. A cross-provider
listing keeps both links. Each all-networks row occurs once in the index.

Consumers can derive the release tag from the current source SHA, check both
asset digests against the manifest and keep the verified snapshot in memory.
Before using it for a deletion, verify the target branch still has the
manifest's `sourceSha`. Derive category and network metadata from the file
table, and resolve records by path and slug when preparing the CSV diff.

`generatorVersion` is the version in the tag. Increment it when intentionally
reissuing different assets for an already published source SHA. Change
`schemaVersion` when the consumer contract changes and coordinate support for
the new tag version with Contributor.

The generator, publisher, tests, and this contract live in `tools/` on the
`json-tools` branch. The Actions workflow lives on `main` and must check out
both the source data and the tooling. Run the scripts with the data Git
repository as the working directory; `--source-sha` always identifies a data
commit, not the tooling commit. The workflow uses `ref: json-tools` to load
the tooling version available on that branch at checkout time.

To build and verify locally from this repository root with Python 3.11 or
later, use the fetched data commit even when the current branch is tooling:

```sh
source_sha=$(git rev-parse origin/main)
scratch_dir=$(mktemp -d)
python3 tools/contributor_snapshot.py build --source-sha "$source_sha" --output "$scratch_dir/snapshot"
python3 tools/contributor_snapshot.py verify --source-sha "$source_sha" --output "$scratch_dir/snapshot"
```

Run the focused tests with:

```sh
python3 -B -m unittest discover -s tools -p 'test_contributor_snapshot.py' -v
bash -n tools/publish_contributor_snapshot.sh
```
