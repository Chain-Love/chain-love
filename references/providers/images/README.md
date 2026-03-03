# Provider logos

Store provider logo files in this folder.

## Naming rules

- One logo file per provider.
- Filename must match `references/providers/providers.csv` `slug` value.
- Preferred extension: `.png`.
- Example: if slug is `alchemy`, `logoPath` value in CSV is `alchemy.png`.

## How it connects to data

- `references/providers/providers.csv` uses `logoPath` as filename only (no directory prefix).
- Set `logoPath` to `<slug>.png`.

## Recommended image format

- Square logo (1:1 aspect ratio), transparent background when possible.
- Recommended size: between 160x160 to 500x500 pixels.
