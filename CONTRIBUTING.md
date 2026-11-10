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
5. Go through [Before you submit](#before-you-submit) below.
6. Open a PR with a clear description and links to sources for changed data.

## Before you submit

These checks catch common, avoidable reasons for change requests in review. The wiki remains the authoritative source for every definition; follow the links for details.

1. **Fill each column as its wiki page defines it.** Pick `planType` from the values listed in [Common Columns](https://github.com/Chain-Love/chain-love/wiki/Common-Columns#plantype) (`Public` = no payment or registration; `Free` = no payment, but registration is needed). In SDKs, do not fill `latestKnownVersion`, `latestKnownReleaseDate`, `maintainer` or `license` by hand: they are reserved for automation and [can't be modified manually](https://github.com/Chain-Love/chain-love/wiki/SDKs#latestknownversion-latestknownreleasedate-maintainer-and-license). For new or changed `dependencies`, include only verified required peer dependencies and direct package/module prerequisites that users must provide separately, with identifiers only and no versions ([SDK dependencies](https://github.com/Chain-Love/chain-love/wiki/SDKs#dependencies)). Required peer dependencies remain eligible even if installed automatically.
2. **Search open PRs for the same provider, offer or listing before opening yours.** If two open PRs overlap, a maintainer confirms which one lands. An overlapping PR should not receive final approval until one of these happens: the overlap is removed, the competing PR is closed or changed, or the maintainer's choice is recorded.
3. **Keep CSVs sorted, booleans uppercase and provider logos in place.** Keep each CSV A-Z sorted by `slug` ([General rules](https://github.com/Chain-Love/chain-love/wiki/Style-Guide#general-rules)) and write booleans as uppercase `TRUE`/`FALSE` ([Booleans](https://github.com/Chain-Love/chain-love/wiki/Style-Guide#booleans)). A new provider also needs `logoPath` set to the PNG filename only (for example `alchemy.png`, see [Link formatting](https://github.com/Chain-Love/chain-love/wiki/Style-Guide#link-formatting)) and the official PNG logo under that name in `references/providers/images/`. Do not use SVG or other formats for provider logos.
4. **`actionButtons`: max 2 buttons.** `Public` endpoints get a `Send Requests` button with a direct link; `Enterprise` plans get a `Contact Sales` button with a contact form link ([Common Columns](https://github.com/Chain-Love/chain-love/wiki/Common-Columns#actionbuttons)). In SDKs, at least one button must lead to an official download source such as GitHub or the npm registry ([SDKs](https://github.com/Chain-Love/chain-love/wiki/SDKs#actionbuttons)).
5. **Resolve merge conflicts.** If GitHub reports a conflict with `main`, before or after you open the PR, resolve it, for example by rebasing your branch on `main`.
6. **Override only what is specific to that network.** A non-blank listing cell replaces the canonical value instead of merging with it, so an `actionButtons` override must contain the full final set of buttons ([Merge behavior](https://github.com/Chain-Love/chain-love/wiki/References-Syntax#merge-behavior)).
7. **Open every link you add and confirm that the provider supports that network** before submitting ([General rules](https://github.com/Chain-Love/chain-love/wiki/Style-Guide#general-rules)).
8. **Choose the category from [Categories definitions](https://github.com/Chain-Love/chain-love/wiki/Categories-definitions#classification-sequence).** If you are unsure, ask in [Discussions Q&A](https://github.com/Chain-Love/chain-love/discussions/categories/q-a) first: a PR "may be closed simply because the category was poorly chosen". A completely network-agnostic offer should have its listing in `listings/all-networks/`; its canonical offer remains in `references/offers/` ([Database structure](https://github.com/Chain-Love/chain-love/wiki/Style-Guide#database-structure)).
9. **For data contributions, confirm that the CSV changes affect the final hydrated output.** Redundant overrides should be removed. A PR that makes no change to the final hydrated data (for example, a listing override equal to the inherited canonical value) should be closed without merging.
10. **Keep the title and description in line with the diff.** Do not use a closing keyword (`Closes #N`, `Fixes #N`, `Resolves #N`) unless the PR implements all of that issue.

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

### Ecosystem outreach bounty

Chain.Love also runs an [Ecosystem Discovery Bounty Program](../../discussions/3731) for contributors who find relevant opportunities to add Chain.Love to external ecosystem documentation, developer catalogs, resource directories, and similar developer resources.

For this program, contributors prepare the proposed patch but **must not contact the destination project or open an external PR, issue, or discussion themselves**. Each prepared proposal should be submitted as a separate Discussion in the [Outreach program submissions](https://github.com/Chain-Love/chain-love/discussions/categories/outreach-program-submissions) category for review by an authorized Chain.Love outreacher.

Read the [full program rules](../../discussions/3731) before preparing a submission.


