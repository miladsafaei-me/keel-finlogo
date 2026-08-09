#!/usr/bin/env python3
"""fetch_flag.py — download every country flag from flagcdn.com into this repo.

Adapted from binaryoptiontrading/scripts/download_flagcdn_flags.py: that script
grabs one w20 WebP per country into a consumer's own static/. This one grabs
the full FLAG_WIDTHS ladder (see keel_finlogo.resolve.FLAG_WIDTHS) plus the SVG
master, writes them under
`src/keel_finlogo/static/keel_finlogo/flags/<iso2>/w{width}.webp` (+`flag.svg`),
and registers each in manifest.json under the `flag/<iso2>` key.

flagcdn.com is the single source for flags — no waterfall needed, it already
covers every ISO-3166-1 alpha-2 code at every useful resolution.

Usage::

    python3 scripts/fetch_flag.py               # every country
    python3 scripts/fetch_flag.py us gb ae       # just these codes
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
STATIC_ROOT = REPO_ROOT / "src" / "keel_finlogo" / "static" / "keel_finlogo"
FLAG_ROOT = STATIC_ROOT / "flags"
MANIFEST_PATH = STATIC_ROOT / "manifest.json"

CODES_URL = "https://flagcdn.com/en/codes.json"
WEBP_URL_TMPL = "https://flagcdn.com/w{width}/{code}.webp"
SVG_URL_TMPL = "https://flagcdn.com/{code}.svg"
WIDTHS = (40, 80, 160, 320, 640)
MAX_WORKERS = 12
TIMEOUT_S = 30
UA = "keel-finlogo-flag-sync/1.0"


def load_manifest() -> dict:
    if MANIFEST_PATH.is_file():
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {}


def save_manifest(data: dict) -> None:
    MANIFEST_PATH.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def fetch_one(code: str) -> tuple[str, bool, str]:
    dest_dir = FLAG_ROOT / code
    dest_dir.mkdir(parents=True, exist_ok=True)
    headers = {"User-Agent": UA}
    try:
        for width in WIDTHS:
            resp = requests.get(WEBP_URL_TMPL.format(width=width, code=code), headers=headers, timeout=TIMEOUT_S)
            resp.raise_for_status()
            (dest_dir / f"w{width}.webp").write_bytes(resp.content)
        svg_resp = requests.get(SVG_URL_TMPL.format(code=code), headers=headers, timeout=TIMEOUT_S)
        if svg_resp.ok:
            (dest_dir / "flag.svg").write_bytes(svg_resp.content)
        return code, True, ""
    except Exception as exc:
        return code, False, str(exc)


def main() -> int:
    ap = argparse.ArgumentParser(description="Download country flags from flagcdn.com into keel-finlogo.")
    ap.add_argument(
        "codes", nargs="*",
        help="ISO-3166-1 alpha-2 codes to (re-)fetch, e.g. 'us gb ae'. Omit for every country.",
    )
    args = ap.parse_args()

    explicit_codes = [c.lower() for c in args.codes]
    if explicit_codes:
        codes = {c: c for c in explicit_codes}
    else:
        print(f"Fetching {CODES_URL} …", flush=True)
        resp = requests.get(CODES_URL, headers={"User-Agent": UA}, timeout=TIMEOUT_S)
        resp.raise_for_status()
        codes = resp.json()

    FLAG_ROOT.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {len(codes)} flags at widths {WIDTHS} …", flush=True)

    manifest = load_manifest()
    failures = []
    done = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(fetch_one, code): (code, name) for code, name in codes.items()}
        for fut in as_completed(futures):
            code, name = futures[fut]
            _, ok, err = fut.result()
            done += 1
            if ok:
                manifest[f"flag/{code}"] = {
                    "category": "flag", "slug": code, "brand_name": name,
                    "domain": "", "source": "flagcdn.com",
                    "license_note": "flagcdn.com (public domain / CC-licensed flag assets)",
                    "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    "variants": {"flag": {"sizes": list(WIDTHS), "svg": True, "webp": True}},
                }
            else:
                failures.append((code, err))
            if done % 50 == 0 or done == len(codes):
                print(f"  … {done}/{len(codes)}", flush=True)

    save_manifest(manifest)

    if failures:
        print("Failures:", file=sys.stderr)
        for code, err in failures[:30]:
            print(f"  {code}: {err}", file=sys.stderr)
        if len(failures) > 30:
            print(f"  … and {len(failures) - 30} more", file=sys.stderr)
        return 1
    print(f"OK — {len(codes)} flags in {FLAG_ROOT}, manifest.json updated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
