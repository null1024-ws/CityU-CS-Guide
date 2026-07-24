# CityU MSc CS 选课参考

香港城市大学 MSc CS 课程的小红书评价汇总，配合 [CityU 官方课纲](https://www.cs.cityu.edu.hk/en/academic-programmes/msc-computer-science/curriculum/structures)。

**非官方参考** — 请以学校通知为准。

在线访问：<https://null1024-ws.github.io/CityU-CS-Guide/>

## 内容

- 36 门课程：难度、给分、作业量、回放、考勤、考试形式
- 帖子来源 + 评论区补充，附可信度标签

## 本地预览

```powershell
python scripts/build_site.py --local
start site/dist/index.html
```

## 更新数据

采集依赖 [xiaohongshu-cli](https://github.com/jackwener/xiaohongshu-cli)（`pip install xiaohongshu-cli` 或 `uv tool install xiaohongshu-cli`）。

```powershell
xhs login --qrcode
python scripts/xhs_collect.py --global-only
python scripts/content_bundle.py
python scripts/review_extract.py
python scripts/credibility_score.py
python scripts/build_site.py
```

推送到 `main` 后 GitHub Actions 自动部署 Pages。
