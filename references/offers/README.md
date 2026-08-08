# Offer references

This directory contains canonical offer templates grouped by category CSV.

An offer represents a reusable product/plan definition. Listings can reference offers
and override network-specific fields.

Offer CSV files use both `provider` and `offer` columns:

- `provider`: provider name/slug
- `offer`: offer/product name

Listings reference offers using `!offer:<slug>`.

## Wallet and write metadata

The `services.csv`, `platforms.csv`, and `mcpservers.csv` offer tables include
wallet interaction metadata. `walletConnection` is `none`, `optional`,
`required`, or `unknown`; use `unknown` only after reviewing the source and
finding the normal wallet requirement unclear. A blank cell means the row has
not been backfilled for that field yet. `onChainWrite` is `TRUE` or `FALSE`
when source-backed; leave it blank only in tables where the schema permits
incremental backfill. Add a listing-level override when behavior differs by
network.
