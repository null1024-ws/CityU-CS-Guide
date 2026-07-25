#!/usr/bin/env python3
"""Extract structured review fields from content bundles."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths import COURSE_CODE_RE, RAW_BUNDLES, REVIEWS_DIR, ensure_dirs, load_courses  # noqa: E402

CODE_PATTERN = re.compile(COURSE_CODE_RE, re.IGNORECASE)

FIELD_PATTERNS: dict[str, list[tuple[str, re.Pattern[str]]]] = {
    "difficulty": [
        ("easy", re.compile(r"水课|好水|无脑选|(?<![\u4e00-\u9fff])水(?![货类])|(?:课|难度|学起来|整体|总体).{0,10}简单|简单.{0,10}(?:课|难度)|不难|好拿|轻松(?=.*(?:课|整体|总体))", re.I)),
        ("medium", re.compile(r"适中|一般|中等|还行|难度不大|难度一般|没想象.*?难", re.I)),
        ("hard", re.compile(r"(?<![\u4e00-\u9fff])难(?![度听懂])|(?<![开闭])卷(?![卷])|很卷|太卷|卷课|硬核|劝退|地狱|崩溃|恶心|折磨|做不完|最难|难爆|吃力", re.I)),
    ],
    "grading": [
        ("generous", re.compile(r"给分.*?(高|好|松|友好|大方|慷慨|很高|不错)|高分|不压分|捞人|改卷.*?松|给分很高", re.I)),
        ("harsh", re.compile(r"压分|给分.*?(低|严|狠)|curve.*低|改.*?严|给分一般|给分太低", re.I)),
        ("fair", re.compile(r"给分.*?(正常|fair)", re.I)),
    ],
    "workload": [
        ("light", re.compile(r"作业(?:很|非常)?少|作业不算多|作业不多|工作量(?:很|非常)?小|事少|无作业|workload.*?小|工作量不大", re.I)),
        ("heavy", re.compile(r"作业(?:很|非常|比较|超)?多|作业不少|工作量大|熬夜|ddl.*?多|workload.*?大|繁琐", re.I)),
        ("medium", re.compile(r"作业.*?适中|工作量.*?一般|中等偏", re.I)),
    ],
    "hasRecording": [
        ("true", re.compile(r"有回放|有录播|有录像|recording|录课|开直播|zoom回放|每节课都有zoom|提供线上|线上课程", re.I)),
        ("false", re.compile(r"无回放|没有回放|不录|没录|无线上课", re.I)),
    ],
    "attendance": [
        ("strict", re.compile(r"点名|签到|考勤.*?严|查勤|查出勤", re.I)),
        ("not_strict", re.compile(r"不点名|考勤.*?松|不查|随便|无考勤|不考勤|不用去", re.I)),
    ],
    "examFormat": [
        ("open_book", re.compile(r"开卷|open.?book|可带资料|全开卷|半开卷|cheat\s*sheet|cheatsheet|小抄", re.I)),
        ("closed_book", re.compile(r"闭卷|closed.?book", re.I)),
        ("take_home", re.compile(r"take.?home|带回家", re.I)),
    ],
}

FIELD_LABELS = {
    "difficulty": {"easy": "简单", "medium": "适中", "hard": "较难"},
    "grading": {"generous": "给分友好", "fair": "给分一般", "harsh": "压分"},
    "workload": {"light": "轻松", "medium": "适中", "heavy": "繁重"},
    "hasRecording": {"true": "有回放", "false": "无回放", "unknown": "未知"},
    "attendance": {"strict": "考勤严", "not_strict": "考勤松", "unknown": "未知"},
    "examFormat": {"open_book": "开卷", "closed_book": "闭卷", "take_home": "Take-home", "unknown": "未知"},
}

CORRECTION_HINTS = re.compile(r"不对|错了|更正|其实|实际上|补充|纠正|楼主", re.I)
TOPIC_TAG_RE = re.compile(r"#[^#\s]+(?:\[话题\])?", re.I)
XHS_STICKER_RE = re.compile(r"\[[^\]]+\]")
EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0000FE00-\U0000FE0F"
    "]+",
    flags=re.UNICODE,
)
STAR_EMOJI_RE = re.compile(r"[🌟⭐✨]+")
EXEMPT_GUIDE_RE = re.compile(r"豁免攻略|课程豁免|申请豁免|免修攻略|课程辅导")
TUTOR_SPAM_RE = re.compile(
    r"预习辅导|厚台咨询|课程辅导|专属咨询|课业辅导|论文辅导|正规辅导|后台咨询|付费选课|辅无忧|课程预习|留学生论文",
    re.I,
)
REVIEW_SIGNAL_RE = re.compile(
    r"水|难|卷|作业|给分|压分|回放|录播|zoom|点名|考勤|开卷|闭卷|考试|tutorial|assignment|推荐|慎选|好课|劝退|体验|项目|期末|捞|workload|cheat",
    re.I,
)
TIP_NOISE_RE = re.compile(r"^(您好|请问|怎么选|哪个老师|蹲一个|学长\s*下学期)", re.I)
COURSE_TIP_RE = re.compile(r"(推荐|建议|必选|慎选|无脑选|闭眼选)", re.I)
TIP_PRAISE_FRAGMENT_RE = re.compile(
    r"^.{0,30}老师.{0,20}(好|不错|负责|捞|大好人|清楚|清晰|温柔|认真|给力|善良)",
    re.I,
)
DIFFICULTY_EASY_SKIP_RE = re.compile(
    r"想选.*简单|最简单的一|你想简单|选个简单|qual\s*exam|问题集|github|coursehero",
    re.I,
)
GRADING_EASY_SKIP_RE = re.compile(r"拿分|给分|得分|分数|考.{0,8}分", re.I)
OFF_TOPIC_COMMENT_RE = re.compile(
    r"guided\s*study|guide\s*study|暑(?:期|假)|旁听|绩点多少|github\.com|可以旁听",
    re.I,
)
OTHER_CODE_IN_SENTENCE_RE = re.compile(COURSE_CODE_RE, re.I)
MARKETING_RE = re.compile(r"专属咨询|付费选课|备考咨询|-付费")
COMMENT_NOISE_RE = re.compile(
    r"^(你好|请问|学长|姐妹|感谢|谢谢|这么狠|高水平|哈哈|蹲一个)",
    re.I,
)
ENGLISH_TITLE_HEADER_RE = re.compile(
    r"^(?:\d+\.\s*)?[A-Z][A-Za-z0-9 .&'()+/-]{8,70}$",
)


def strip_xhs_markup(text: str) -> str:
    text = TOPIC_TAG_RE.sub("", text)
    text = XHS_STICKER_RE.sub("", text)
    text = re.sub(r"#+\s*", "", text)
    text = re.sub(r"\s{2,}", " ", text).strip()
    return text


def normalize_review_line(line: str) -> str:
    line = strip_xhs_markup(line)
    line = STAR_EMOJI_RE.sub("", line)
    line = EMOJI_RE.sub("", line)
    line = re.sub(r"➕", "+", line)
    line = re.sub(r"^\*\s+", "", line)
    line = re.sub(r"^[·•▪️✅❌✔️🙅]\s*", "", line)
    line = re.sub(r"[:：]\s*$", "", line)
    line = re.sub(r"\s{2,}", " ", line).strip()
    return line


def consolidate_tips(tips: list[str], code: str) -> list[str]:
    """Merge short teacher-praise fragments into the main course recommendation tip."""
    normalized: list[str] = []
    for tip in tips:
        line = normalize_review_line(tip)
        if line and line not in normalized:
            normalized.append(line)
    if len(normalized) < 2:
        return normalized[:8]

    anchors: list[str] = []
    fragments: list[str] = []
    for tip in normalized:
        is_fragment = (
            code.upper() not in tip.upper()
            and len(tip) <= 30
            and TIP_PRAISE_FRAGMENT_RE.search(tip)
            and not COURSE_TIP_RE.search(tip)
        )
        if is_fragment:
            fragments.append(tip)
        else:
            anchors.append(tip)

    if anchors and fragments:
        primary_idx = next(
            (
                i
                for i, tip in enumerate(anchors)
                if COURSE_TIP_RE.search(tip) or code.upper() in tip.upper()
            ),
            0,
        )
        anchors[primary_idx] = anchors[primary_idx] + "；" + "；".join(fragments)
        return anchors[:8]

    return normalized[:8]


def is_noise_line(line: str) -> bool:
    if len(line) < 4:
        return True
    if MARKETING_RE.search(line):
        return True
    if re.fullmatch(r"[\W\d_]+", line):
        return True
    return False


def clean_excerpt(text: str, max_len: int = 680) -> str:
    lines: list[str] = []
    for raw_line in text.splitlines():
        line = normalize_review_line(raw_line)
        if is_noise_line(line):
            continue
        lines.append(line)
    text = "；".join(lines)
    text = re.sub(r"；{2,}", "；", text).strip("；")
    if len(text) > max_len:
        text = text[:max_len].rstrip() + "…"
    return text


def is_course_header_line(line: str, code: str) -> bool:
    upper = code.upper()
    before = r"(?:^|[\s#\].]|(?:\d+\.)\s*)"
    after = r"(?:\s|：|:|（|$|[^A-Za-z0-9])"
    return bool(re.search(rf"{before}{re.escape(upper)}{after}", line, re.I))


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"[。！？\n；;]+", text)
    return [p.strip() for p in parts if len(p.strip()) >= 4]


def is_non_code_course_header(line: str, current_code: str | None) -> bool:
    if not current_code:
        return False
    if current_code.upper() in line.upper():
        return False
    if re.search(r"[\u4e00-\u9fff，。！？；：]", line):
        return False
    return bool(ENGLISH_TITLE_HEADER_RE.match(line.strip()))


def is_exemption_guide(post_title: str) -> bool:
    return bool(EXEMPT_GUIDE_RE.search(post_title))


def is_tutor_spam(post_title: str, text: str) -> bool:
    return bool(TUTOR_SPAM_RE.search(f"{post_title}\n{text}"))


def is_weak_catalog_excerpt(excerpt: str, code: str) -> bool:
    """Drop excerpts that only name the course without review substance."""
    if len(excerpt) > 100:
        return False
    if REVIEW_SIGNAL_RE.search(excerpt):
        return False
    stripped = re.sub(re.escape(code), "", excerpt, flags=re.I)
    stripped = re.sub(r"[\s：:、，。；;·\-—（）()]", "", stripped)
    return len(stripped) < 18


def is_useful_comment(text: str, code: str) -> bool:
    t = text.strip()
    if len(t) < 12:
        return False
    if COMMENT_NOISE_RE.search(t):
        return False
    if code.upper() not in t.upper() and sentence_mentions_other_course(t, code):
        return False
    if re.search(r"(怎么选|何时选|什么时候|在哪看|可以选上|邮件联系|成绩界面)", t):
        if code.upper() not in t.upper():
            return False
    return True


def split_course_sections(text: str) -> list[tuple[str | None, str]]:
    """Split multi-course posts into (course_code, paragraph) sections."""
    sections: list[tuple[str | None, str]] = []
    current_code: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        nonlocal buffer, current_code
        if buffer:
            sections.append((current_code, "\n".join(buffer)))
            buffer = []

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        codes = CODE_PATTERN.findall(line)
        header_code = None
        for c in codes:
            if is_course_header_line(line, c):
                header_code = c.upper()
                break
        if header_code and (header_code != current_code or not buffer):
            flush()
            current_code = header_code
        elif is_non_code_course_header(line, current_code):
            flush()
            current_code = None
            continue
        elif current_code is None and not header_code:
            continue
        buffer.append(line)
    flush()
    return sections


def sentence_mentions_other_course(sentence: str, code: str) -> bool:
    for match in OTHER_CODE_IN_SENTENCE_RE.finditer(sentence):
        if match.group(0).upper() != code.upper():
            return True
    code_digits = re.sub(r"\D", "", code)
    for num in re.findall(r"(?<![A-Za-z0-9])(\d{4})(?![0-9])", sentence):
        if num != code_digits and num.startswith(("51", "52", "53", "54", "61", "62", "64", "65")):
            return True
    return False


def is_dedicated_course_post(post_title: str, code: str) -> bool:
    return code.upper() in post_title.upper()


def chunk_scope_for_code(chunk: dict, code: str, all_codes_in_note: list[str], post_title: str = "") -> bool:
    text = chunk["text"]
    if code.upper() in text.upper():
        return True
    if chunk.get("type") not in {"comment", "sub_comment"}:
        if len(all_codes_in_note) == 1 and all_codes_in_note[0].upper() == code.upper():
            return True
        return False
    if sentence_mentions_other_course(text, code):
        return False
    if OFF_TOPIC_COMMENT_RE.search(text):
        return False
    if not REVIEW_SIGNAL_RE.search(text):
        return False
    if is_dedicated_course_post(post_title, code):
        return True
    if len(all_codes_in_note) == 1 and all_codes_in_note[0].upper() == code.upper():
        return True
    return False


def extract_field_values(sentence: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for field, patterns in FIELD_PATTERNS.items():
        for value, pattern in patterns:
            if field == "difficulty" and value == "easy":
                if DIFFICULTY_EASY_SKIP_RE.search(sentence):
                    continue
                if GRADING_EASY_SKIP_RE.search(sentence) and pattern.search(sentence):
                    continue
            if pattern.search(sentence):
                found[field] = value
                break
    return found


def field_sentence_applies(sentence: str, code: str, chunk: dict, post_title: str) -> bool:
    if code.upper() in sentence.upper():
        return True
    if chunk.get("type") not in {"comment", "sub_comment"}:
        return True
    if sentence_mentions_other_course(sentence, code):
        return False
    if OFF_TOPIC_COMMENT_RE.search(sentence):
        return False
    if not REVIEW_SIGNAL_RE.search(sentence):
        return False
    return is_dedicated_course_post(post_title, code)


def process_text_block(
    text: str,
    code: str,
    note_id: str,
    url: str,
    chunk: dict,
    field_hits: dict,
    tips: list,
    post_sources: list,
    comment_sources: list,
    post_title: str = "",
) -> None:
    text = text.strip()
    if not text:
        return

    for sentence in split_sentences(text):
        if not field_sentence_applies(sentence, code, chunk, post_title):
            continue
        fields = extract_field_values(sentence)
        for field, value in fields.items():
            field_hits[field].append({
                "field": field,
                "value": value,
                "sentence": sentence[:300],
                "noteId": note_id,
                "url": url,
                "sourceRef": chunk.get("sourceRef", ""),
                "type": chunk.get("type", ""),
                "likes": chunk.get("likes", 0),
            })

        if len(sentence) >= 10 and any(k in sentence for k in ("建议", "推荐", "注意", "教授", "老师", "必选", "慎选", "总结")):
            if code.upper() in sentence.upper() or (
                chunk.get("type") in {"comment", "sub_comment"}
                and is_dedicated_course_post(post_title, code)
                and not OFF_TOPIC_COMMENT_RE.search(sentence)
                and not sentence_mentions_other_course(sentence, code)
            ):
                if not TIP_NOISE_RE.search(sentence.strip()):
                    tips.append(sentence[:200])

    excerpt = clean_excerpt(text)
    if len(excerpt) < 20:
        return
    if chunk.get("type") in {"post_body", "post_title", "ocr"} and is_weak_catalog_excerpt(excerpt, code):
        return

    src = {
        "noteId": note_id,
        "url": url,
        "excerpt": excerpt,
        "extractedFrom": [chunk.get("type", "text")],
    }
    if post_title:
        src["postTitle"] = normalize_review_line(post_title) or strip_xhs_markup(post_title)

    if chunk.get("type") in {"comment", "sub_comment"}:
        if not is_useful_comment(text, code):
            return
        role = "correction" if CORRECTION_HINTS.search(text) else "supplement"
        comment_sources.append({
            **src,
            "commentId": chunk.get("commentId", chunk.get("sourceRef", "")),
            "author": chunk.get("author", ""),
            "likes": chunk.get("likes", 0),
            "role": role,
        })
    elif chunk.get("type") in {"post_body", "post_title", "ocr"}:
        post_sources.append(src)


def process_bundles(bundles: list[dict], code: str) -> dict:
    field_hits: dict[str, list[dict]] = defaultdict(list)
    tips: list[str] = []
    post_sources: list[dict] = []
    comment_sources: list[dict] = []

    for bundle in bundles:
        note_id = bundle["note_id"]
        url = bundle.get("url", "")
        codes = bundle.get("course_codes") or []
        chunks = bundle.get("chunks", [])
        post_title = next((c["text"] for c in chunks if c.get("type") == "post_title"), "")
        if is_exemption_guide(post_title):
            continue
        full_text = " ".join(c["text"] for c in chunks)
        if is_tutor_spam(post_title, full_text):
            continue
        if code.upper() not in [c.upper() for c in codes] and code.upper() not in full_text.upper():
            continue

        for chunk in chunks:
            chunk_type = chunk.get("type", "")
            if chunk_type in {"post_body", "ocr"}:
                for section_code, section_text in split_course_sections(chunk["text"]):
                    if section_code and section_code.upper() != code.upper():
                        continue
                    if not section_code:
                        if code.upper() not in section_text.upper():
                            continue
                    process_text_block(
                        section_text, code, note_id, url, chunk,
                        field_hits, tips, post_sources, comment_sources,
                        post_title=post_title,
                    )
            elif chunk_type == "post_title":
                continue
            elif chunk_scope_for_code(chunk, code, codes, post_title=post_title):
                process_text_block(
                    chunk["text"], code, note_id, url, chunk,
                    field_hits, tips, post_sources, comment_sources,
                    post_title=post_title,
                )

    post_sources.sort(key=lambda s: len(s.get("excerpt", "")), reverse=True)
    comment_sources.sort(key=lambda s: len(s.get("excerpt", "")), reverse=True)

    return {
        "courseCode": code,
        "field_hits": dict(field_hits),
        "tips": consolidate_tips(list(dict.fromkeys(tips)), code),
        "post_sources": post_sources[:8],
        "comment_sources": comment_sources[:8],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    args = parser.parse_args()
    ensure_dirs()
    courses = load_courses()

    bundle_files = sorted(RAW_BUNDLES.glob("*.json"))
    bundles = [json.loads(p.read_text(encoding="utf-8")) for p in bundle_files]

    for course in courses:
        code = course["code"]
        extracted = process_bundles(bundles, code)
        out_path = REVIEWS_DIR / f"{code}.json"
        out_path.write_text(json.dumps(extracted, indent=2, ensure_ascii=False), encoding="utf-8")
        hit_count = sum(len(v) for v in extracted["field_hits"].values())
        print(f"{code}: {hit_count} field hits, {len(extracted['post_sources'])} post sources, {len(extracted['comment_sources'])} comment sources")

    print("Run credibility_score.py next to finalize reviews.")


if __name__ == "__main__":
    main()
