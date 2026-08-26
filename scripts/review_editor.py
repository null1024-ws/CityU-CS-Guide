#!/usr/bin/env python3
"""Apply editorial overlay: rewrite tips and excerpts, drop noisy sources.

Regex extraction keeps recall; this step is the precision layer.
Canonical copy lives in data/editorial.json (not overwritten by extract/score).
Re-edit with the prompt in scripts/prompts/review_editor.md.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths import (  # noqa: E402
    EDITORIAL_JSON,
    REVIEW_EDITOR_PROMPT,
    REVIEWS_DIR,
    ensure_dirs,
    load_courses,
)

TITLE_ONLY_RE = re.compile(
    r"^(?:[A-Z]{2}\d{4}\s+)?[A-Za-z][A-Za-z0-9 .,&'():+/-]{8,80}$"
)
QUESTION_RE = re.compile(
    r"大家推荐选吗|有没有也选了|有上过.{0,8}吗|蹲一个|求问",
    re.I,
)


def load_editorial() -> dict:
    if not EDITORIAL_JSON.exists():
        return {}
    return json.loads(EDITORIAL_JSON.read_text(encoding="utf-8"))


def save_editorial(data: dict) -> None:
    EDITORIAL_JSON.parent.mkdir(parents=True, exist_ok=True)
    EDITORIAL_JSON.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def is_title_only(excerpt: str) -> bool:
    text = re.sub(r"\s+", " ", excerpt or "").strip()
    if len(text) > 90:
        return False
    return bool(TITLE_ONLY_RE.match(text))


def is_question_post(excerpt: str) -> bool:
    text = excerpt or ""
    if len(text) > 400:
        return False
    return bool(QUESTION_RE.search(text)) and not any(
        k in text for k in ("作业", "期末", "开卷", "闭卷", "给分", "project", "Project")
    )


def filter_sources(sources: list[dict], drop_ids: set[str], *, comments: bool = False) -> list[dict]:
    kept = []
    for src in sources:
        nid = src.get("noteId", "")
        cid = src.get("commentId", "")
        if comments:
            if cid in drop_ids or nid in drop_ids:
                continue
        elif nid in drop_ids:
            continue
        excerpt = src.get("excerpt", "")
        if is_title_only(excerpt):
            continue
        if not comments and is_question_post(excerpt):
            continue
        kept.append(src)
    return kept


def apply_one(review: dict, entry: dict | None) -> tuple[dict, list[str]]:
    logs: list[str] = []
    code = review.get("courseCode", "")
    drop_notes = set((entry or {}).get("dropNoteIds") or [])
    drop_comments = set((entry or {}).get("dropCommentIds") or [])

    before_posts = len(review.get("sources") or [])
    before_comments = len(review.get("commentSources") or [])
    review["sources"] = filter_sources(review.get("sources") or [], drop_notes)
    review["commentSources"] = filter_sources(
        review.get("commentSources") or [], drop_notes | drop_comments, comments=True
    )
    dropped_p = before_posts - len(review["sources"])
    dropped_c = before_comments - len(review["commentSources"])
    if dropped_p or dropped_c:
        logs.append(f"{code}: dropped {dropped_p} post(s), {dropped_c} comment(s)")

    if entry is not None and "excerpts" in entry:
        mapping = entry.get("excerpts") or {}
        rewritten = []
        for src in review.get("sources") or []:
            nid = src.get("noteId")
            if nid in mapping and str(mapping[nid]).strip():
                rewritten.append({**src, "excerpt": str(mapping[nid]).strip()})
        review["sources"] = rewritten
        logs.append(f"{code}: {len(rewritten)} edited post excerpt(s)")

    if entry is not None and "commentExcerpts" in entry:
        mapping = entry.get("commentExcerpts") or {}
        rewritten = []
        for src in review.get("commentSources") or []:
            cid = src.get("commentId")
            if cid in mapping and str(mapping[cid]).strip():
                rewritten.append({**src, "excerpt": str(mapping[cid]).strip()})
        review["commentSources"] = rewritten
        logs.append(f"{code}: {len(rewritten)} edited comment excerpt(s)")
    elif entry is not None and "excerpts" in entry:
        review["commentSources"] = []

    if entry is not None and "tips" in entry:
        tips = [t.strip() for t in entry["tips"] if str(t).strip()]
        if len(tips) > 2:
            logs.append(f"{code}: truncating {len(tips)} tips to 2")
            tips = tips[:2]
        review["tips"] = tips
        review["lastUpdated"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        logs.append(f"{code}: set {len(tips)} editorial tip(s)")
    return review, logs


def dump_packet(code: str) -> str:
    path = REVIEWS_DIR / f"{code}.json"
    if not path.exists():
        raise SystemExit(f"missing review file: {path}")
    review = json.loads(path.read_text(encoding="utf-8"))
    courses = {c["code"]: c for c in load_courses()}
    meta = courses.get(code, {})
    prompt = REVIEW_EDITOR_PROMPT.read_text(encoding="utf-8") if REVIEW_EDITOR_PROMPT.exists() else ""
    packet = {
        "course": {
            "code": code,
            "title": meta.get("title"),
            "category": meta.get("category"),
            "group": meta.get("group"),
            "stream": meta.get("stream"),
        },
        "draftTips": review.get("tips") or [],
        "fields": review.get("fields") or {},
        "sources": [
            {"noteId": s.get("noteId"), "postTitle": s.get("postTitle"), "excerpt": s.get("excerpt")}
            for s in (review.get("sources") or [])[:8]
        ],
        "commentSources": [
            {
                "noteId": s.get("noteId"),
                "commentId": s.get("commentId"),
                "excerpt": s.get("excerpt"),
            }
            for s in (review.get("commentSources") or [])[:8]
        ],
    }
    return prompt.strip() + "\n\n## 本课材料\n\n" + json.dumps(packet, ensure_ascii=False, indent=2)


def rebuild_index() -> None:
    entries = []
    for course in load_courses():
        path = REVIEWS_DIR / f"{course['code']}.json"
        if not path.exists():
            continue
        review = json.loads(path.read_text(encoding="utf-8"))
        fields = review.get("fields") or {}
        covered = sum(1 for f in fields.values() if f.get("confidence") != "unknown")
        entries.append({
            "code": course["code"],
            "coveredFields": covered,
            "sourceCount": len(review.get("sources") or []) + len(review.get("commentSources") or []),
        })
    (REVIEWS_DIR / "_index.json").write_text(
        json.dumps(entries, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply or dump review editorial overlay")
    parser.add_argument("--dump", metavar="CODE", help="print editor prompt + course packet")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    ensure_dirs()

    if args.dump:
        print(dump_packet(args.dump.upper()))
        return

    editorial = load_editorial()
    courses = load_courses()
    changed = 0
    for course in courses:
        code = course["code"]
        path = REVIEWS_DIR / f"{code}.json"
        if not path.exists():
            continue
        review = json.loads(path.read_text(encoding="utf-8"))
        review, logs = apply_one(review, editorial.get(code))
        for line in logs:
            print(line)
        if logs:
            changed += 1
            if not args.dry_run:
                path.write_text(
                    json.dumps(review, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
    if not args.dry_run:
        rebuild_index()
    print(f"{'Would update' if args.dry_run else 'Updated'} {changed} course review(s).")


if __name__ == "__main__":
    main()
