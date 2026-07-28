# CityU MSc CS 选课参考

香港城市大学 MSc CS 课程的小红书评价汇总，配合 [CityU 官方课纲](https://www.cs.cityu.edu.hk/en/academic-programmes/msc-computer-science/curriculum/structures)。

**非官方参考** — 请以学校通知为准。

在线访问：<https://null1024-ws.github.io/CityU-CS-Guide/>

## 内容

- 36 门课程：难度、给分、作业量、回放、考勤、考试形式
- 帖子来源 + 评论区补充，附可信度标签（多源一致 / 单源提及 / 存疑）
- 每条评价可跳转原帖核对

## 本地预览

```powershell
python scripts/build_site.py --local
start site/dist/index.html
```

## 数据流水线

```
xhs_collect.py  →  data/raw/xhs/          原始笔记 JSON
content_bundle  →  data/raw/bundles/       正文 + 评论合并
review_extract  →  data/reviews/          结构化字段与摘录
credibility_score                      可信度打分
build_site.py   →  site/dist/            静态站点
audit_reviews.py                       一致性与广告过滤检查
```

一键运行（不含采集）：

```powershell
python scripts/run_pipeline.py
python scripts/build_site.py --local
```

## 采集数据

依赖 [xhs-cli](https://github.com/jackwener/xhs-cli)（Camoufox 浏览器模式，稳定性优于逆向 API）：

```powershell
pipx install xhs-cli
python -m camoufox fetch
xhs login
xhs status
```

采集示例（保守限速，支持断点续跑）：

```powershell
python scripts/xhs_collect.py --per-course --skip-global --max-notes 2 --sleep 8
python scripts/run_pipeline.py
python scripts/build_site.py --local
```

补采尚无来源的课程（优先 `sourceCount=0`，可重试已搜过仍空的课）：

```powershell
python scripts/xhs_collect.py --per-course --skip-global --prioritize-empty --retry-empty `
  --courses CS5185,CS5282,CS5348,CS6175 --max-notes 3 --sleep 8
```

- `--prioritize-empty`：先跑暂无来源 / 暂无字段结论的课程
- `--retry-empty`：清零这些课的 checkpoint，便于提高 `--max-notes` 后再搜
- 进度与恢复命令见 `data/raw/index.json` → `checkpoint.batch_progress`

Cookie 保存在 `~/.xhs-cli/cookies.json`。若 QR 登录触发风控，可从浏览器 DevTools 复制 `a1` 与 `web_session`：

```powershell
xhs login --cookie "a1=...; web_session=..."
```

## 可信度说明

| 标签 | 含义 |
|------|------|
| **多源一致** | ≥2 篇独立帖子说法一致，或帖子与评论区相互印证 |
| **单源提及** | 仅 1 篇来源，或同一帖子内重复提及 |
| **存疑** | 不同来源说法冲突 |
| **暂无数据** | 未找到有效评价摘录 |

流水线会自动过滤：豁免攻略、课业辅导广告、仅列出课号无实质内容的帖子；评论区会剔除纯提问（如「有了解不」）、社交灌水（同问/插眼/+1）及无课评信号的评论。运行 `python scripts/audit_reviews.py` 可检查剩余来源与 bundle 是否一致。

## 项目结构

| 路径 | 说明 |
|------|------|
| `data/courses.json` | 36 门课程元数据 |
| `data/raw/xhs/` | xhs-cli 原始抓取 |
| `data/raw/bundles/` | 合并后的文本块 |
| `data/reviews/` | 每课评价 JSON |
| `scripts/xhs_collect.py` | 采集器（多关键词 + 交叉验证 + 空课优先） |
| `scripts/search_queries.py` | 全局/按课搜索词 |
| `scripts/content_bundle.py` | 解析 xhs-cli JSON（含 camelCase 字段） |
| `scripts/review_extract.py` | 正则抽取 + 摘录清洗 |
| `scripts/credibility_score.py` | 多源一致性打分 |
| `scripts/build_site.py` | 生成静态页 |
| `scripts/audit_reviews.py` | 审阅脚本 |

## 部署

推送到 `main` 后 GitHub Actions 自动部署 Pages。

## 致谢

本站页面样式基于 [Kami](https://github.com/tw93/kami)（tw93）— 纸感阅读主题，由 `scripts/build_site.py` 生成静态页时沿用其排版与视觉风格。感谢作者开源。

## 免责声明

本站信息来自小红书社区，未经 CityU 官方核实。选课请以学校通知与课程大纲为准。
