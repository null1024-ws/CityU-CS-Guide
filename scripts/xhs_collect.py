#!/usr/bin/env python3
"""Collect Xiaohongshu notes via jackwener/xhs-cli with checkpoint/resume."""

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
from search_queries import GLOBAL_QUERIES, build_queries  # noqa: E402


def classify_xhs_error(stderr: str, stdout: str) -> dict:
    text = f"{stderr}\n{stdout}".lower()
    if "not logged in" in text:
        return {"_error": "not_authenticated", "message": (stderr or stdout).strip()}
    if "verification" in text or "verify" in text or "captcha" in text:
        return {"_error": "verification_required", "message": (stderr or stdout).strip()}
    return {"_error": "fetch_failed", "message": (stderr or stdout).strip()}


def run_xhs(args: list[str], timeout: int = 240) -> dict | list | None:
    """Run xhs-cli. Search returns a list; read --comments returns {note, comments}."""
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
        if result.stdout.strip():
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError:
                pass
        if result.returncode != 0:
            err = classify_xhs_error(result.stderr, result.stdout)
            print(
                f"  WARN xhs failed: {' '.join(args[:3])} -> {err.get('message', '')[:200]}",
                file=sys.stderr,
            )
            return err
        return None
    except subprocess.TimeoutExpired as exc:
        print(f"  ERROR xhs timeout: {exc}", file=sys.stderr)
        return {"_error": "fetch_failed", "message": "timeout"}


def note_id_from_item(item: dict) -> str | None:
    for key in ("id", "note_id", "noteId"):
        if item.get(key):
            return str(item[key]).split("#", 1)[0]
    note_card = item.get("note_card") or item.get("noteCard") or item.get("note") or {}
    if note_card.get("note_id"):
        return str(note_card["note_id"]).split("#", 1)[0]
    if note_card.get("id"):
        return str(note_card["id"]).split("#", 1)[0]
    return None


def clean_note_url(url: str) -> str:
    """Strip hash fragments and normalize explore URLs for xhs CLI."""
    url = url.split("#", 1)[0]
    return url


def note_url_from_item(item: dict) -> str | None:
    for key in ("url", "note_url", "link"):
        if item.get(key):
            return clean_note_url(str(item[key]))
    note_card = item.get("note_card") or item.get("noteCard") or {}
    if note_card.get("url"):
        return clean_note_url(str(note_card["url"]))
    note_id = note_id_from_item(item)
    xsec = item.get("xsec_token") or item.get("xsecToken") or note_card.get("xsec_token")
    if note_id and xsec:
        return f"https://www.xiaohongshu.com/explore/{note_id}?xsec_token={xsec}"
    if note_id:
        return f"https://www.xiaohongshu.com/explore/{note_id}"
    return None


def extract_search_items(data: dict | list | None) -> list[dict]:
    if data is None:
        return []
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        if data.get("_error"):
            return []
        if data.get("ok") is False:
            return []
        payload = data.get("data") or {}
        for key in ("items", "notes", "note_list"):
            if isinstance(payload.get(key), list):
                return payload[key]
        if isinstance(payload, list):
            return payload
    return []


def search_error_code(data: dict | list | None) -> str | None:
    if data is None:
        return "fetch_failed"
    if isinstance(data, dict) and data.get("_error"):
        return str(data["_error"])
    if isinstance(data, dict) and data.get("ok") is False:
        return (data.get("error") or {}).get("code", "api_error")
    return None


def normalize_note_entry(entry: dict) -> dict:
    """Ensure queries list exists for cross-check tracking."""
    if "queries" not in entry:
        q = entry.get("query")
        entry["queries"] = [q] if q else []
    elif entry.get("query") and entry["query"] not in entry["queries"]:
        entry["queries"].append(entry["query"])
    return entry


def record_cross_ref(index: dict, note_id: str, query: str) -> bool:
    """Record an additional search query that surfaced an existing note. Returns True if new."""
    entry = normalize_note_entry(index["notes"][note_id])
    if query in entry["queries"]:
        return False
    entry["queries"].append(query)
    entry["query"] = entry["queries"][0]
    index["notes"][note_id] = entry
    return True


def save_note_bundle(note_id: str, bundle: dict) -> None:
    path = RAW_XHS / f"{note_id}.json"
    path.write_text(json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8")


def fetch_note_detail(url: str, note_id: str) -> dict:
    note_id = note_id.split("#", 1)[0]
    bundle: dict = {"note_id": note_id, "url": url, "fetched_at": time.time()}
    read_data = run_xhs(["read", note_id, "--comments"], timeout=300)
    if read_data and isinstance(read_data, dict) and not read_data.get("_error"):
        if "note" in read_data:
            bundle["note"] = read_data["note"]
        elif read_data.get("ok"):
            bundle["note"] = read_data.get("data")
        if "comments" in read_data:
            bundle["comments"] = read_data["comments"]
    return bundle


def collect_search(query: str, index: dict, max_notes: int, max_pages: int = 1) -> int:
    if query in index["checkpoint"].get("completed_searches", []):
        print(f"  skip (done): {query}")
        return 0

    if max_pages > 1:
        print(
            "  note: xhs-cli search has no pagination; using first page only",
            file=sys.stderr,
        )
        max_pages = 1

    items: list[dict] = []
    for page in range(1, max(1, max_pages) + 1):
        page_label = f" (page {page})" if max_pages > 1 else ""
        print(f"  search: {query}{page_label}")
        data = run_xhs(["search", query], timeout=240)
        code = search_error_code(data)
        if code:
            print(f"  skip (failed:{code}): {query}{page_label}", file=sys.stderr)
            if code == "verification_required":
                return -1
            if code == "not_authenticated":
                return -2
            break
        page_items = extract_search_items(data)
        if not page_items:
            break
        items.extend(page_items)
        if page < max_pages:
            time.sleep(2.0)

    seen_ids: set[str] = set()
    deduped: list[dict] = []
    for item in items:
        nid = note_id_from_item(item)
        if nid and nid not in seen_ids:
            seen_ids.add(nid)
            deduped.append(item)
    items = deduped
    new_count = 0
    cross_refs = 0

    for item in items:
        if new_count >= max_notes:
            break
        note_id = note_id_from_item(item)
        url = note_url_from_item(item)
        if not note_id or not url:
            continue
        if note_id in index["notes"]:
            if record_cross_ref(index, note_id, query):
                cross_refs += 1
                print(f"    cross-ref {note_id} via «{query}»")
            continue

        print(f"    fetch note {note_id}")
        bundle = fetch_note_detail(url, note_id)
        bundle["search_query"] = query
        bundle["search_item"] = item
        save_note_bundle(note_id, bundle)
        index["notes"][note_id] = {
            "url": url,
            "query": query,
            "queries": [query],
            "fetched_at": bundle["fetched_at"],
        }
        new_count += 1
        time.sleep(2.0)

    index["searches"].append({
        "query": query,
        "items_found": len(items),
        "new_notes": new_count,
        "cross_refs": cross_refs,
        "at": time.time(),
    })
    index["checkpoint"].setdefault("completed_searches", []).append(query)
    save_raw_index(index)
    return new_count


def migrate_index_cross_refs(index: dict) -> None:
    for note_id, entry in index.get("notes", {}).items():
        normalize_note_entry(entry)


def print_cross_check_summary(index: dict) -> None:
    multi = [
        (nid, e.get("queries", []))
        for nid, e in index.get("notes", {}).items()
        if len(e.get("queries", [])) >= 2
    ]
    if not multi:
        print("Cross-check: no notes matched by multiple queries yet.")
        return
    print(f"Cross-check: {len(multi)} notes found via 2+ search queries")
    for nid, qs in sorted(multi, key=lambda x: -len(x[1]))[:8]:
        print(f"  {nid}: {len(qs)} queries — {qs[0]!r} + {len(qs) - 1} more")


def clear_checkpoint_queries(index: dict, queries: list[str]) -> int:
    completed = index["checkpoint"].setdefault("completed_searches", [])
    remove = set(queries)
    before = len(completed)
    index["checkpoint"]["completed_searches"] = [q for q in completed if q not in remove]
    return before - len(index["checkpoint"]["completed_searches"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect XHS course review posts")
    parser.add_argument("--per-course", action="store_true", help="Search every course code")
    parser.add_argument("--courses", type=str, default="", help="Comma-separated course codes (e.g. CS6493,CS6535)")
    parser.add_argument("--retry-failed", action="store_true", help="Clear checkpoint for selected queries before run")
    parser.add_argument("--max-notes", type=int, default=5, help="Max new notes per search query")
    parser.add_argument("--global-only", action="store_true", help="Only run global discovery queries")
    parser.add_argument("--sleep", type=float, default=3.0, help="Pause between search queries (seconds)")
    parser.add_argument("--max-pages", type=int, default=1, help="Search result pages per query (xhs-cli: first page only)")
    parser.add_argument(
        "--refresh-global",
        action="store_true",
        help="Clear checkpoint for global discovery queries before run",
    )
    parser.add_argument(
        "--skip-global",
        action="store_true",
        help="Skip global discovery queries (useful when focusing on per-course search)",
    )
    args = parser.parse_args()

    ensure_dirs()
    courses = load_courses()
    index = load_raw_index()
    index.setdefault("notes", {})
    index.setdefault("searches", [])
    index.setdefault("checkpoint", {})
    migrate_index_cross_refs(index)

    course_filter = {c.strip().upper() for c in args.courses.split(",") if c.strip()} or None
    queries = build_queries(
        courses,
        per_course=not args.global_only,
        course_filter=course_filter,
        skip_global=args.skip_global,
    )

    if args.retry_failed:
        cleared = clear_checkpoint_queries(index, queries)
        save_raw_index(index)
        print(f"Cleared {cleared} checkpoint entries for retry.")

    if args.refresh_global:
        cleared = clear_checkpoint_queries(index, GLOBAL_QUERIES)
        save_raw_index(index)
        print(f"Cleared {cleared} global query checkpoint entries for rediscovery.")

    max_pages = max(1, min(args.max_pages, 3))
    total = 0
    for query in queries:
        result = collect_search(query, index, args.max_notes, max_pages=max_pages)
        if result == -2:
            print("Not authenticated. Run: xhs login", file=sys.stderr)
            break
        if result == -1:
            print(
                "Verification required. Complete verification, re-login with `xhs login`, "
                "then retry with --retry-failed.",
                file=sys.stderr,
            )
            break
        if result > 0:
            total += result
        time.sleep(args.sleep)

    print(f"Done. {total} new notes collected. Total notes: {len(index['notes'])}")
    print_cross_check_summary(index)


if __name__ == "__main__":
    main()
