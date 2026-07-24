#!/usr/bin/env python3
"""Merge post body, OCR, and comments into content bundles."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths import COURSE_CODE_RE, RAW_BUNDLES, RAW_OCR, RAW_XHS, ensure_dirs  # noqa: E402

CODE_PATTERN = re.compile(COURSE_CODE_RE, re.IGNORECASE)


def text_from_note(note_payload: dict | None) -> tuple[str, str]:
    if not note_payload:
        return "", ""
    title = ""
    body_parts: list[str] = []

    def absorb(card: dict) -> None:
        nonlocal title
        for key in ("title", "display_title"):
            if card.get(key) and not title:
                title = str(card[key])
        for key in ("desc", "content", "note_content", "text"):
            val = card.get(key)
            if isinstance(val, str) and val.strip():
                body_parts.append(val.strip())

    if isinstance(note_payload.get("items"), list):
        for item in note_payload["items"]:
            if isinstance(item, dict):
                absorb(item)
                card = item.get("note_card") or item.get("note") or {}
                if isinstance(card, dict):
                    absorb(card)

    absorb(note_payload)
    note_card = note_payload.get("note_card") or note_payload.get("note") or {}
    if isinstance(note_card, dict):
        absorb(note_card)

    return title, "\n".join(dict.fromkeys(body_parts))


def iter_comments(comments_payload: dict | None) -> list[dict]:
    if not comments_payload:
        return []
    raw: list[dict] = []
    for key in ("comments", "comment_list", "items"):
        val = comments_payload.get(key)
        if isinstance(val, list):
            raw = val
            break
    if isinstance(comments_payload, list):
        raw = comments_payload

    flat: list[dict] = []
    for c in raw:
        flat.append({**c, "_kind": "comment"})
        for sub in c.get("sub_comments") or []:
            if isinstance(sub, dict):
                flat.append({**sub, "_kind": "sub_comment", "_parent": c})
    return flat


def comment_text(c: dict) -> str:
    for key in ("content", "text", "comment"):
        val = c.get(key)
        if isinstance(val, str):
            return val.strip()
    return ""


def comment_id(c: dict, fallback: str) -> str:
    for key in ("id", "comment_id", "cid"):
        if c.get(key):
            return str(c[key])
    return fallback


def build_bundle(note_file: Path) -> dict:
    raw = json.loads(note_file.read_text(encoding="utf-8"))
    note_id = raw.get("note_id") or note_file.stem
    title, body = text_from_note(raw.get("note"))
    chunks: list[dict] = []

    if title:
        chunks.append({"type": "post_title", "text": title, "sourceRef": "post"})
    if body:
        chunks.append({"type": "post_body", "text": body, "sourceRef": "post"})

    ocr_path = RAW_OCR / f"{note_id}.json"
    if ocr_path.exists():
        ocr = json.loads(ocr_path.read_text(encoding="utf-8"))
        for i, page in enumerate(ocr.get("pages") or []):
            text = (page.get("text") or "").strip()
            if text:
                chunks.append({
                    "type": "ocr",
                    "text": text,
                    "sourceRef": f"image:{i}",
                    "confidence": page.get("confidence", 0),
                })

    comments = iter_comments(raw.get("comments"))
    for i, c in enumerate(comments):
        text = comment_text(c)
        if len(text) < 4:
            continue
        cid = comment_id(c, f"idx{i}")
        likes = c.get("like_count") or c.get("likes") or 0
        chunk_type = "sub_comment" if c.get("_kind") == "sub_comment" else "comment"
        chunks.append({
            "type": chunk_type,
            "text": text,
            "sourceRef": f"comment:{cid}",
            "commentId": cid,
            "likes": likes,
            "author": c.get("user_info", {}).get("nickname") or c.get("nickname") or "",
        })

    codes = sorted(set(m.group(1).upper() for m in CODE_PATTERN.finditer("\n".join(c["text"] for c in chunks))))
    return {
        "note_id": note_id,
        "url": raw.get("url", ""),
        "fetched_at": raw.get("fetched_at"),
        "course_codes": codes,
        "chunks": chunks,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--note-id", help="Process single note")
    args = parser.parse_args()
    ensure_dirs()

    files = [RAW_XHS / f"{args.note_id}.json"] if args.note_id else sorted(RAW_XHS.glob("*.json"))
    for path in files:
        bundle = build_bundle(path)
        out = RAW_BUNDLES / f"{bundle['note_id']}.json"
        out.write_text(json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Bundle {bundle['note_id']}: {len(bundle['chunks'])} chunks, codes={bundle['course_codes']}")


if __name__ == "__main__":
    main()
