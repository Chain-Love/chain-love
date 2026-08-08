# Offer references

This directory contains canonical offer templates grouped by category CSV.

An offer represents a reusable product/plan definition. Listings can reference offers
and override network-specific fields.

Offer CSV files use both `provider` and `offer` columns:

- `provider`: provider name/slug
- `offer`: offer/product name

Listings reference offers using `!offer:<slug>`.

## API authentication metadata

API offers may use the optional authenticationMethods JSON array to record
provider-documented request credentials: none, api_key, bearer_token, jwt,
basic_auth, oauth2, mtls, or wallet_signature. Leave the cell blank when the
method has not been verified; none cannot be combined with another value, and
credentials or secrets must never be stored here.

Use securityImprovements for protective controls such as DDoS protection,
encryption, key rotation, allow lists, rate limiting, private endpoints, or
dedicated infrastructure. Do not use it as a substitute for the normalized
request-authentication field.
