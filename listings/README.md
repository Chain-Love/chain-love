# Listings

This directory contains concrete listing instances (e.g. this folder answers the question "On which networks offers mentioned in `references` folder are available?")

- `specific-networks/`: for the offers that are available on the specific networks only.
- `all-networks/`: for offers available on all networks. Note: all networks - means being fully chain-agnostic, and only applies for the offers that may exist virtually on any network, not only the ones that already exist in `specific-networks/`

Listings are the final node in the model:
`provider -> offer -> listing`.
