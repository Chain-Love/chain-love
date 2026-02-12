# References

This directory contains reusable canonical data.

- `providers/providers.csv`: provider identity records (organization-level metadata).
- `offers/`: offers of providers that can be referenced by listings.

Use references for data you want to define once and reuse across many listings.

## Provider metadata and logos

`providers/providers.csv` main fields:

- `slug`: unique provider identifier.
- `name`: provider display name.
- `logoPath`: logo filename only (for example `alchemy.png`).
- `description`: short provider summary.

Provider logo assets are stored in:

- `references/providers/images/`

Visualization should resolve logo file as:

`references/providers/images/` + `logoPath`
