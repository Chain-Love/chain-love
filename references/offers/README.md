# Offer references

This directory contains canonical offer templates grouped by category CSV.

An offer represents a reusable product/plan definition. Listings can reference offers
and override network-specific fields.

Offer CSV files use both `provider` and `offer` columns:

- `provider`: provider name/slug
- `offer`: offer/product name

Listings reference offers using `!offer:<slug>`.

## Wallet and write metadata

The `services.csv`, `platforms.csv`, and `mcpservers.csv` offer tables include the optional `walletConnection` and `onChainWrite` fields. `walletConnection` is `none`, `optional`, `required`, or `unknown`; `onChainWrite` is `TRUE`, `FALSE`, or blank when the authoritative source does not establish the value. Use source-backed values only, and add a listing-level override when behavior differs by network.
