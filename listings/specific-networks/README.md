# Specific network listings

Each subdirectory is one blockchain network (for example `ethereum/`).

Category CSV files in those folders are the entries shown for that network only.

## Adding a new network

When creating a new `<network>/` folder, you must also add chain logo image files
alongside the CSV data.

**One PNG per unique `chain` column value** used in that network's CSV files.

File naming rule: filename = the `chain` value (for example `mainnet.png`, `testnet.png`).

Example — if your new network's CSVs contain `chain = mainnet` and `chain = testnet`:

```
listings/specific-networks/<network>/
  mainnet.png
  testnet.png
  apis.csv
  explorers.csv
  ...
```

Logo requirements (same as `references/providers/images/`):

- PNG format, `.png` extension.
- Square 1:1 aspect ratio with **transparent background** — no white, black, or solid fills.
- Recommended size: 160×160 to 500×500 px.
- Use the network's official logo. Check the project's `/brand`, `/press`, or `/media` page,
  or its GitHub organisation for a transparent-background asset.
- If only a logo with a solid background is available, remove it with
  [remove.bg](https://www.remove.bg), [Erase.bg](https://www.erase.bg), or ImageMagick
  before submitting.

See [`references/providers/images/README.md`](../../references/providers/images/README.md)
for the full logo spec and visual examples of acceptable vs. unacceptable assets.

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
