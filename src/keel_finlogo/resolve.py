"""Turn a (category, slug) or ISO-2 country code into a static URL.

Every lookup consults ``manifest.json`` (via :mod:`keel_finlogo.manifest`) so a
caller never has to guess whether a given size actually exists — it asks for a
size and gets back the closest one this repo actually shipped.
"""

from __future__ import annotations

from .manifest import get_entry

FLAG_WIDTHS = (40, 80, 160, 320, 640)


def _nearest_size(available: list[int], wanted: int) -> int | None:
    if not available:
        return None
    at_least = sorted(s for s in available if s >= wanted)
    return at_least[0] if at_least else max(available)


def has_logo(slug: str, category: str) -> bool:
    return get_entry(category, slug) is not None


def resolve_logo(
    slug: str,
    category: str,
    *,
    variant: str = "icon",
    size: int = 256,
    prefer_svg: bool = False,
) -> str | None:
    """Return a ``{% static %}`` URL for the closest available size, or ``None``.

    ``category`` is one of ``forex|prop|crypto|binary|regulator``. ``variant``
    is ``icon`` (square mark) or ``wordmark`` (wide logo). Set ``prefer_svg=True``
    to get the vector file when this brand's source was a vector.
    """
    from django.templatetags.static import static

    entry = get_entry(category, slug)
    if not entry:
        return None
    variant_data = entry.get("variants", {}).get(variant)
    if not variant_data:
        return None

    if prefer_svg and variant_data.get("svg"):
        return static(f"keel_finlogo/logos/{category}/{slug}/{variant}.svg")

    chosen = _nearest_size(variant_data.get("sizes", []), size)
    if chosen is None:
        return None
    return static(f"keel_finlogo/logos/{category}/{slug}/{variant}-{chosen}.png")


def resolve_logo_webp(
    slug: str, category: str, *, variant: str = "icon", size: int = 256
) -> str | None:
    from django.templatetags.static import static

    entry = get_entry(category, slug)
    if not entry:
        return None
    variant_data = entry.get("variants", {}).get(variant)
    if not variant_data or not variant_data.get("webp"):
        return None
    chosen = _nearest_size(variant_data.get("sizes", []), size)
    if chosen is None:
        return None
    return static(f"keel_finlogo/logos/{category}/{slug}/{variant}-{chosen}.webp")


def resolve_flag(iso2: str, *, width: int = 80) -> str | None:
    """Return a ``{% static %}`` URL for a country flag WebP at the closest width."""
    from django.templatetags.static import static

    iso2 = iso2.strip().lower()
    if len(iso2) != 2:
        return None
    chosen = _nearest_size(list(FLAG_WIDTHS), width)
    return static(f"keel_finlogo/flags/{iso2}/w{chosen}.webp")


def resolve_flag_svg(iso2: str) -> str | None:
    from django.templatetags.static import static

    iso2 = iso2.strip().lower()
    if len(iso2) != 2:
        return None
    return static(f"keel_finlogo/flags/{iso2}/flag.svg")
