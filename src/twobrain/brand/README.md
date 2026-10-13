# 2brain identity

Open `index.html` directly in a browser. This editable guide, the reference board,
SVG artwork, and `style.json` are bundled with the CLI. Save a portable copy with:

```sh
2brain brand --export ./2brain-brand
```

The supplied chat image established the direction: a split brain / 2 silhouette,
lowercase geometric wordmark, warm white, deep ink, and soft sage. The attachment
preview did not expose its original file. `references/brand-board.svg` is an
editable reconstruction, not the original image. Mark geometry, lettering, and
hex values are interpreted from the preview. The app-icon variants are flat
vectors; the board's rendered shadows are not used in terminal interfaces.

`style.json` owns the color tokens and compact reusable prompt direction.
The CLI and TUI read the same tokens; the guide's catalog carries the same prompt.
The logo and wordmark SVGs contain actual paths and shapes, with no bitmap, font,
external dependency, or active content. Typography outside the artwork uses system
fonts. Use ink on sage and paper on ink; use forest for accent text on paper.

The guide and SVGs are ordinary editable files. After editing this kit, refresh
its derived catalog using Wstack's `wstack-brand` helper:

```sh
python3 <wstack-brand>/scripts/brand.py refresh --root <2brain-checkout> --brand-dir src/twobrain/brand --json
```

Keep the original board in `references/` if its file becomes available, and record
it in `asset-manifest.json` as a reference. Do not replace the reconstructed vectors
with an embedded bitmap or silently describe them as exact original artwork.
