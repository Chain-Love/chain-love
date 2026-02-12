# Provider logos

Store provider logo files in this folder.

## Naming rules

- One logo file per provider.
- Filename must match `references/providers/providers.csv` `slug` value.
- Preferred extension: `.png`.
- Example: if slug is `alchemy`, `logoPath` value in CSV is `alchemy.png`.

## How it connects to data

- `references/providers/providers.csv` uses `logoPath` as filename only (no directory prefix).
- Visualization layer should prepend a fixed prefix: `references/providers/images/`.
- Set `logoPath` to `<slug>.png`.

## Recommended image format

- Square logo (1:1 aspect ratio), transparent background when possible.
- Recommended size: 512x512 px or 1024x1024 px.
