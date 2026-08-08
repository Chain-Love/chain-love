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
- link fields:
  - `website`, `docs`: full URL format (for example `https://example.com`).
  - `x`, `discord`, `telegram`, `linkedin`: store the value after the platform domain only.
  - `github`: store the owning GitHub organization or account login only; repository paths are not stored in provider identity metadata.
    - Example: `https://github.com/Chain-Love/chain-love` -> `Chain-Love`.

Link style difference:

- `references/providers/providers.csv`: plain URLs in dedicated link columns.
- `references/offers/*.csv`: Markdown links (commonly inside `actionButtons`).
