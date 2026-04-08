# Listings

This directory contains concrete listing instances (e.g. this folder answers the question "On which networks offers mentioned in `references` folder are available?")

- `specific-networks/`: for the offers that are available on the specific networks only.
- `all-networks/`: for offers available on all networks. Note: all networks - means being fully chain-agnostic, and only applies for the offers that may exist virtually on any network, not only the ones that already exist in `specific-networks/`

Listings are the final node in the model:
`provider -> offer -> listing`.

## Adding a new network

A complete new network contribution includes:

1. A new folder under `specific-networks/<network>/` with the category CSV files.
2. **Chain logo PNG files** inside that folder — one per unique `chain` value used in
   the CSVs (e.g. `mainnet.png`, `testnet.png`). Transparent background required.

See [`specific-networks/README.md`](specific-networks/README.md) for the full image spec.
