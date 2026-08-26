#!/usr/bin/env python3
"""Audit course reviews for consistency with source bundles."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths import RAW_BUNDLES, REVIEWS_DIR, load_courses  # noqa: E402
from review_extract import TUTOR_SPAM_RE  # noqa: E402

SPAM_RE = TUTOR_SPAM_RE


def load_bundles() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for path in RAW_BUNDLES.glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        out[data["note_id"]] = data
    return out


def audit() -> int:
    bundles = load_bundles()
    issues: list[str] = []
    courses = load_courses()

    for course in courses:
        code = course["code"]
        path = REVIEWS_DIR / f"{code}.json"
        if not path.exists():
            issues.append(f"{code}: missing review file")
            continue
        review = json.loads(path.read_text(encoding="utf-8"))
        if "fields" not in review:
            issues.append(f"{code}: not finalized (missing fields)")
            continue

        tips = review.get("tips") or []
        if len(tips) > 2:
            issues.append(f"{code}: {len(tips)} tips (want 1–2)")

        for fname, field in review.get("fields", {}).items():
            conf = field.get("confidence")
            ds = field.get("distinctSources", 0)
            sc = field.get("sourceCount", 0)
            if conf == "confirmed" and ds < 2:
                issues.append(f"{code}.{fname}: confirmed but only {ds} distinct source(s)")
            if conf != "unknown" and sc == 0:
                issues.append(f"{code}.{fname}: {conf} but sourceCount=0")

        for kind, sources in (("post", review.get("sources", [])), ("comment", review.get("commentSources", []))):
            for src in sources:
                note_id = src.get("noteId", "")
                excerpt = src.get("excerpt", "")
                if SPAM_RE.search(excerpt) or SPAM_RE.search(src.get("postTitle", "")):
                    issues.append(f"{code}: spam {kind} from {note_id}")
                if note_id and note_id not in bundles:
                    issues.append(f"{code}: {kind} note {note_id} missing bundle")
                    continue
                if not note_id:
                    continue
                bundle = bundles[note_id]
                full = " ".join(c["text"] for c in bundle.get("chunks", []))
                if code.upper() not in full.upper() and code.upper() not in excerpt.upper():
                    issues.append(f"{code}: excerpt may not mention {code} (note {note_id})")

                if fname_hits := review.get("fields"):
                    pass  # field hits stored only in pre-finalize; skip deep verify

    print(f"Audited {len(courses)} courses, {len(issues)} issue(s)")
    for item in issues[:40]:
        print(f"  - {item}")
    if len(issues) > 40:
        print(f"  ... and {len(issues) - 40} more")
    return len(issues)


if __name__ == "__main__":
    raise SystemExit(1 if audit() else 0)
