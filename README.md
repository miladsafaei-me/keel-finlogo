# keel-finlogo

A shared, business-blind repository of high-quality brand logos and country
flags for every Keel consumer: forex brokers, prop firms, crypto exchanges,
binary-option brokers, regulators, and flags — one place to fetch a brand mark
once and reuse it everywhere, instead of every project re-implementing its own
logo crawler.

## What it ships

- `src/keel_finlogo/static/keel_finlogo/logos/<category>/<slug>/` — transparent
  PNG + WebP at several sizes (`icon-{64,128,256,512}` and
  `wordmark-{256,512}`), plus `icon.svg`/`wordmark.svg` when the source was a
  vector. `<category>` is one of `forex`, `prop`, `crypto`, `binary`,
  `regulator`, `coin`, `platform`. `coin` covers a cryptocurrency's own symbol
  (`btc`, `eth`, `xrp`, `sol`, `bnb`, `doge`, `zec`, `sui`, `hype`, …) —
  distinct from `crypto`, which is exchange brands (Binance, Coinbase, …).
  `platform` covers trading platforms, terminals, chat apps, browsers and app
  stores (`metatrader-4`/`-5`, `tradingview`, `ctrader`, `ninjatrader`,
  `telegram`, `dxtrade`, `tradelocker`, `match-trader`, `rithmic`, `tradovate`,
  `bookmap`, `whatsapp`, `discord`, `chrome`, `firefox`, `edge`, `app-store`,
  `google-play`, …) — anything a signal or a broker gets *delivered through*,
  never a broker/exchange/prop-firm itself.
- **A mono brand ships a third variant, `icon-light`.** Most brand marks are
  already full colour and read fine on both a light and a dark ground (their
  colour never coincides with either canvas extreme). A handful are a single
  ink whose only published colour collides with one of our two standard
  grounds — TradingView (white-only), XRP and Hyperliquid (each a single dark
  or light glyph), TradeLocker (a solid black mark) — so each ships **two**
  square-mark variants: `icon` is the brand's dark ink, sized for a light
  ground, and `icon-light` is its light ink (the same official mark, or the
  same path data recoloured, never a different design), sized for a dark
  ground. `manifest.json` tags every variant `"ink": "color"` or `"ink":
  "mono"` so a caller can tell which grounds a mark actually needs versus
  which one is merely swapped by convention.
- **Each landing coin also ships `coin3d-{512,1024}.png`** (`btc`, `eth`, `xrp`,
  `sol`, `bnb`, `doge`, `zec`, `sui`, `hype`): the coin's own mark on a minted 3D coin,
  rendered on the landing-cover stage's camera, recorded as the `coin3d` variant with
  `"face": "svg"` or `"face": "png"` (see "Branded 3D coins" below).
- `src/keel_finlogo/static/keel_finlogo/flags/<iso2>/` — `w{40,80,160,320,640}.webp`
  + `flag.svg` for every ISO-3166-1 alpha-2 country code, sourced from
  flagcdn.com.
- `manifest.json` — the index of every brand/flag this repo carries: category,
  slug, brand name, source domain, fetch date, license note, and which sizes
  actually exist. Consulted by `resolve_logo()`/`resolve_flag()` so a caller
  never has to guess.

## Using it in a consumer project

1. Pin it in `requirements.txt`: `keel-finlogo @ git+https://github.com/miladsafaei-me/keel-finlogo@vX.Y.Z`
2. Add `"keel_finlogo"` to `INSTALLED_APPS` — that's the only wiring needed;
   Django's staticfiles finder picks up everything under
   `static/keel_finlogo/...` on the next `collectstatic`. No new URL, no new
   route — the asset rides the project's existing static-file pipeline.
3. Resolve a logo:

   ```python
   from keel_finlogo import resolve_logo, resolve_flag

   resolve_logo("exness", "forex", variant="icon", size=256)   # -> static URL or None
   resolve_flag("gb", width=80)
   ```

   Or in a template: `{% load keel_finlogo %}{% finlogo_url "exness" "forex" size=256 %}`.

## Adding a new logo or flag

Requires the `fetch` extra: `pip install -e '.[fetch]'` from the repo root.

```bash
python3 scripts/fetch_logo.py "Exness" --category forex --domain exness.com
python3 scripts/fetch_logo.py "Exness" --category forex --domain exness.com --variant wordmark
python3 scripts/fetch_flag.py            # every country (idempotent, re-run to refresh)

# A mono brand: fetch its dark ink, then its light ink, from two direct URLs
# (or two local files — see below) found by eye, one per official ink.
python3 scripts/fetch_logo.py "TradeLocker" --category platform --domain tradelocker.com \
  --direct-url https://tradelocker.com/wp-content/uploads/2023/04/Icon-3.png --ink mono
python3 scripts/fetch_logo.py "TradeLocker" --category platform --domain tradelocker.com \
  --direct-url /path/to/tradelocker-icon-light.png --variant icon-light --ink mono
```

`fetch_logo.py` walks a scored source waterfall (Brandfetch API when
`BRANDFETCH_API_KEY` is set, Wikipedia, logo.dev, unavatar.io, the brand's own
site, Simple Icons, Google favicon) and picks the best-scoring candidate.
**`--direct-url` never competes in that scoring** — an operator who found the
official file by eye (a press kit, a Wikimedia asset page, the brand's own
site source) gets it used exactly as passed, normalised into the usual sizes;
if the waterfall would have preferred a different candidate, that is logged as
a note, never substituted (closed 2026-09-13: a transparent SVG always
outscored a correct raster, so the waterfall kept overruling explicit
`--direct-url` picks with the wrong logo — a rainbow ETH diamond, a cropped
"BNB CHAIN" banner, FxPro's mark for cTrader, a mismatched MetaTrader 5 icon).
`--direct-url` also accepts a local file path (or `file://` path) instead of a
URL — the way to hand the pipeline a derived asset (a mono mark's ink inverted
from the same official path data) that never had a URL of its own.

`--variant icon-light --ink mono` is the second half of a mono pair (see
"What it ships" above); pass `--ink color` (the default) for an ordinary
full-colour mark. **Always visually inspect the written PNG on both a
near-black and a near-white ground** before committing — a script can confirm
"transparent, 512×512" but not "this is actually the current, correct logo,
and it reads on both grounds." See `keel-kit/skills/seo-logo/SKILL.md` for the
full verification checklist this tool is adapted from.

## Branded 3D coins

`scripts/build_coin3d.py` renders each landing coin's `coin3d` variant through the
keel-visuals object factory (`scripts/build_factory_objects.py coin`), which owns the
geometry, the materials and the camera; this repo decides only which mark goes on which
coin, and keeps the result beside the brand it belongs to.

```bash
python3 scripts/build_coin3d.py --container signalbots-web \
  --factory-script /path/to/keel-visuals/scripts/build_factory_objects.py [--coins btc doge]
```

- **A coin whose manifest `icon` has an SVG is struck from `icon.svg`.** The mark's
  shapes stand up out of the face in its own colours, and a mark that is a disc of its
  own has its knockouts filled with white enamel, the way the brand prints them:
  Bitcoin's B is white on the orange disc, not the coin's metal showing through.
- **A coin whose `icon` has no SVG is set from its largest `icon-<size>.png`** as a
  clear-coated decal inset in the face, cut to a circle when the mark is a disc.
- **`METAL_OVERRIDE`** in the script pins the rim metal where `auto` was reviewed and
  read wrong: a near-black mark (`xrp`, `hype`) on a gunmetal coin all but vanishes, so
  those two are silver.
- **`FACE_OVERRIDE`** in the script pins a specific raster face for a slug whose SVG the
  extruder cannot strike faithfully. Dogecoin is the one today: `icon.svg` is Dogecoin
  Core's official vector (`share/pixmaps/dogecoin256.svg` in github.com/dogecoin/dogecoin,
  Expat licence — the same upright-D layout as dogecoin.com's own mark), but its
  `clipPath` plus translucent overlay layer strikes through `--face-svg` as a near-solid
  black disc (verified 2026-09-13). `coin3d-face.png`, a 2048 px rasterization of that
  same vector kept beside `icon.svg`, is struck with `--face-png` instead and renders the
  full mark correctly. The large translucent white "D" across the Shiba's face is part of
  the official mark (dogecoin.com, the Core app icon and the Core vector all draw it), so
  the coin keeps it rather than showing an edited trademark.
- **Read every render on a near-white and a near-black ground** before committing, as
  with any other mark.

## Release

Same as every other Keel package — see
`keel-kit/methodology/versioning-and-release.md`. Bump `pyproject.toml`
`version`, then `keel-kit/scripts/keel-release.sh X.Y.Z`. `version-guard` CI
enforces that the tag matches `pyproject` and that `src/` never changes
without a bump.
