"""Load and query manifest.json — the index of every logo/flag this repo carries.

Kept dependency-free (stdlib only) so it can be imported before Django's app
registry is ready (e.g. from a management command or a data-migration script).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

MANIFEST_PATH = Path(__file__).resolve().parent / "static" / "keel_finlogo" / "manifest.json"


@lru_cache(maxsize=1)
def load_manifest() -> dict:
    """Return the full manifest dict, keyed by ``"<category>/<slug>"``.

    Cached for process lifetime — the manifest only changes when this package
    is re-pinned, never at runtime in a consumer.
    """
    if not MANIFEST_PATH.is_file():
        return {}
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def get_entry(category: str, slug: str) -> dict | None:
    return load_manifest().get(f"{category}/{slug}")


def iter_entries(category: str | None = None):
    for key, entry in load_manifest().items():
        if category is None or entry.get("category") == category:
            yield entry
