#!/usr/bin/env python3
"""fetch_logo.py — fetch, normalize, and register a brand logo in this repo.

Adapted from the `seo-logo` Keel skill (keel-kit/skills/seo-logo/fetch_logo.py).
The difference: that skill writes ONE size into a host project's static folder.
This script is the maintenance tool for keel-finlogo ITSELF — it derives every
configured size from one clean master download, writes them under
`src/keel_finlogo/static/keel_finlogo/logos/<category>/<slug>/`, and updates
`manifest.json` so consumers can discover what's available.

Install the extra once: `pip install -e '.[fetch]'` from the repo root.

Typical use::

    python3 scripts/fetch_logo.py "Exness" --category forex --domain exness.com
    python3 scripts/fetch_logo.py binance --category crypto --domain binance.com --variant wordmark
    python3 scripts/fetch_logo.py "Acme Prop" --category prop --direct-url https://.../acme.svg

Run with --help for the full flag list.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from shutil import which
from urllib.parse import quote, urljoin

import requests
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parent.parent
STATIC_ROOT = REPO_ROOT / "src" / "keel_finlogo" / "static" / "keel_finlogo"
MANIFEST_PATH = STATIC_ROOT / "manifest.json"

CATEGORIES = ("forex", "prop", "crypto", "binary", "regulator")

# Master max-edge each variant is fetched/cleaned at; every configured size is
# then DERIVED (resize, no re-fetch) from that one clean master.
VARIANT_MASTER_EDGE = {"icon": 1024, "wordmark": 1024}
VARIANT_SIZES = {"icon": (64, 128, 256, 512), "wordmark": (256, 512)}

BROWSER_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
IMAGE_ACCEPT = "image/svg+xml,image/webp,image/png,image/*,*/*;q=0.8"

MIN_EDGE = 48


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


# Slug / domain

def slugify(name: str) -> str:
    s = name.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def normalize_domain(raw: str) -> str:
    raw = raw.strip()
    for prefix in ("https://", "http://"):
        if raw.startswith(prefix):
            raw = raw[len(prefix):]
    if raw.startswith("www."):
        raw = raw[4:]
    return raw.split("/", 1)[0]


# HTTP

def http_get(url: str, *, timeout: int = 20, as_text: bool = False):
    headers = {"User-Agent": BROWSER_UA, "Accept": IMAGE_ACCEPT}
    try:
        resp = requests.get(url, timeout=timeout, headers=headers, allow_redirects=True)
        resp.raise_for_status()
        if as_text:
            return resp.text
        ctype = resp.headers.get("Content-Type", "").lower()
        if "text/html" in ctype or "application/json" in ctype:
            log(f"      · skipped non-image ({ctype.split(';')[0]}) {url[:80]}")
            return None
        return resp.content
    except Exception as exc:
        log(f"      · GET failed {url[:90]}: {exc}")
        return None


# Image inspection

def looks_like_svg(data: bytes) -> bool:
    head = data[:600].lstrip()
    return head.startswith(b"<svg") or (head.startswith(b"<?xml") and b"<svg" in data[:2000])


def raster_dims(data: bytes):
    try:
        with Image.open(io.BytesIO(data)) as im:
            return im.size
    except Exception:
        return None


def raster_has_transparency(data: bytes) -> bool:
    try:
        with Image.open(io.BytesIO(data)) as im:
            if im.mode in ("RGBA", "LA"):
                alpha = im.convert("RGBA").getchannel("A")
                return alpha.getextrema()[0] < 250
            if im.mode == "P" and "transparency" in im.info:
                return True
    except Exception:
        return False
    return False


def _corner_uniform(im: Image.Image):
    rgb = im.convert("RGB")
    w, h = rgb.size
    pts = [(2, 2), (w - 3, 2), (2, h - 3), (w - 3, h - 3)]
    cols = [rgb.getpixel(p) for p in pts]
    avg = tuple(sum(c[i] for c in cols) // len(cols) for i in range(3))
    spread = max(sum((c[i] - avg[i]) ** 2 for i in range(3)) ** 0.5 for c in cols)
    return spread < 24, avg


def solid_removable_bg(data: bytes) -> bool:
    try:
        with Image.open(io.BytesIO(data)) as im:
            return _corner_uniform(im)[0]
    except Exception:
        return False


class Candidate:
    def __init__(self, data: bytes, source: str, *, variant: str = ""):
        self.data = data
        self.source = source
        self.variant = variant  # brandfetch type hint: logo/symbol/icon
        self.is_svg = looks_like_svg(data)
        self.dims = None if self.is_svg else raster_dims(data)
        self.transparent = True if self.is_svg else raster_has_transparency(data)
        self.removable_bg = (
            False if (self.is_svg or self.transparent) else solid_removable_bg(data)
        )

    @property
    def min_edge(self) -> int:
        if self.is_svg:
            return 4096
        return min(self.dims) if self.dims else 0

    @property
    def valid(self) -> bool:
        if self.is_svg:
            return len(self.data) > 80
        return self.dims is not None and self.min_edge >= MIN_EDGE

    def score(self, want_variant: str) -> float:
        fits = wrong = False
        if want_variant and self.variant:
            fits = (want_variant == "icon" and self.variant in ("icon", "symbol")) or (
                want_variant == "wordmark" and self.variant == "logo")
            wrong = (want_variant == "icon" and self.variant == "logo") or (
                want_variant == "wordmark" and self.variant in ("icon", "symbol"))

        s = 0.0
        if self.is_svg:
            s += 200 if wrong else 1000
        s += 600 if self.transparent else (450 if self.removable_bg else 0)

        if not self.is_svg:
            s += min(self.min_edge, 512) * 0.25
            if self.min_edge < 128:
                s -= (128 - self.min_edge) * 1.5

        aspect = (max(self.dims) / min(self.dims)) if (self.dims and min(self.dims)) else 1.0
        if want_variant == "icon":
            if fits:
                s += 250
            elif wrong:
                s -= 150
            if not self.is_svg:
                s += 150 if aspect <= 1.4 else (-130 if aspect >= 2.2 else 0)
        elif want_variant == "wordmark":
            if fits:
                s += 250
            if not self.is_svg and aspect >= 1.8:
                s += 120

        priors = {
            "direct-url": 90, "brandfetch": 70, "wikipedia": 55, "logo.dev": 45,
            "unavatar": 30, "getlogo.dev": 25, "website": 20, "simpleicons": 15,
            "google-favicon": -50,
        }
        s += priors.get(self.source, 0)
        return s

    def describe(self) -> str:
        kind = "svg" if self.is_svg else (f"{self.dims[0]}x{self.dims[1]}" if self.dims else "?")
        tr = "transparent" if self.transparent else ("opaque/solid-bg" if self.removable_bg else "opaque")
        v = f" {self.variant}" if self.variant else ""
        return f"{self.source}{v}: {kind} {tr}"


# Sources

def src_brandfetch(domain: str, key: str):
    if not (domain and key):
        return
    url = f"https://api.brandfetch.io/v2/brands/{domain}"
    try:
        resp = requests.get(
            url, headers={"Authorization": f"Bearer {key}", "User-Agent": BROWSER_UA}, timeout=20,
        )
        if resp.status_code == 404:
            log("      · brandfetch: brand not found")
            return
        resp.raise_for_status()
        payload = resp.json()
    except Exception as exc:
        log(f"      · brandfetch API error: {exc}")
        return
    for logo in payload.get("logos", []):
        ltype = logo.get("type", "")
        for fmt in logo.get("formats", []):
            src = fmt.get("src")
            if src:
                yield src, ltype


def src_wikipedia(brand: str):
    api = (
        "https://en.wikipedia.org/w/api.php?action=query&format=json"
        "&generator=search&gsrlimit=1&gsrsearch=" + quote(brand)
        + "&prop=pageimages&piprop=original&pilicense=any"
    )
    try:
        data = requests.get(api, headers={"User-Agent": BROWSER_UA}, timeout=20).json()
        pages = data.get("query", {}).get("pages", {})
        for page in pages.values():
            original = page.get("original", {}).get("source")
            if original:
                yield original, ""
    except Exception as exc:
        log(f"      · wikipedia error: {exc}")


def src_logodev(domain: str, token: str):
    if domain and token:
        yield f"https://img.logo.dev/{domain}?token={token}&size=512&format=png&retina=true", ""


def src_unavatar(domain: str):
    if domain:
        yield f"https://unavatar.io/{domain}?fallback=false", ""


def src_simpleicons(brand: str, slug: str):
    seen = set()
    for cand in (re.sub(r"[^a-z0-9]", "", brand.lower()), slug.replace("-", ""), slug):
        if cand and cand not in seen:
            seen.add(cand)
            yield f"https://cdn.simpleicons.org/{cand}", "symbol"


def src_getlogodev(domain: str, token: str):
    if domain and token:
        yield f"https://img.getlogo.dev/logos/{domain}?token={token}&format=png&size=512", ""


def src_google_favicon(domain: str):
    if domain:
        yield f"https://www.google.com/s2/favicons?domain={domain}&sz=256", "icon"


def src_website(domain: str):
    if not domain:
        return
    base = f"https://{domain}"
    yield f"{base}/apple-touch-icon.png", "icon"
    yield f"{base}/apple-touch-icon-precomposed.png", "icon"

    html = http_get(base, as_text=True)
    if not html:
        return
    head = html[:120_000]

    man_m = re.search(r'<link[^>]+rel=["\']manifest["\'][^>]*href=["\']([^"\']+)["\']', head, re.I)
    if man_m:
        man_url = urljoin(base, man_m.group(1))
        try:
            manifest = requests.get(man_url, headers={"User-Agent": BROWSER_UA}, timeout=15).json()

            def icon_px(ic):
                m = re.match(r"(\d+)", ic.get("sizes", "0") or "0")
                return int(m.group(1)) if m else 0

            for ic in sorted(manifest.get("icons", []), key=icon_px, reverse=True):
                if ic.get("src"):
                    yield urljoin(man_url, ic["src"]), "icon"
        except Exception:
            pass

    og_m = re.search(
        r'<meta[^>]+property=["\']og:image["\'][^>]*content=["\']([^"\']+)["\']', head, re.I
    ) or re.search(
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]*property=["\']og:image["\']', head, re.I
    )
    if og_m:
        yield urljoin(base, og_m.group(1)), "logo"

    sized = []
    for tag in re.findall(r"<link[^>]+rel=[\"'][^\"']*icon[^\"']*[\"'][^>]*>", head, re.I):
        href = re.search(r'href=["\']([^"\']+)["\']', tag)
        size = re.search(r'sizes=["\'](\d+)x\d+["\']', tag)
        if href:
            sized.append((int(size.group(1)) if size else 0, urljoin(base, href.group(1))))
    for _, icon_url in sorted(sized, key=lambda x: x[0], reverse=True):
        yield icon_url, "icon"


def build_source_plan(brand, slug, domain, keys, direct_url):
    plan = []
    if direct_url:
        plan.append(("direct-url", iter([(direct_url, "")])))
    plan.append(("brandfetch", src_brandfetch(domain, keys.get("BRANDFETCH_API_KEY", ""))))
    plan.append(("wikipedia", src_wikipedia(brand)))
    plan.append(("logo.dev", src_logodev(domain, keys.get("LOGO_DEV_ACCESS_TOKEN", ""))))
    plan.append(("unavatar", src_unavatar(domain)))
    plan.append(("simpleicons", src_simpleicons(brand, slug)))
    plan.append(("website", src_website(domain)))
    plan.append(("getlogo.dev", src_getlogodev(domain, keys.get("GETLOGO_DEV_TOKEN", ""))))
    plan.append(("google-favicon", src_google_favicon(domain)))
    return plan


def collect_best(plan, want_variant, *, max_per_source=6):
    best = None
    excellent = False
    for source_name, gen in plan:
        if excellent:
            break
        log(f"  → {source_name}")
        count = 0
        for url, variant in gen:
            if count >= max_per_source:
                break
            count += 1
            data = http_get(url)
            if not data or len(data) < 120:
                continue
            cand = Candidate(data, source_name, variant=variant)
            if not cand.valid:
                continue
            log(f"      ✓ {cand.describe()}")
            if best is None or cand.score(want_variant) > best.score(want_variant):
                best = cand
            wrong = {"icon": "logo", "wordmark": "symbol"}.get(want_variant)
            if cand.is_svg and cand.transparent and cand.variant != wrong:
                excellent = True
                break
    return best


# SVG rasterization + background removal + trim/resize (unchanged from seo-logo)

def _run(cmd, *, env=None, timeout=120) -> bool:
    try:
        proc = subprocess.run(cmd, env=env, timeout=timeout, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        if proc.returncode != 0:
            log(f"      · cmd failed ({cmd[0]}): {proc.stderr.decode('utf-8', 'replace')[:160]}")
        return proc.returncode == 0
    except Exception as exc:
        log(f"      · cmd error ({cmd[0]}): {exc}")
        return False


def rasterize_svg(svg_bytes: bytes, width: int):
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "in.svg"
        out = Path(td) / "out.png"
        src.write_bytes(svg_bytes)
        if which("rsvg-convert"):
            if _run(["rsvg-convert", "-w", str(width), "-o", str(out), str(src)]) and out.exists():
                return out.read_bytes()
        magick = which("magick") or which("convert")
        if magick:
            if _run([magick, "-background", "none", "-density", "384", str(src), "-resize", f"{width}x", str(out)]) and out.exists():
                return out.read_bytes()
    return None


def remove_bg_magick(data: bytes):
    magick = which("magick") or which("convert")
    if not magick:
        return None
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "in.png"
        out = Path(td) / "out.png"
        Image.open(io.BytesIO(data)).convert("RGBA").save(src)
        with Image.open(src) as im:
            w, h = im.size
        cmd = [magick, str(src), "-alpha", "set", "-fuzz", "14%"]
        for x, y in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
            cmd += ["-fill", "none", "-draw", f"alpha {x},{y} floodfill"]
        cmd.append(str(out))
        if _run(cmd) and out.exists():
            return out.read_bytes()
    return None


def ensure_transparent(data: bytes, mode: str):
    if raster_has_transparency(data):
        return data, "already transparent"
    if mode == "none":
        return data, "opaque (bg removal skipped)"
    result = remove_bg_magick(data)
    if result and raster_has_transparency(result):
        return result, "bg removed via magick"
    return data, "opaque (bg removal failed — no solid-color corners to flood-fill)"


def trim(data: bytes) -> bytes:
    im = Image.open(io.BytesIO(data)).convert("RGBA")
    bbox = im.getchannel("A").getbbox()
    if bbox:
        im = im.crop(bbox)
    buf = io.BytesIO()
    im.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def resize_to(png_bytes: bytes, max_edge: int) -> bytes:
    im = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    w, h = im.size
    if max(w, h) != max_edge:
        scale = max_edge / max(w, h)
        im = im.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def write_webp(png_bytes: bytes, path: Path) -> None:
    im = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    im.save(path, "WEBP", quality=90, method=6, lossless=False)


# Manifest bookkeeping

def load_manifest() -> dict:
    if MANIFEST_PATH.is_file():
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {}


def save_manifest(data: dict) -> None:
    MANIFEST_PATH.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def update_manifest(*, category, slug, brand_name, domain, source, license_note, variant, sizes, has_svg):
    data = load_manifest()
    key = f"{category}/{slug}"
    entry = data.get(key) or {
        "category": category, "slug": slug, "brand_name": brand_name,
        "domain": domain, "variants": {},
    }
    entry["brand_name"] = brand_name
    entry["domain"] = domain
    entry["source"] = source
    entry["license_note"] = license_note
    entry["fetched_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    entry["variants"][variant] = {"sizes": sorted(sizes), "svg": has_svg, "webp": True}
    data[key] = entry
    save_manifest(data)


# Main

def main() -> int:
    ap = argparse.ArgumentParser(description="Fetch + normalize a brand logo into keel-finlogo.")
    ap.add_argument("brand", help="Brand name, slug, or domain (e.g. 'Exness', binance, ftmo.com).")
    ap.add_argument("--category", required=True, choices=CATEGORIES)
    ap.add_argument("--domain", help="Official domain override (recommended).")
    ap.add_argument("--slug", help="Output slug (default: slugified brand).")
    ap.add_argument("--direct-url", help="Explicit image URL to try first.")
    ap.add_argument("--variant", choices=["icon", "wordmark"], default="icon")
    ap.add_argument("--bg", choices=["auto", "magick", "none"], default="auto")
    ap.add_argument("--no-webp", action="store_true")
    ap.add_argument("--no-svg", action="store_true")
    ap.add_argument(
        "--license-note", default="official brand mark, fetched via automated waterfall",
    )
    args = ap.parse_args()

    keys = {
        "BRANDFETCH_API_KEY": os.environ.get("BRANDFETCH_API_KEY", ""),
        "LOGO_DEV_ACCESS_TOKEN": os.environ.get("LOGO_DEV_ACCESS_TOKEN", ""),
        "GETLOGO_DEV_TOKEN": os.environ.get("GETLOGO_DEV_TOKEN", ""),
    }

    raw = args.brand.strip()
    is_domain_input = "." in raw and " " not in raw
    slug = args.slug or slugify(raw if not is_domain_input else raw.split(".")[0])

    if args.domain:
        domain = normalize_domain(args.domain)
        brand = raw if not is_domain_input else raw.split(".")[0]
    elif is_domain_input:
        domain = normalize_domain(raw)
        brand = domain.split(".")[0]
    else:
        domain = ""
        brand = raw

    brand_for_search = brand.replace("-", " ").title()

    log(f"Brand: {brand_for_search!r}  slug: {slug!r}  domain: {domain or '(unknown)'}  "
        f"category: {args.category}  variant: {args.variant}")
    active = [k.split("_")[0].title() for k, v in keys.items() if v]
    log(f"Keyed sources active: {', '.join(active) or 'none (free sources only)'}")
    if not domain:
        log("  ! No domain — brandfetch/logo.dev/unavatar/website/favicon are skipped. Pass --domain.")

    plan = build_source_plan(brand_for_search, slug, domain, keys, args.direct_url)
    best = collect_best(plan, args.variant)
    if best is None:
        log("\n✗ No usable logo found from any source.")
        log("  Next: WebSearch for an official PNG/SVG (press kit, Wikipedia) and re-run with --direct-url.")
        print(json.dumps({"ok": False, "slug": slug, "domain": domain}))
        return 2

    log(f"\n★ Winner — {best.describe()}  (score {best.score(args.variant):.0f})")

    out_dir = STATIC_ROOT / "logos" / args.category / slug
    out_dir.mkdir(parents=True, exist_ok=True)

    svg_path = None
    if best.is_svg:
        if not args.no_svg:
            svg_path = out_dir / f"{args.variant}.svg"
            svg_path.write_bytes(best.data)
        raster = rasterize_svg(best.data, VARIANT_MASTER_EDGE[args.variant])
        if raster is None:
            log("  ! Could not rasterize the SVG (no rsvg-convert/magick succeeded). Kept the .svg only.")
            print(json.dumps({"ok": bool(svg_path), "slug": slug, "svg": str(svg_path) if svg_path else None}))
            return 0 if svg_path else 3
        # A vector CAN paint its own opaque background rect (common in square
        # "avatar" exports) — rasterizing with a transparent canvas doesn't
        # help if the SVG itself draws over it. Same removal pass as a raster.
        if not raster_has_transparency(raster):
            raster, note = ensure_transparent(raster, args.bg)
            log(f"  · svg rasterized opaque — {note}")
        master = trim(raster)
    else:
        png_bytes, note = ensure_transparent(best.data, args.bg)
        log(f"  · {note}")
        master = trim(png_bytes)

    written = []
    sizes_written = []
    for edge in VARIANT_SIZES[args.variant]:
        sized_png = resize_to(master, edge)
        png_path = out_dir / f"{args.variant}-{edge}.png"
        png_path.write_bytes(sized_png)
        written.append(png_path)
        sizes_written.append(edge)
        if not args.no_webp:
            webp_path = out_dir / f"{args.variant}-{edge}.webp"
            write_webp(sized_png, webp_path)
            written.append(webp_path)

    update_manifest(
        category=args.category, slug=slug, brand_name=brand_for_search, domain=domain,
        source=best.source, license_note=args.license_note, variant=args.variant,
        sizes=sizes_written, has_svg=bool(svg_path),
    )

    log("\n✓ Done:")
    for p in written:
        log(f"  {p.relative_to(REPO_ROOT)}")
    if svg_path:
        log(f"  {svg_path.relative_to(REPO_ROOT)}")
    log(f"  manifest.json updated: {args.category}/{slug}.{args.variant}")

    print(json.dumps({
        "ok": True, "slug": slug, "category": args.category, "variant": args.variant,
        "source": best.source, "sizes": sizes_written, "svg": bool(svg_path),
        "master_preview": str(out_dir / f"{args.variant}-512.png"),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
