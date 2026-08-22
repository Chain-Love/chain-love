# Offer references

This directory contains canonical offer templates grouped by category CSV.

An offer represents a reusable product/plan definition. Listings can reference offers
and override network-specific fields.

Offer CSV files use both `provider` and `offer` columns:

- `provider`: provider name/slug
- `offer`: offer/product name

Listings reference offers using `!offer:<slug>`.

## Payments offers

`payments.csv` contains payment-specific offer templates for checkout, payment links,
merchant gateways, x402 flows, paymasters, and on-chain payouts. Its comparison fields
cover `paymentType`, `settlementAssets`, `settlementChains`, `custodial`, `kycLevel`,
`developerInterface`, `x402`, `onChainSettlement`, and `nonCustodial` in addition to
the shared plan, pricing, link, tag, and description fields.

Leave a payment attribute blank when the linked official source does not document it;
do not infer custody, KYC, supported chains, or settlement assets from a provider's
general marketing copy.
