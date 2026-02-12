# Contributing to Chain.Love

This repository is intentionally CSV-first so contributors can edit data in spreadsheet tools without programming knowledge.

## Start here (required)

Before editing data, read the Style Guide:

- [Style Guide](https://github.com/Chain-Love/chain-love/wiki/Style-Guide)
- [Column Definitions](https://github.com/Chain-Love/chain-love/wiki)


## Data model

`provider -> offer -> listing`

- `references/providers/providers.csv`: provider identity metadata.
- `references/offers`: canonical offer templates.
- `listings/specific-networks/<network>`: listings for one network.
- `listings/all-networks`: listings merged into every network output.

## Where to edit

| Goal | Edit here |
|---|---|
| Add/update provider profile metadata | `references/providers/providers.csv` |
| Add/update provider logo files | `references/providers/images/` |
| Add/update reusable offer (product/plan) | `references/offers/<category>.csv` |
| Add/update an offer on one chain | `listings/specific-networks/<network>/<category>.csv` |
| Add/update entries for every chain | `listings/all-networks/<category>.csv` |

## How to populate `references/providers/providers.csv`

Required baseline fields:

- `slug`: unique provider id (stable, lowercase kebab-case recommended).
- `name`: provider display name.
- `description`: concise provider description.
- `logoPath`: logo filename only, format `<slug>.png`.

Optional enrichment fields:

- `website`, `docs`, `x`, `github`, `discord`, `telegram`, `linkedin`, `supportEmail`.
- `tag` for custom grouping/search tags.

Logo guidance:

- Put logo files into `references/providers/images/`.
- Keep filename aligned with provider slug.
- Visualization should prepend `references/providers/images/` to `logoPath`.
- See `references/providers/images/README.md` for image recommendations.

## How references work

- Category CSV files use separate columns: `provider` and `offer`.
- In `references/offers/*.csv`, set `provider` to the provider name/slug and `offer` to the offer name.
- In listings CSV files, reference canonical offers with `!offer:<slug>` in the `offer` column.
- During JSON generation, referenced fields are hydrated from `references/offers/<category>.csv`.
- Values in the listing row override hydrated values where provided.
- Rows from `listings/all-networks` are appended to every network output.

## Contribution workflow

1. Fork this repository and create a descriptive branch (example: `add-ankr-offer`).
2. Edit the correct CSV based on the table above.
3. Validate locally (optional) or rely on CI checks.
4. Open a PR with a clear description and links to sources for changed data.

## Local validation (optional)

Our CI will automatically run on every commit you make in an open PR and verify if your patches don't break anything. However, to make your contribution cleaner - you can make your computer run the same verifications locally before every commit.

Install and enable pre-commit:

1. Install `python3`.
2. Install `pipx`.
3. Install `pre-commit` with `pipx install pre-commit`.
4. Run `pre-commit install` in the repository root.

Verification commands:

```bash
python3 --version
pipx --version
pre-commit --version
```

Platform-specific install links:

- Python: <https://www.python.org/downloads/>
- pipx: <https://pipx.pypa.io/stable/installation/>

Alternatively - consider using "Contributor" wizard - click "+ Add provider" at any network's Toolbox (e.g. https://filecoin.chain.love)

## Reporting issues

Use [GitHub Issues](https://github.com/Chain-Love/chain-love/issues).

- **Bug Report**: broken database structure or Chain.Love website issue.
- **DB Improvement Proposal (DBIP)**: suggested data model changes (categories, tables, columns).
- **Blank Issue**: anything else.

## Grant program and rewards

See the [Grant Program](../../discussions/41). Database contributions may be eligible for USDT/USDC rewards under certain conditions.


