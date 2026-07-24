#!/usr/bin/env python3
"""Collect Xiaohongshu notes via xhs CLI with checkpoint/resume."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths import (  # noqa: E402
    RAW_XHS,
    ensure_dirs,
    load_courses,
    load_raw_index,
    save_raw_index,
    xhs_bin,
    xhs_env,
)

GLOBAL_QUERIES = [
    "城大 MSc CS 选课",
    "城市大学 计算机硕士 选课攻略",
    "CityU CS 硕士 课程评价",
    "城大计算机硕士 选课",
    "香港城市大学 CS 选课",
]


def run_xhs(args: list[str], timeout: int = 120) -> dict | None:
    cmd = [xhs_bin(), *args, "--json"]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=xhs_env(),
            encoding="utf-8",
        )
        if result.returncode != 0:
            print(f"  WARN xhs failed: {' '.join(args[:3])} -> {result.stdout[:200]}", file=sys.stderr)
            return None
        return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        print(f"  ERROR xhs: {exc}", file=sys.stderr)
        return None


def note_id_from_item(item: dict) -> str | None:
    for key in ("id", "note_id"):
        if item.get(key):
            return str(item[key])
    note_card = item.get("note_card") or item.get("note") or {}
    if note_card.get("note_id"):
        return str(note_card["note_id"])
    if note_card.get("id"):
        return str(note_card["id"])
    return None


def clean_note_url(url: str) -> str:
    """Strip hash fragments and normalize explore URLs for xhs CLI."""
    url = url.split("#", 1)[0]
    return url


def note_url_from_item(item: dict) -> str | None:
    for key in ("url", "note_url", "link"):
        if item.get(key):
            return clean_note_url(str(item[key]))
    note_card = item.get("note_card") or {}
    if note_card.get("url"):
        return clean_note_url(str(note_card["url"]))
    note_id = note_id_from_item(item)
    xsec = item.get("xsec_token") or note_card.get("xsec_token")
    if note_id and xsec:
        clean_id = note_id.split("#", 1)[0]
        return f"https://www.xiaohongshu.com/explore/{clean_id}?xsec_token={xsec}"
    return None


def extract_search_items(data: dict) -> list[dict]:
    if not data or not data.get("ok"):
        return []
    payload = data.get("data") or {}
    for key in ("items", "notes", "note_list"):
        if isinstance(payload.get(key), list):
            return payload[key]
    if isinstance(payload, list):
        return payload
    return []


def save_note_bundle(note_id: str, bundle: dict) -> None:
    path = RAW_XHS / f"{note_id}.json"
    path.write_text(json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8")


def fetch_note_detail(url: str, note_id: str) -> dict:
    url = clean_note_url(url)
    note_id = note_id.split("#", 1)[0]
    bundle: dict = {"note_id": note_id, "url": url, "fetched_at": time.time()}
    read_data = run_xhs(["read", url])
    if read_data and read_data.get("ok"):
        bundle["note"] = read_data.get("data")
        read_url = (read_data.get("data") or {}).get("url") or url
        url = clean_note_url(str(read_url))
        bundle["url"] = url
    comments_data = run_xhs(["comments", url, "--all"], timeout=180)
    if comments_data and comments_data.get("ok"):
        bundle["comments"] = comments_data.get("data")
    return bundle


def collect_search(query: str, index: dict, max_notes: int) -> int:
    if query in index["checkpoint"].get("completed_searches", []):
        print(f"  skip (done): {query}")
        return 0

    print(f"  search: {query}")
    data = run_xhs(["search", query])
    if search_failed(data):
        err = (data or {}).get("error") or {}
        code = err.get("code", "unknown")
        print(f"  skip (failed:{code}): {query}", file=sys.stderr)
        if code == "verification_required":
            return -1
        if code == "not_authenticated":
            return -2
        return 0

    items = extract_search_items(data or {})
    new_count = 0

    for item in items:
        if new_count >= max_notes:
            break
        note_id = note_id_from_item(item)
        url = note_url_from_item(item)
        if not note_id or not url:
            continue
        if note_id in index["notes"]:
            continue

        print(f"    fetch note {note_id}")
        bundle = fetch_note_detail(url, note_id)
        bundle["search_query"] = query
        bundle["search_item"] = item
        save_note_bundle(note_id, bundle)
        index["notes"][note_id] = {"url": url, "query": query, "fetched_at": bundle["fetched_at"]}
        new_count += 1
        time.sleep(2.0)

    index["searches"].append({"query": query, "items_found": len(items), "new_notes": new_count, "at": time.time()})
    index["checkpoint"].setdefault("completed_searches", []).append(query)
    save_raw_index(index)
    return new_count


def queries_for_course(code: str) -> list[str]:
    return [
        f"{code} 城大",
        f"{code} 城大CS",
        f"{code} CityU",
        f"城大{code}",
    ]


def build_queries(courses: list[dict], per_course: bool, course_filter: set[str] | None) -> list[str]:
    queries = list(GLOBAL_QUERIES)
    if per_course:
        for course in courses:
            code = course["code"]
            if course_filter and code not in course_filter:
                continue
            queries.extend(queries_for_course(code))
    elif course_filter:
        for code in sorted(course_filter):
            queries.extend(queries_for_course(code))
    return queries


def clear_checkpoint_queries(index: dict, queries: list[str]) -> int:
    completed = index["checkpoint"].setdefault("completed_searches", [])
    remove = set(queries)
    before = len(completed)
    index["checkpoint"]["completed_searches"] = [q for q in completed if q not in remove]
    return before - len(index["checkpoint"]["completed_searches"])


def search_failed(data: dict | None) -> bool:
    if data is None:
        return True
    if data.get("ok"):
        return False
    code = (data.get("error") or {}).get("code", "")
    return code in {"verification_required", "not_authenticated", "api_error"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect XHS course review posts")
    parser.add_argument("--per-course", action="store_true", help="Search every course code")
    parser.add_argument("--courses", type=str, default="", help="Comma-separated course codes (e.g. CS6493,CS6535)")
    parser.add_argument("--retry-failed", action="store_true", help="Clear checkpoint for selected queries before run")
    parser.add_argument("--max-notes", type=int, default=5, help="Max new notes per search query")
    parser.add_argument("--global-only", action="store_true", help="Only run global discovery queries")
    parser.add_argument("--sleep", type=float, default=3.0, help="Pause between search queries (seconds)")
    args = parser.parse_args()

    ensure_dirs()
    courses = load_courses()
    index = load_raw_index()
    index.setdefault("notes", {})
    index.setdefault("searches", [])
    index.setdefault("checkpoint", {})

    course_filter = {c.strip().upper() for c in args.courses.split(",") if c.strip()} or None
    queries = build_queries(courses, per_course=not args.global_only, course_filter=course_filter)

    if args.retry_failed:
        cleared = clear_checkpoint_queries(index, queries)
        save_raw_index(index)
        print(f"Cleared {cleared} checkpoint entries for retry.")

    total = 0
    for query in queries:
        result = collect_search(query, index, args.max_notes)
        if result == -2:
            print("Not authenticated. Run: xhs login --cookie-source edge", file=sys.stderr)
            break
        if result == -1:
            print("Captcha required. Complete verification in browser, re-login, then retry with --retry-failed.", file=sys.stderr)
            break
        if result > 0:
            total += result
        time.sleep(args.sleep)

    print(f"Done. {total} new notes collected. Total notes: {len(index['notes'])}")


if __name__ == "__main__":
    main()
