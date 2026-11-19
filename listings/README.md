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

## Limiting global listings on a network's chains

When a newly listed chain is not known to support the chain-aware offers in
`listings/all-networks/`, add an optional
`listings/specific-networks/<network>/global-chain-scope.json` file:

```json
{
  "chains": ["mainnet", "testnet"]
}
```

The JSON generator on the `json-tools` branch expands chain-aware global listings
only for those explicitly allowed chain IDs. The default for networks without this
file remains unchanged (all discovered chains). Network-specific listings,
including a newly introduced BetaNet faucet, are never filtered by this policy.
This prevents new chain IDs from accidentally inheriting global EVM RPC and
analytics claims that have not been verified for them.
