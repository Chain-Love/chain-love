# Specific network listings

Each subdirectory is one blockchain network (for example `ethereum/`).

Category CSV files in those folders are the entries shown for that network only.

## How references work

A row can either:

- be fully written in this file, or
- reference a canonical offer from `references/offers/<category>.csv`.

Reference format:

- put `!offer:<slug>` in the `offer` column
- example: `!offer:alchemy-free-recent-state`

When a reference is used:

1. Data is loaded from the matching slug in `references/offers/<category>.csv`.
2. Values in this network row override referenced values (for example `chain`, links, or notes).

Use a reference when the offer is mostly the same across networks.  
Write full row values when particular offer is only available for a selected network.
