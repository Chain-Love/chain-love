# AGENTS.md

This file helps AI coding agents quickly understand how to read and edit this repository.

## Repository purpose

Chain.Love is a CSV-first Web3 dataset. Contributors edit CSV files, and those CSVs are later transformed into per-network JSON artifacts in another branch/tooling context.

## Canonical data model

Use this conceptual graph when reasoning about data:

`provider -> offer -> listing`

- **Provider**: organization identity and metadata (name, logo, links, description).
- **Offer**: a product/plan sold by a provider in a category (apis, wallets, services, etc.).
- **Listing**: where an offer is available for a specific network (or globally for all networks).

## Directory semantics

Repository paths:

- `references/providers/providers.csv`: provider entities.
- `references/offers`: canonical offer templates.
- `listings/specific-networks/<network>`: chain-specific listing instances.
- `listings/all-networks`: listing instances merged into every chain output.

## CSV schema expectations

- Category CSVs use separate `provider` and `offer` columns.
- Listings should place canonical references in the `offer` column using `!offer:<slug>`.
- `references/providers/providers.csv` uses `logoPath` as filename only (example: `alchemy.png`).
- Consumers should prepend the static prefix `references/providers/images/` during visualization.

## Data contribution rules

- Only add or modify data you are 100% confident is accurate.
- If confidence is below 100% for any value, do not invent data; leave it unchanged and request clarification or a source.
- Before making any data contribution, read the project Style Guide in the GitHub Wiki:
  `https://github.com/Chain-Love/chain-love/wiki/Style-Guide`.

## First files to read for context

1. `README.md`
2. `CONTRIBUTING.md`
3. This file (`AGENTS.md`)