# Offer references

This directory contains canonical offer templates grouped by category CSV.

An offer represents a reusable product/plan definition. Listings can reference offers
and override network-specific fields.

Offer CSV files use both `provider` and `offer` columns:

- `provider`: provider name/slug
- `offer`: offer/product name

Listings reference offers using `!offer:<slug>`.
