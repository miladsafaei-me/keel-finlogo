#!/usr/bin/env python3
"""build_coin3d.py — strike each landing coin's own vector mark into a minted 3D coin.

The nine coins `/signals/crypto` carries (`signal_universe.MARKETS["crypto"]`) each get
a `coin3d` variant: the coin's official mark, extruded into the keel-visuals object
factory's coin blank and rendered on the stage's one camera, at 1024 and 512 px. This
package owns the brand (§3.3 of the landing-cover implementation spec); the extrusion
itself is keel-visuals' `coin` command (`scripts/build_factory_objects.py coin`), which
ships no brand of its own on purpose.

Typical use, from this repo's root::

    python3 scripts/build_coin3d.py --container signalbots-web \\
        --factory-script /path/to/keel-visuals/scripts/build_factory_objects.py

Rendering needs Playwright with Chromium (WebGL2 on SwiftShader) — see the factory
script's own module docstring. `--container` runs it there instead: this script copies
the factory script, its `_common.py` and its vendored `factory/` (three.js + the page)
in once, runs `coin` for every requested slug, and copies each PNG back out — the same
copy-in/run/copy-out recipe the keel-visuals README documents for `render`.

A coin whose manifest `icon` carries an SVG is struck from `icon.svg` (`--face-svg`).
A coin whose `icon` has no SVG is set from its largest `icon-<size>.png` instead
(`--face-png`): the factory lays a raster mark into the coin's face as a clear-coated
decal, inset and cut to a circle when the mark is a disc. The manifest's `coin3d`
variant records which kind of face each coin was made from. Doge is that case today
only because its `icon` was fetched from dogecoin.com's 300 px raster; Dogecoin Core
publishes the same mark as a vector (`share/pixmaps/dogecoin256.svg`), and once `icon`
is re-fetched from it this script needs no change — rerun `--coins doge`. The white "D"
across the Shiba is part of that official mark, so the coin keeps it. Run with --help
for the full flag list.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
STATIC_ROOT = REPO_ROOT / "src" / "keel_finlogo" / "static" / "keel_finlogo"
LOGOS_ROOT = STATIC_ROOT / "logos" / "coin"
MANIFEST_PATH = STATIC_ROOT / "manifest.json"
MANIFEST_LOCK_PATH = MANIFEST_PATH.with_suffix(".json.lock")

# The nine coins /signals/crypto carries, in the order the landing lists them.
COINS = ["btc", "eth", "xrp", "sol", "bnb", "doge", "zec", "sui", "hype"]

SIZES = (1024, 512)

# Per-slug override for the coin CLI's --metal choice, for when "auto" (which follows
# the mark's own dominant colour) picks a rim that reads wrong next to that brand's
# colours once rendered. xrp and hype are both a single near-black ink (#141414,
# #011916) — "auto" reads that as gunmetal, so the flat face and the mark's own enamel
# end up the same near-black tone and the mark all but disappears (visible only in the
# specular highlight). Forcing silver keeps the mark in its true dark ink while giving
# the face enough contrast to actually read; a reviewed render is what earns a slug a
# place here, not a guess.
METAL_OVERRIDE: dict[str, str] = {"xrp": "silver", "hype": "silver"}


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def load_manifest() -> dict:
    if MANIFEST_PATH.is_file():
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {}


def face_for(slug: str, manifest: dict) -> tuple[str, Path] | None:
    """Return this coin's best mark as ("svg" | "png", path), or None when it has none.

    The manifest is the source of truth, not a bare file check: a stale pre-fix SVG can
    still be sitting on disk (doge's `icon.svg` is the flat Simple Icons "D" glyph the
    official raster mark replaced as `icon` — see ENGINE-REVIEW §3.1's known defects),
    and a coin this repo has already decided has no acceptable vector must not be
    struck with the mark it was replaced for. Such a coin gets its official raster
    instead, at the largest size the manifest lists, because the factory magnifies a
    raster to fill the coin's face and every pixel it starts with shows.
    """
    icon = manifest.get(f"coin/{slug}", {}).get("variants", {}).get("icon")
    if not icon:
        return None
    if icon.get("svg"):
        path = LOGOS_ROOT / slug / "icon.svg"
        return ("svg", path) if path.is_file() else None
    for size in sorted(icon.get("sizes", []), reverse=True):
        path = LOGOS_ROOT / slug / f"icon-{size}.png"
        if path.is_file():
            return "png", path
    return None


class Runner:
    """Runs the keel-visuals factory's `coin` command, locally or inside a container."""

    def __init__(self, factory_script: Path, container: str | None):
        self.factory_script = factory_script
        self.container = container
        self.remote_root = "/tmp/keel-finlogo-coin3d"
        if container:
            self._stage_container()

    def _run(self, cmd: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(cmd, check=True, capture_output=True, text=True)

    def _stage_container(self) -> None:
        factory_dir = self.factory_script.parent
        self._run([
            "podman", "exec", self.container, "mkdir", "-p",
            f"{self.remote_root}/scripts", f"{self.remote_root}/faces", f"{self.remote_root}/out",
        ])
        for name in ("build_factory_objects.py", "_common.py"):
            src = factory_dir / name
            self._run(["podman", "cp", str(src), f"{self.container}:{self.remote_root}/scripts/{name}"])
        self._run([
            "podman", "cp", str(factory_dir / "factory"),
            f"{self.container}:{self.remote_root}/scripts/factory",
        ])

    def coin(self, slug: str, face: tuple[str, Path], out: Path, size: int, metal: str) -> dict:
        kind, face_path = face
        flag = f"--face-{kind}"
        out.parent.mkdir(parents=True, exist_ok=True)
        if self.container:
            remote_face = f"{self.remote_root}/faces/{slug}.{kind}"
            remote_out = f"{self.remote_root}/out/{slug}-{size}.png"
            self._run(["podman", "cp", str(face_path), f"{self.container}:{remote_face}"])
            result = self._run([
                "podman", "exec", "-w", f"{self.remote_root}/scripts", self.container,
                "python3", "build_factory_objects.py", "coin",
                flag, f"../faces/{slug}.{kind}", "--out", f"../out/{slug}-{size}.png",
                "--size", str(size), "--metal", metal,
            ])
            self._run(["podman", "cp", f"{self.container}:{remote_out}", str(out)])
        else:
            result = self._run([
                sys.executable, str(self.factory_script), "coin",
                flag, str(face_path), "--out", str(out),
                "--size", str(size), "--metal", metal,
            ])
        return json.loads(result.stdout)

    def cleanup(self) -> None:
        if self.container:
            self._run(["podman", "exec", self.container, "rm", "-rf", self.remote_root])


def update_manifest(built: dict[str, dict]) -> None:
    """Add a `coin3d` variant to each built coin's existing manifest entry.

    Only the `variants.coin3d` key is touched — `brand_name`/`source`/`fetched_at`/
    `license_note` describe the 2-D mark's own provenance and stay untouched, since the
    3-D render adds no new source, it re-strikes the mark this repo already fetched.
    `face` says whether it was struck from the vector or set from the raster, because
    a raster coin is softer and a caller choosing a hero size should know.
    Wrapped in the same flock `fetch_logo.py` uses, so this can run alongside it.
    """
    if not built:
        return
    MANIFEST_LOCK_PATH.touch(exist_ok=True)
    with open(MANIFEST_LOCK_PATH, "r+") as lock_fh:
        fcntl.flock(lock_fh, fcntl.LOCK_EX)
        try:
            data = load_manifest()
            for slug in built:
                key = f"coin/{slug}"
                entry = data[key]
                entry["variants"]["coin3d"] = {
                    "sizes": sorted(SIZES), "svg": False, "webp": False, "ink": "color",
                    "face": built[slug]["face"],
                }
            MANIFEST_PATH.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        finally:
            fcntl.flock(lock_fh, fcntl.LOCK_UN)


def main() -> int:
    ap = argparse.ArgumentParser(description="Strike each landing coin's mark into a 3-D coin.")
    ap.add_argument("--coins", nargs="*", default=COINS, choices=COINS, help="Slugs to build (default: all nine).")
    ap.add_argument(
        "--factory-script", type=Path, default=REPO_ROOT.parent / "keel-visuals" / "scripts" / "build_factory_objects.py",
        help="Path to keel-visuals' build_factory_objects.py (default: the sibling repo checkout).",
    )
    ap.add_argument("--container", help="Run the factory command inside this podman container (needs Playwright there).")
    ap.add_argument("--metal", choices=["auto", "gold", "silver", "gunmetal"], default="auto")
    args = ap.parse_args()

    if not args.factory_script.is_file():
        log(f"✗ no factory script at {args.factory_script} — pass --factory-script.")
        return 2

    manifest = load_manifest()
    runner = Runner(args.factory_script, args.container)

    built: dict[str, dict] = {}
    skipped: dict[str, str] = {}
    failed: dict[str, str] = {}

    for slug in args.coins:
        face = face_for(slug, manifest)
        if face is None:
            reason = f"coin/{slug} has no icon in the manifest, neither an SVG nor a PNG on disk, to put on a coin"
            log(f"· {slug}: skipped — {reason}")
            skipped[slug] = reason
            continue

        metal = METAL_OVERRIDE.get(slug, args.metal)
        reports = {}
        try:
            for size in SIZES:
                out = LOGOS_ROOT / slug / f"coin3d-{size}.png"
                reports[size] = runner.coin(slug, face, out, size, metal)
                log(f"  {slug} @ {size}px from {face[0]}: metal={reports[size]['metal']} face={reports[size]['face']}")
        except subprocess.CalledProcessError as exc:  # one coin's failure should not sink the batch
            detail = exc.stderr.strip() if exc.stderr else str(exc)
            failed[slug] = detail
            log(f"✗ {slug}: {detail}")
            continue

        built[slug] = {"metal": reports[SIZES[0]]["metal"], "face": face[0], "sizes": sorted(SIZES)}
        log(f"✓ {slug}: coin3d-{{{','.join(str(s) for s in sorted(SIZES))}}}.png")

    runner.cleanup()
    update_manifest(built)

    print(json.dumps({
        "ok": not failed,
        "built": built,
        "skipped": skipped,
        "failed": failed,
        "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }, indent=2))
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
