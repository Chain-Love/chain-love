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

## API throughput and quota fields

API offer tables and API listing tables may use these optional normalized fields:

- `throughputLimit`: non-negative numeric maximum documented processing rate.
- `throughputUnit`: unit for `throughputLimit`, such as `requests/second`, `compute units/second`, or `requests/10 seconds`.
- `usageQuota`: non-negative numeric documented allowance.
- `usageQuotaUnit`: unit for `usageQuota`, such as `requests`, `credits`, or `compute units`.
- `quotaPeriod`: period for `usageQuota`, currently `day`, `month`, or `lifetime`.

Keep the original provider wording in `limitations` and retain the provider's source links in `actionButtons`. Preserve provider-native units; do not convert compute units, credits, or other capacity units into requests unless the provider documents a deterministic conversion. Leave normalized fields blank when the source is custom, dynamic, a range or alternative set, burst/soft/hard limits, or otherwise cannot be represented by the single-value fields.

When an offer is referenced from a listing, populate these fields in `references/offers/apis.csv`; the generated listing inherits them. Direct listing rows may populate the fields when their own `limitations` value is explicit and source-backed.
