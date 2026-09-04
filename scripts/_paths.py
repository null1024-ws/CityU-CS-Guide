"""Shared paths for CityU-CS-Guide pipeline."""

from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
COURSES_JSON = DATA / "courses.json"
REVIEWS_DIR = DATA / "reviews"
EDITORIAL_JSON = DATA / "editorial.json"
CHANGELOG_JSON = DATA / "changelog.json"
REVIEW_EDITOR_PROMPT = ROOT / "scripts" / "prompts" / "review_editor.md"
RAW_DIR = DATA / "raw"
RAW_XHS = RAW_DIR / "xhs"
RAW_IMAGES = RAW_DIR / "images"
RAW_OCR = RAW_DIR / "ocr"
RAW_BUNDLES = RAW_DIR / "bundles"
RAW_INDEX = RAW_DIR / "index.json"
SITE_DIST = ROOT / "site" / "dist"

SITE_REPO = "https://github.com/null1024-ws/CityU-CS-Guide"
PARTNER_REVIEW_SITE = "https://shanechen0722.github.io/cityu-CS-review/"
PARTNER_REVIEW_NAME = "CityU 课程资料库"
ORCA_ROUTER_URL = "https://www.orcarouter.ai/ref/ref_f97ea114d1bf7fd70092"
XHS_TOKEN_CACHE = Path.home() / ".xhs-cli" / "token_cache.json"

COURSE_CODE_RE = r"(?<![A-Za-z0-9])(CS\d{4}|EC5001)(?![A-Za-z0-9])"
CATALOGUE_YEAR = "202627"
CATALOGUE_BASE = f"https://www.cityu.edu.hk/catalogue/pg/{CATALOGUE_YEAR}/course"
MSC_CURRICULUM_URL = "https://www.cs.cityu.edu.hk/en/academic-programmes/msc-computer-science/curriculum/structures"


def catalogue_url(code: str) -> str:
    return f"{CATALOGUE_BASE}/{code.upper()}.htm"


def load_xsec_token(note_id: str) -> str:
    """Match xhs-cli: resolve xsec_token from ~/.xhs-cli/token_cache.json."""
    if not XHS_TOKEN_CACHE.exists():
        return ""
    try:
        cache = json.loads(XHS_TOKEN_CACHE.read_text(encoding="utf-8"))
        return str(cache.get(note_id, "") or "")
    except (OSError, json.JSONDecodeError):
        return ""


def resolve_note_url(note_id: str, url: str = "", *, search_item: dict | None = None) -> str:
    """Build explore URL with xsec_token when available (search item or token cache)."""
    note_id = note_id.split("#", 1)[0]
    if url and "xsec_token=" in url:
        return url.split("#", 1)[0]

    xsec = ""
    if search_item:
        note_card = search_item.get("note_card") or search_item.get("noteCard") or {}
        xsec = str(
            search_item.get("xsec_token")
            or search_item.get("xsecToken")
            or note_card.get("xsec_token")
            or ""
        )
    if not xsec:
        xsec = load_xsec_token(note_id)

    base = url.split("?", 1)[0].split("#", 1)[0] if url else f"https://www.xiaohongshu.com/explore/{note_id}"
    if note_id not in base:
        base = f"https://www.xiaohongshu.com/explore/{note_id}"
    return f"{base}?xsec_token={xsec}" if xsec else base


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
    """Prefer jackwener/xhs-cli (browser-based) over legacy xiaohongshu-cli."""
    pipx = (
        Path.home()
        / "AppData"
        / "Local"
        / "pipx"
        / "pipx"
        / "venvs"
        / "xhs-cli"
        / "Scripts"
        / "xhs.exe"
    )
    if pipx.exists():
        return str(pipx)
    local = Path.home() / ".local" / "bin" / "xhs.exe"
    if local.exists():
        return str(local)
    return "xhs"


def xhs_env() -> dict[str, str]:
    env = os.environ.copy()
    path_parts: list[str] = []
    pipx_scripts = (
        Path.home()
        / "AppData"
        / "Local"
        / "pipx"
        / "pipx"
        / "venvs"
        / "xhs-cli"
        / "Scripts"
    )
    if pipx_scripts.exists():
        path_parts.append(str(pipx_scripts))
    local_bin = Path.home() / ".local" / "bin"
    if local_bin.exists():
        path_parts.append(str(local_bin))
    if path_parts:
        env["PATH"] = ";".join(path_parts) + ";" + env.get("PATH", "")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return env
