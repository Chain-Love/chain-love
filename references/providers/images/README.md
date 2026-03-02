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

- Square logo (1:1 aspect ratio), **transparent background required**.
- Recommended size: between 160x160 to 500x500 pixels.
- **Do not submit logos with a solid background** (white, black, gray, etc.) — these look broken on dark/light themes.
- Exception: if the logo itself includes a background as an intentional part of its design (e.g. a black rounded square that is part of the brand identity), it is acceptable to keep it. This should be the rare case, not the default.

Use:
![correct3xpl](https://3xpl.com/assets/images/brand-kit/logomarks/dark.svg)

No use:
![incorrect3xpl](https://raw.githubusercontent.com/harunsulaiman/chain-love/18bb5f5100fea6b2c9431cc84d21d67bac5c5259/references/providers/images/3xpl.png)

## Finding the logo

- Check the provider's official **media kit** first — most projects publish one on their website or GitHub.
- Common locations: `/brand`, `/press`, `/media` pages, or the project's GitHub org.

## Removing backgrounds

If you only have a logo with a background, use one of these tools to remove it before submitting:

- [remove.bg](https://www.remove.bg) — works well for most logos
- [Adobe Express Background Remover](https://www.adobe.com/express/feature/image/remove-background) — free, no account needed
- [Erase.bg](https://www.erase.bg) — good for logos with flat colors
