#!/usr/bin/env python3
"""Download images from collected XHS notes."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths import RAW_IMAGES, RAW_XHS, ensure_dirs  # noqa: E402


def extract_image_urls(note_data: dict) -> list[str]:
    urls: list[str] = []
    note = note_data.get("note") or {}
    for key in ("image_list", "images", "imageList"):
        val = note.get(key)
        if isinstance(val, list):
            for item in val:
                if isinstance(item, str):
                    urls.append(item)
                elif isinstance(item, dict):
                    for ukey in ("url", "url_default", "original", "info_list"):
                        u = item.get(ukey)
                        if isinstance(u, str):
                            urls.append(u)
                        elif isinstance(u, list):
                            for sub in u:
                                if isinstance(sub, dict) and sub.get("url"):
                                    urls.append(sub["url"])
    desc = note.get("desc") or note.get("content") or ""
    if isinstance(desc, str) and "http" in desc:
        pass
    return list(dict.fromkeys(urls))


def download_note_images(note_id: str, urls: list[str]) -> list[str]:
    out_dir = RAW_IMAGES / note_id
    out_dir.mkdir(parents=True, exist_ok=True)
    saved: list[str] = []
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.xiaohongshu.com/"}
    with httpx.Client(timeout=30, follow_redirects=True, headers=headers) as client:
        for i, url in enumerate(urls):
            ext = ".jpg"
            if ".png" in url.lower():
                ext = ".png"
            path = out_dir / f"{i}{ext}"
            if path.exists():
                saved.append(str(path))
                continue
            try:
                resp = client.get(url)
                resp.raise_for_status()
                path.write_bytes(resp.content)
                saved.append(str(path))
            except httpx.HTTPError as exc:
                print(f"  skip image {url}: {exc}", file=sys.stderr)
    return saved


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--note-id", help="Process single note")
    args = parser.parse_args()
    ensure_dirs()

    files = [RAW_XHS / f"{args.note_id}.json"] if args.note_id else sorted(RAW_XHS.glob("*.json"))
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        note_id = data.get("note_id") or path.stem
        urls = extract_image_urls(data)
        if not urls:
            continue
        print(f"Downloading {len(urls)} images for {note_id}")
        saved = download_note_images(note_id, urls)
        meta_path = RAW_IMAGES / note_id / "manifest.json"
        meta_path.write_text(json.dumps({"urls": urls, "saved": saved}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
