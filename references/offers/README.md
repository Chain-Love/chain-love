# Offer references

This directory contains canonical offer templates grouped by category CSV.

An offer represents a reusable product/plan definition. Listings can reference offers
and override network-specific fields.

Offer CSV files use both `provider` and `offer` columns:

- `provider`: provider name/slug
- `offer`: offer/product name

Listings reference offers using `!offer:<slug>`.

## Security offer capability fields

Security offers may use these optional JSON-array columns:

- `supportedLanguages`: programming or smart-contract languages that the provider
  explicitly documents as analysis, testing, scanning, or audit targets.
- `supportedFrameworks`: build, development, or testing frameworks for which the
  provider explicitly documents direct integration or project ingestion.

Leave either field blank when support is undocumented or not applicable. Do not
infer a language from `executionEnvironment` alone. Values must be non-empty,
deduplicated strings with the provider's documented capitalization; examples
include `["Solidity"]`, `["Solidity","Vyper"]`, and
`["Foundry","Hardhat"]`.
