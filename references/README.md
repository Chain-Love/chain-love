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
  - `x`, `github`, `discord`, `telegram`, `linkedin`: store value after domain only.
    - Example: `https://github.com/Chain-Love/chain-love` -> `Chain-Love/chain-love`.

Link style difference:

- `references/providers/providers.csv`: plain URLs in dedicated link columns.
- `references/offers/*.csv`: Markdown links (commonly inside `actionButtons`).

## Offer-to-provider references

Every non-empty `providerSlug` value in `offers/*.csv` must match exactly one
`slug` in `providers/providers.csv`. The slug is the stable, machine-readable
relationship; `providers.csv:name` is presentation metadata and must not be
used as the canonical join key. Generated JSON exposes the resolved display
name as `provider` and retains `providerSlug` for consumers that need a stable
join.
