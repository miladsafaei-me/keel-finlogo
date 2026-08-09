from django import template

from ..resolve import resolve_flag, resolve_logo

register = template.Library()


@register.simple_tag
def finlogo_url(slug, category, variant="icon", size=256):
    """{% finlogo_url "exness" "forex" variant="icon" size=256 %}"""
    return resolve_logo(slug, category, variant=variant, size=int(size)) or ""


@register.simple_tag
def finlogo_svg_url(slug, category, variant="icon"):
    """{% finlogo_svg_url "exness" "forex" %} — empty string when no vector exists."""
    return resolve_logo(slug, category, variant=variant, prefer_svg=True) or ""


@register.simple_tag
def finflag_url(iso2, width=80):
    """{% finflag_url "us" width=80 %}"""
    return resolve_flag(iso2, width=int(width)) or ""
