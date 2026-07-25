#!/usr/bin/env python3
"""Run the full data pipeline (except xhs_collect)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STEPS = [
    (["content_bundle.py"], True),
    (["review_extract.py"], True),
    (["credibility_score.py"], True),
    (["build_site.py"], True),
    (["audit_reviews.py"], False),
]


def main() -> None:
    for step, required in STEPS:
        script = ROOT / "scripts" / step[0]
        print(f"\n=== {script.name} ===")
        result = subprocess.run([sys.executable, str(script), *step[1:]], cwd=ROOT)
        if result.returncode != 0:
            if required:
                sys.exit(result.returncode)
            print(f"Warning: {script.name} reported issues (non-fatal).")
    print("\nPipeline complete. Open site/dist/index.html or deploy to GitHub Pages.")


if __name__ == "__main__":
    main()
