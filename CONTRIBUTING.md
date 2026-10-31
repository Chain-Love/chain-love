# Contributing to Chain.Love


! **We recommend using "Contributor" wizard available at https://app.chain.love/contributor.**

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
| Add a new network | `listings/specific-networks/<network>/` — CSV files **and** chain logo PNGs (see below) |
| Add/update chain logo for a network | `listings/specific-networks/<network>/<chain>.png` |

## How references work

- Category CSV files use separate columns: `provider` and `offer`.
- In `references/offers/*.csv`, set `provider` to the provider name/slug and `offer` to the offer name.
- In listings CSV files, reference canonical offers with `!offer:<slug>` in the `offer` column.
- During JSON generation, referenced fields are hydrated from `references/offers/<category>.csv`.
- Values in the listing row override hydrated values where provided.
- Rows from `listings/all-networks` are appended to every network output.

## Link formatting convention

- In `references/offers/*.csv` (for example `actionButtons`), keep Markdown link style (for example `[Website](https://example.com)`).
- In `references/providers/providers.csv`, keep plain links only (no Markdown wrappers).
- Use full URLs for `website` and `docs`.
- For platform columns with known domains (`x`, `github`, `discord`, `telegram`, `linkedin`), store only the part after the domain.
  - Example: `https://github.com/Chain-Love/chain-love` -> `Chain-Love/chain-love`

## Provider website and docs provenance

A `200 OK` response proves only that a URL is **reachable**. It does not prove
that the page belongs to the provider named in the row. Domains can be parked,
repurposed, taken over, or redirect to unrelated content, and a genuine live
page can document one product while being proposed as provider-wide docs.

For every **new or changed** `website` or `docs` value in
`references/providers/providers.csv`, include one independent first-party
ownership trail in the pull request description:

- a link from the provider's canonical GitHub organization or repository
  README to the exact URL, or
- a link from the provider's official website (an unchanged `website` value)
  to the exact `docs` URL.

A URL in the same provider row is not independent evidence. Product-scoped
documentation (for example, one product's docs for a multi-product collective)
needs explicit scope confirmation; it is not provider-wide documentation by
default.

The link check reports reachability and provenance separately:

| Provenance status | Meaning |
|---|---|
| `first_party_evidenced` | An independent provider-controlled page links to the candidate URL. |
| `needs_manual_identity_review` | No independent crosslink was found, the evidence is product-scoped, or the page is blocked/unknown. A reviewer must confirm identity. |
| `not_applicable` | The field was cleared or is empty. |

`needs_manual_identity_review` is **not** an accusation that a domain was
hijacked. HTTP `401`/`403`/`429`, anti-bot pages, redirects, and discontinued
domains stay in manual review until a maintainer-provided crosslink resolves
them. Never approve a link because the page "looks similar", and never condemn
one because it is blocked.

## Chain logo images

Each `listings/specific-networks/<network>/` folder contains PNG logo files named after
the `chain` values used in that network's CSVs (for example `mainnet.png`, `testnet.png`).

When adding a new network or a CSV that introduces a new `chain` value, include the
corresponding `<chain>.png` in the same PR.

Requirements:
- PNG format, transparent background, square aspect ratio, 160–500 px per side.
- No solid-colour backgrounds (white, black, etc.).
- See [`listings/specific-networks/README.md`](listings/specific-networks/README.md) for
  the full spec and logo source suggestions.

**Required:** Contributors must star the Chain.Love repository before opening a pull request.

## Contribution workflow

1. Star and fork this repository before submitting a contribution.
2. Create a descriptive branch (example: `add-ankr-offer`).
3. Edit the correct CSV based on the table above.
4. Validate locally (optional) or rely on CI checks.
5. Open a PR with a clear description and links to sources for changed data.

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

## Reporting issues

Use [GitHub Issues](https://github.com/Chain-Love/chain-love/issues).

- **Bug Report**: broken database structure or Chain.Love website issue.
- **DB Improvement Proposal (DBIP)**: suggested data model changes (categories, tables, columns).
- **Blank Issue**: anything else.

## Grant program and rewards

See the [Grant Program](../../discussions/41). Database contributions may be eligible for USDT/USDC rewards under certain conditions.


