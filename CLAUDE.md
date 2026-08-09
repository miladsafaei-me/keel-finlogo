# CLAUDE.md — keel-finlogo

Guidance for Claude Code in **keel-finlogo**, a reusable Keel **package** (not a
consumer app). Inherits the global rules in `~/.claude/CLAUDE.md` and the Keel
methodology in `~/www/keel-kit/methodology/`.

## What this package is

A **business-blind** static-asset repository: brand logos (forex broker, prop
firm, crypto exchange, binary-option broker, regulator) and country flags, plus
a thin `resolve_logo()`/`resolve_flag()` lookup layer. It knows nothing about
any consumer's data model — a logo is addressed by `(category, slug)` only,
never by a foreign key into someone else's `Platform`/`Broker` table.

## The boundary — what belongs here vs the consumer

**Here:** the image files themselves, `manifest.json` (source/license/size
metadata), the fetch tooling (`scripts/fetch_logo.py`, `scripts/fetch_flag.py`),
and the slug→static-URL resolver.

**Consumer:** which slug maps to which of *their* domain objects (e.g.
revenika's `Platform.slug == "exness"` → `resolve_logo("exness", "forex")`),
any DB-backed logo fields they still carry, and all UI/template wiring beyond
calling `resolve_logo`/`{% finlogo_url %}`.

## No models, no migrations, no new URL

This app exists purely for Django's staticfiles **finder** to discover
`static/keel_finlogo/...`. Do not add a model, a migration, a view, or a
`urls.py` — the moment this package needs a route or a DB table, that is a
different kind of package and the design has drifted. A consumer wires it in
by adding `"keel_finlogo"` to `INSTALLED_APPS` and nothing else; `collectstatic`
does the rest.

## Adding a logo/flag — always verify visually

`scripts/fetch_logo.py` is adapted from the `seo-logo` Keel skill
(`keel-kit/skills/seo-logo/`) — same scored waterfall, same background-removal
logic, extended to derive multiple sizes from one master and to update
`manifest.json`. The single most important discipline carried over from that
skill: **`Read` the written PNG before committing.** A confident "ok: true,
256x256, transparent" JSON result does not mean it is the *right* logo — it can
be a stale rebrand, an award badge, or a share-card banner. If the best
candidate is weak, `WebSearch` for an official image and re-run with
`--direct-url`.

## manifest.json is the source of truth for what exists

Never write an image file under `static/keel_finlogo/logos/` or `.../flags/`
without also updating the matching `manifest.json` entry (the fetch scripts do
this automatically) — `resolve_logo`/`resolve_flag` only look sizes up there,
they never `glob` the filesystem. A file on disk with no manifest entry is
invisible to every consumer.

## Category namespacing (do not break)

Logo slugs are namespaced by category (`forex/exness` vs a hypothetical
`prop/exness`) specifically so two unrelated brands sharing a name never
collide. Never flatten `logos/<category>/<slug>/` into a bare `logos/<slug>/`.

## Release

Same as every Keel package: bump `pyproject.toml` `version`, then
`keel-kit/scripts/keel-release.sh X.Y.Z`. `version-guard` CI enforces the tag ==
`pyproject.toml` version and that `src/` never changes without a bump — see
`keel-kit/methodology/versioning-and-release.md`.

## Self-check before shipping

- `python3 -m py_compile` the whole `src/keel_finlogo` tree and `scripts/`.
- Every new/changed manifest entry has a real file on disk at every listed size.
- No banner comments; English only in code/identifiers/docs (this file
  included) — see the global rule.
