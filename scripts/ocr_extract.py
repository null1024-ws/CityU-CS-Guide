#!/usr/bin/env python3
"""OCR downloaded note images with EasyOCR."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths import RAW_IMAGES, RAW_OCR, ensure_dirs  # noqa: E402


def ocr_image(reader, path: Path) -> tuple[str, float]:
    results = reader.readtext(str(path))
    lines = []
    confidences = []
    for _bbox, text, conf in results:
        lines.append(text)
        confidences.append(float(conf))
    avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
    return "\n".join(lines), avg_conf


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--note-id", help="Process single note")
    args = parser.parse_args()

    try:
        import easyocr
    except ImportError:
        print("Install easyocr: pip install easyocr", file=sys.stderr)
        sys.exit(1)

    ensure_dirs()
    reader = easyocr.Reader(["ch_sim", "en"], gpu=False)

    note_dirs = [RAW_IMAGES / args.note_id] if args.note_id else sorted(p for p in RAW_IMAGES.iterdir() if p.is_dir())
    for note_dir in note_dirs:
        note_id = note_dir.name
        images = sorted(p for p in note_dir.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"})
        if not images:
            continue
        print(f"OCR {note_id}: {len(images)} images")
        pages = []
        for img in images:
            text, conf = ocr_image(reader, img)
            pages.append({"file": img.name, "text": text, "confidence": round(conf, 3)})
        out = {"note_id": note_id, "pages": pages, "full_text": "\n\n".join(p["text"] for p in pages if p["text"])}
        (RAW_OCR / f"{note_id}.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
