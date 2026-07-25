#!/usr/bin/env python3
"""Apply credibility scoring to extracted review hits."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from review_extract import FIELD_LABELS  # noqa: E402
from _paths import REVIEWS_DIR, ensure_dirs, load_courses  # noqa: E402


def format_variant_note(field_name: str, counter: Counter) -> str:
    label_map = FIELD_LABELS.get(field_name, {})
    parts = [
        f"{label_map.get(value, value)}×{count}"
        for value, count in counter.most_common()
    ]
    return "来源说法不一：" + "、".join(parts)


def score_field(hits: list[dict]) -> dict:
    if not hits:
        return {"value": "unknown", "confidence": "unknown", "sourceCount": 0, "label": "暂无数据"}

    values = [h["value"] for h in hits]
    counter = Counter(values)
    top_value, top_count = counter.most_common(1)[0]

    post_hits = [h for h in hits if h.get("type") != "comment"]
    comment_hits = [h for h in hits if h.get("type") == "comment"]

    if len(counter) > 1 and counter.most_common(2)[0][1] == counter.most_common(2)[1][1]:
        confidence = "disputed"
        field_name = hits[0]["field"]
        note = format_variant_note(field_name, counter)
    elif top_count >= 2 and len({h["noteId"] for h in hits}) >= 2:
        confidence = "confirmed"
        note = ""
    elif top_count == 1 and comment_hits and post_hits:
        post_vals = {h["value"] for h in post_hits}
        comment_vals = {h["value"] for h in comment_hits}
        if post_vals & comment_vals:
            confidence = "confirmed"
            note = "帖子与评论区一致"
        elif comment_vals - post_vals:
            confidence = "disputed"
            note = "评论区与帖子说法不一致"
        else:
            confidence = "reported"
            note = ""
    elif top_count >= 2:
        confidence = "reported"
        note = "同一帖子多次提及，待更多独立来源确认"
    else:
        confidence = "reported"
        note = ""

    field_name = hits[0]["field"]
    label_map = FIELD_LABELS.get(field_name, {})
    label = label_map.get(top_value, top_value)

    result = {
        "value": top_value,
        "label": label,
        "confidence": confidence,
        "sourceCount": len(hits),
        "distinctSources": len({h["noteId"] for h in hits}),
    }
    if note:
        result["note"] = note
    if confidence == "disputed":
        result["variants"] = dict(counter)
    return result


def finalize_review(raw: dict) -> dict:
    fields = {}
    for field_name, hits in raw.get("field_hits", {}).items():
        if hits:
            hit_copy = [{**h, "field": field_name} for h in hits]
            fields[field_name] = score_field(hit_copy)

    for fname in ("difficulty", "grading", "workload", "hasRecording", "attendance", "examFormat"):
        fields.setdefault(fname, score_field([]))

    seen_posts = {}
    for src in raw.get("post_sources", []):
        key = src.get("noteId")
        if not key:
            continue
        prev = seen_posts.get(key)
        if not prev or len(src.get("excerpt", "")) > len(prev.get("excerpt", "")):
            seen_posts[key] = src

    seen_comments = {}
    for src in raw.get("comment_sources", []):
        key = (src.get("noteId"), src.get("commentId"))
        if key not in seen_comments:
            seen_comments[key] = src

    return {
        "courseCode": raw["courseCode"],
        "fields": fields,
        "tips": raw.get("tips", []),
        "sources": list(seen_posts.values()),
        "commentSources": list(seen_comments.values()),
        "lastUpdated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    args = parser.parse_args()
    ensure_dirs()
    courses = load_courses()

    index_entries = []
    for course in courses:
        code = course["code"]
        raw_path = REVIEWS_DIR / f"{code}.json"
        if not raw_path.exists():
            continue
        raw = json.loads(raw_path.read_text(encoding="utf-8"))
        if "field_hits" not in raw:
            continue
        final = finalize_review(raw)
        raw_path.write_text(json.dumps(final, indent=2, ensure_ascii=False), encoding="utf-8")
        covered = sum(1 for f in final["fields"].values() if f.get("confidence") != "unknown")
        index_entries.append({"code": code, "coveredFields": covered, "sourceCount": len(final["sources"]) + len(final["commentSources"])})

    (REVIEWS_DIR / "_index.json").write_text(json.dumps(index_entries, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Finalized {len(index_entries)} course reviews.")


if __name__ == "__main__":
    main()
