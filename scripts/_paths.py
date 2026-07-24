"""Shared paths for CityU-CS-Guide pipeline."""

from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
COURSES_JSON = DATA / "courses.json"
REVIEWS_DIR = DATA / "reviews"
RAW_DIR = DATA / "raw"
RAW_XHS = RAW_DIR / "xhs"
RAW_IMAGES = RAW_DIR / "images"
RAW_OCR = RAW_DIR / "ocr"
RAW_BUNDLES = RAW_DIR / "bundles"
RAW_INDEX = RAW_DIR / "index.json"
SITE_DIST = ROOT / "site" / "dist"

SITE_REPO = "https://github.com/null1024-ws/CityU-CS-Guide"

COURSE_CODE_RE = r"(?<![A-Za-z0-9])(CS\d{4}|EC5001)(?![A-Za-z0-9])"
CATALOGUE_YEAR = "202627"
CATALOGUE_BASE = f"https://www.cityu.edu.hk/catalogue/pg/{CATALOGUE_YEAR}/course"
MSC_CURRICULUM_URL = "https://www.cs.cityu.edu.hk/en/academic-programmes/msc-computer-science/curriculum/structures"


def catalogue_url(code: str) -> str:
    return f"{CATALOGUE_BASE}/{code.upper()}.htm"


def ensure_dirs() -> None:
    for path in (REVIEWS_DIR, RAW_XHS, RAW_IMAGES, RAW_OCR, RAW_BUNDLES, SITE_DIST):
        path.mkdir(parents=True, exist_ok=True)


def load_courses() -> list[dict]:
    return json.loads(COURSES_JSON.read_text(encoding="utf-8"))


def load_raw_index() -> dict:
    if not RAW_INDEX.exists():
        return {"searches": [], "notes": {}, "checkpoint": {}}
    return json.loads(RAW_INDEX.read_text(encoding="utf-8"))


def save_raw_index(index: dict) -> None:
    RAW_INDEX.parent.mkdir(parents=True, exist_ok=True)
    RAW_INDEX.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")


def xhs_bin() -> str:
    local = Path.home() / ".local" / "bin" / "xhs.exe"
    if local.exists():
        return str(local)
    return "xhs"


def xhs_env() -> dict[str, str]:
    env = os.environ.copy()
    local_bin = Path.home() / ".local" / "bin"
    if local_bin.exists():
        env["PATH"] = f"{local_bin};{env.get('PATH', '')}"
    return env
