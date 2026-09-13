#!/usr/bin/env python3
"""
Download the CC0 sprite library. One archive, a couple of seconds, no API key.

    python core/scripts/fetch_assets.py

4,006 PNGs from Kenney (CC0 1.0 — public domain, commercial use fine, safe to
redistribute inside generated games), plus audio and fonts. Vendored rather than
fetched per sprite so generation is instant, offline and free.
"""

import io
import sys
import tarfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "core" / "asset_library_raw"
URL = "https://codeload.github.com/iwenzhou/kenney/tar.gz/refs/heads/master"


def main() -> int:
    if TARGET.exists() and any(TARGET.rglob("*.png")):
        count = sum(1 for _ in TARGET.rglob("*.png"))
        print(f"Already present: {count} sprites at {TARGET}")
        return 0

    print(f"Downloading CC0 sprite library (~19MB)...")
    with urllib.request.urlopen(URL, timeout=300) as response:
        data = response.read()

    TARGET.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        members = archive.getmembers()
        for member in members:
            # Strip the repo's top-level directory.
            parts = Path(member.name).parts[1:]
            if not parts:
                continue
            member.name = str(Path(*parts))
            archive.extract(member, TARGET)

    count = sum(1 for _ in TARGET.rglob("*.png"))
    print(f"Extracted {count} sprites to {TARGET}")
    return 0 if count else 1


if __name__ == "__main__":
    raise SystemExit(main())
