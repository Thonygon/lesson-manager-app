#!/usr/bin/env python3
"""
Download open-source fonts (DejaVu Sans and Open Sans) into static/fonts/.

Usage:
    python download_fonts.py

Both font families are freely licensed:
  - DejaVu Sans : public domain / Bitstream Vera licence
  - Open Sans   : Apache License 2.0 (Google Fonts)

The script is idempotent — it skips files that already exist.
"""
import os
import sys
import zipfile
import urllib.request
import shutil
from pathlib import Path

FONT_DIR = Path(__file__).resolve().parent / "static" / "fonts"

# ── Sources ──────────────────────────────────────────────────────────
# Each entry: (url, list of (zip_member_path, target_filename))

DOWNLOADS = [
    # DejaVu Sans — GitHub release
    {
        "url": "https://github.com/dejavu-fonts/dejavu-fonts/releases/download/version_2_37/dejavu-fonts-ttf-2.37.zip",
        "extract": [
            ("dejavu-fonts-ttf-2.37/ttf/DejaVuSans.ttf", "DejaVuSans.ttf"),
            ("dejavu-fonts-ttf-2.37/ttf/DejaVuSans-Bold.ttf", "DejaVuSans-Bold.ttf"),
        ],
    },
    # Open Sans — fontsource CDN (Apache 2.0 licence)
    {
        "direct_files": [
            ("https://cdn.jsdelivr.net/fontsource/fonts/open-sans@latest/latin-400-normal.ttf", "OpenSans-Regular.ttf"),
            ("https://cdn.jsdelivr.net/fontsource/fonts/open-sans@latest/latin-700-normal.ttf", "OpenSans-Bold.ttf"),
        ],
    },
]


def _download(url: str, dest: Path) -> Path:
    """Download a URL to a temporary file and return its path."""
    tmp = dest.with_suffix(".tmp")
    print(f"  Downloading {url} …")
    req = urllib.request.Request(url, headers={"User-Agent": "Classio-FontDownloader/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp, open(tmp, "wb") as f:
        shutil.copyfileobj(resp, f)
    return tmp


def _extract_from_zip(zip_path: Path, members: list[tuple[str, str]]):
    """Extract specific members from a zip to FONT_DIR."""
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
        for member, target in members:
            target_path = FONT_DIR / target
            if target_path.exists():
                print(f"  ✓ {target} already exists, skipping")
                continue

            # Try exact match first, then search by filename
            if member in names:
                found = member
            else:
                # Search by basename in case folder structure differs
                basename = os.path.basename(member)
                candidates = [n for n in names if n.endswith(basename) and not n.endswith("/")]
                if candidates:
                    found = candidates[0]
                else:
                    print(f"  ✗ {member} not found in archive, skipping")
                    continue

            data = zf.read(found)
            target_path.write_bytes(data)
            print(f"  ✓ Extracted {target} ({len(data):,} bytes)")


def _download_file(url: str, target: Path):
    """Download a single file directly to target path."""
    print(f"  Downloading {os.path.basename(str(target))} …")
    req = urllib.request.Request(url, headers={"User-Agent": "Classio-FontDownloader/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp, open(target, "wb") as f:
        shutil.copyfileobj(resp, f)
    size = target.stat().st_size
    print(f"  ✓ Saved {target.name} ({size:,} bytes)")


def main():
    FONT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Font directory: {FONT_DIR}\n")

    all_exist = True
    for dl in DOWNLOADS:
        # Determine which files are needed
        if "direct_files" in dl:
            # Download individual files directly (no zip)
            for url, target_name in dl["direct_files"]:
                target_path = FONT_DIR / target_name
                if target_path.exists():
                    print(f"  ✓ {target_name} already exists")
                    continue
                all_exist = False
                _download_file(url, target_path)
        else:
            targets = [t for _, t in dl["extract"]]
            missing = [t for t in targets if not (FONT_DIR / t).exists()]
            if not missing:
                for t in targets:
                    print(f"  ✓ {t} already exists")
                continue

            all_exist = False
            tmp_zip = _download(dl["url"], FONT_DIR / "download.zip")
            try:
                _extract_from_zip(tmp_zip, dl["extract"])
            finally:
                tmp_zip.unlink(missing_ok=True)

    print()
    if all_exist:
        print("All fonts already present — nothing to do.")
    else:
        print("Done! Fonts are ready in static/fonts/.")


if __name__ == "__main__":
    main()
