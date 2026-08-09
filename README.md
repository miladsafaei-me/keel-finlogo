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
  `regulator`.
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
```

`fetch_logo.py` walks a scored source waterfall (Brandfetch API when
`BRANDFETCH_API_KEY` is set, Wikipedia, logo.dev, unavatar.io, the brand's own
site, Simple Icons, Google favicon — plus `--direct-url` for a manually found
image), derives every configured size from one clean master, and updates
`manifest.json`. **Always visually inspect the written PNG** before committing
— a script can confirm "transparent, 512×512" but not "this is actually the
current, correct logo." See `keel-kit/skills/seo-logo/SKILL.md` for the full
verification checklist this tool is adapted from.

## Release

Same as every other Keel package — see
`keel-kit/methodology/versioning-and-release.md`. Bump `pyproject.toml`
`version`, then `keel-kit/scripts/keel-release.sh X.Y.Z`. `version-guard` CI
enforces that the tag matches `pyproject` and that `src/` never changes
without a bump.
