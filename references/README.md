# References

This directory contains reusable canonical data.

- `providers/providers.csv`: provider identity records (organization-level metadata).
- `offers/`: offers of providers that can be referenced by listings.

Use references for data you want to define once and reuse across many listings.

## Provider metadata and logos

`providers/providers.csv` main fields:

- `slug`: unique provider identifier.
- `name`: provider display name.
- `aliases`: optional JSON array of documented former or alternate official names for the same provider entity.
- `logoPath`: logo filename only (for example `alchemy.png`).
- `description`: short provider summary.
- link fields:
  - `website`, `docs`: full URL format (for example `https://example.com`).
  - `x`, `github`, `discord`, `telegram`, `linkedin`: store value after domain only.
    - Example: `https://github.com/Chain-Love/chain-love` -> `Chain-Love/chain-love`.

Link style difference:

- `references/providers/providers.csv`: plain URLs in dedicated link columns.
- `references/offers/*.csv`: Markdown links (commonly inside `actionButtons`).

Provider aliases:

- Keep `name` as the current display name and `slug` as the canonical identifier.
- Use `aliases` only for documented former names or alternate official names of the same entity.
- Do not add product names, slogans, or unrelated subsidiaries as aliases.
- Store an empty cell when a provider has no verified aliases; the generated JSON uses `null`.
- Downstream provider search and duplicate detection should compare aliases case- and punctuation-insensitively.
