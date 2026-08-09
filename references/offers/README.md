# Offer references

This directory contains canonical offer templates grouped by category CSV.

An offer represents a reusable product/plan definition. Listings can reference offers
and override network-specific fields.

Offer CSV files use both `provider` and `offer` columns:

- `provider`: provider name/slug
- `offer`: offer/product name

Listings reference offers using `!offer:<slug>`.

## Wallet recovery metadata

Wallet offers may define `recoveryMethods` as a JSON array of documented access
recovery mechanisms. Allowed values are `seed_phrase`, `cloud_backup`,
`social_guardians`, `multisig`, `passkey`, `hardware_backup`,
`provider_assisted`, `none`, and `unknown`. Use `unknown` for unreviewed
migration rows and do not infer a recovery method from `keyExport`. The `none`
value is exclusive.

Use `recoveryDelay` only for a documented product- or protocol-enforced waiting
period such as `0`, `24h`, or `7d`; leave it blank when no delay is documented
or the field is not applicable. Keep an authoritative provider documentation
link in `actionButtons` for rows populated with a known method.
