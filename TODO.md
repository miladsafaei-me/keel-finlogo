# TODO

This file is the single source of truth for pending, follow-up, and deferred work on this project. See CLAUDE.md for the tracking rule.

Guidelines:
- Add a task here as soon as it's identified — with priority, prerequisites/dependencies, and enough context to pick it up cold.
- Group by priority: P0 (urgent / blocking / production risk), P1 (next up), P2 (backlog / nice-to-have).
- Note real dependencies explicitly ("Blocked by: ...", "Requires: ...").
- Delete a task from this file the moment it's done. This file only ever holds what's left.

Open work, most important first. Remove an item the moment it is done.

### `--direct-url` should short-circuit the logo waterfall
- **Priority:** medium
- **Context:** Found while adding the coin and platform categories (2026-09-13). `collect_best()` in `scripts/fetch_logo.py` scores a `--direct-url` candidate against the rest of the waterfall, and any transparent SVG candidate outscores a raster direct URL, even a wrong one. It picked a rainbow ETH diamond, a cropped "BNB CHAIN" banner, FxPro's logo for cTrader, and a mismatched MetaTrader 5 icon over the official files that were passed explicitly; each had to be caught by eye.
- **Done when:** an explicit `--direct-url` is used as-is (normalised, sized, manifest written) without competing on score, and a candidate the waterfall would have preferred is only reported, not chosen.
