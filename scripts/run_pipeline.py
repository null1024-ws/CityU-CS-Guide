#!/usr/bin/env python3
"""Run the full data pipeline (except xhs_collect)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STEPS = [
    ["content_bundle.py"],
    ["review_extract.py"],
    ["credibility_score.py"],
    ["build_site.py"],
]


def main() -> None:
    for step in STEPS:
        script = ROOT / "scripts" / step[0]
        print(f"\n=== {script.name} ===")
        result = subprocess.run([sys.executable, str(script), *step[1:]], cwd=ROOT)
        if result.returncode != 0:
            sys.exit(result.returncode)
    print("\nPipeline complete. Open site/dist/index.html or deploy to GitHub Pages.")


if __name__ == "__main__":
    main()
