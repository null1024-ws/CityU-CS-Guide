"""Search query variants for XHS collection — codes, titles, streams, and review phrasing."""

from __future__ import annotations

GLOBAL_QUERIES = [
    "城大 MSc CS 选课",
    "城市大学 计算机硕士 选课攻略",
    "CityU CS 硕士 课程评价",
    "城大计算机硕士 选课",
    "香港城市大学 CS 选课",
    "城大 CS 选课 锐评",
    "CityU MSCS 选课体验",
    "城大计算机硕士 SemA 选课",
    "城大计算机硕士 SemB 选课",
    "CityU CS course review",
    "港城 CS 硕士 避雷",
    "城大计算机 课评",
]

STREAM_QUERIES = {
    "AI": ["城大 CS AI stream 选课", "城大 人工智能 方向 选课"],
    "DS": ["城大 CS 数据科学 stream", "城大 大数据 选课"],
    "IS": ["城大 信息安全 stream 选课", "城大 网安 选课"],
}

# Chinese / English topic words students use besides course codes
COURSE_KEYWORDS: dict[str, list[str]] = {
    "CS5222": ["计算机网络", "network"],
    "CS5351": ["软件工程", "software engineering"],
    "CS5481": ["数据工程", "data engineering"],
    "CS5487": ["机器学习", "machine learning"],
    "CS6493": ["自然语言处理", "NLP"],
    "CS6535": ["AI guided study", "人工智能 导修"],
    "CS5286": ["搜索引擎", "web search"],
    "CS5296": ["云计算", "cloud computing"],
    "CS5489": ["机器学习 应用", "ML applications"],
    "CS6536": ["数据科学 导修", "data science guided"],
    "CS5293": ["信息安全", "information security"],
    "CS6290": ["隐私技术", "privacy"],
    "CS6537": ["信息安全 导修", "IS guided study"],
    "CS5188": ["虚拟现实", "VR"],
    "CS5367": ["游戏设计", "game design"],
    "CS6187": ["视觉语言", "vision language"],
    "CS6382": ["博弈论", "game theory"],
    "CS6487": ["机器学习 专题", "ML topics"],
    "CS6520": ["CS project 城大", "城大 CS 项目"],
    "CS6521": ["research project 城大", "城大 研究项目"],
    "CS6538": ["internship project 城大", "城大 实习项目"],
    "CS5491": ["人工智能", "artificial intelligence"],
    "CS5187": ["计算机视觉", "vision image"],
    "CS5486": ["智能系统", "intelligent systems"],
    "CS5483": ["数据仓库", "data mining"],
    "CS5488": ["大数据", "big data"],
    "CS5285": ["电商安全", "ecommerce security"],
    "CS5288": ["密码学", "cryptography"],
    "CS5294": ["安全管理", "security management"],
    "CS5182": ["计算机图形学", "computer graphics"],
    "CS5185": ["多媒体", "multimedia"],
    "CS5282": ["优化算法", "optimization"],
    "CS5348": ["软件质量", "software quality"],
    "CS6175": ["虚拟现实 游戏引擎", "VR game engine"],
    "CS6491": ["优化 应用", "optimization CS"],
    "EC5001": ["电子商务", "eCommerce"],
}


def short_title_phrase(title: str) -> str | None:
    """First meaningful chunk of English title for search."""
    if not title:
        return None
    # Drop parenthetical / subtitle after colon
    head = title.split(":")[0].strip()
    words = head.split()
    if len(words) >= 2:
        return " ".join(words[:3])
    return head if len(head) >= 4 else None


def queries_for_course(course: dict) -> list[str]:
    code = course["code"]
    stream = course.get("stream")
    keywords = list(COURSE_KEYWORDS.get(code, []))
    title_phrase = short_title_phrase(course.get("title", ""))
    if title_phrase and title_phrase.lower() not in {k.lower() for k in keywords}:
        keywords.append(title_phrase)

    candidates = [
        f"{code} 城大",
        f"{code} 城大CS",
        f"{code} CityU",
        f"城大{code}",
        f"{code} 选课",
        f"{code} 体验",
        f"{code} 评价",
        f"{code} 怎么样",
        f"{code} 避雷",
        f"{code} 给分",
        f"CityU {code}",
        f"港城 {code}",
    ]
    if stream:
        candidates.append(f"城大 {code} {stream}")
        candidates.extend(STREAM_QUERIES.get(stream, []))

    for kw in keywords[:3]:
        candidates.append(f"城大 {kw}")
        candidates.append(f"{code} {kw}")

    # Preserve order, dedupe
    seen: set[str] = set()
    out: list[str] = []
    for q in candidates:
        q = q.strip()
        if q and q not in seen:
            seen.add(q)
            out.append(q)
    return out


def build_queries(
    courses: list[dict],
    per_course: bool,
    course_filter: set[str] | None,
    skip_global: bool = False,
) -> list[str]:
    queries: list[str] = [] if skip_global else list(GLOBAL_QUERIES)
    if per_course:
        for course in courses:
            if course_filter and course["code"] not in course_filter:
                continue
            queries.extend(queries_for_course(course))
    elif course_filter:
        by_code = {c["code"]: c for c in courses}
        for code in sorted(course_filter):
            course = by_code.get(code, {"code": code, "title": ""})
            queries.extend(queries_for_course(course))

    seen: set[str] = set()
    deduped: list[str] = []
    for q in queries:
        if q not in seen:
            seen.add(q)
            deduped.append(q)
    return deduped
