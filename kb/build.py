#!/usr/bin/env python3
"""知识库索引：扫描 kb/*.md，生成 kb/index.json（网页用）和 kb/README.md（GitHub 上看的目录 + 更新日志）。

每篇文章开头可以写（都可省略）：
    ---
    title: 标题            # 省略时用第一行「# 标题」，再没有就用文件名
    tags: [物流, 算法]      # 也可以写成 tags: 物流, 算法
    summary: 一句话简介     # 省略时取正文第一段
    ---
日期来自 git：第一次提交 = 创建，最后一次提交 = 更新；还没提交的文件用今天。
只用标准库，GitHub Actions 和家里主机都能直接跑。
"""
import datetime
import json
import os
import re
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SKIP = {"README.md"}


def parse(text):
    meta, body = {}, text
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?", text, re.S)
    if m:
        body = text[m.end():]
        for line in m.group(1).splitlines():
            if ":" not in line or line.lstrip().startswith("#"):
                continue
            k, v = line.split(":", 1)
            k, v = k.strip().lower(), v.strip()
            if k == "tags":
                v = [t.strip().strip("'\"#") for t in v.strip("[]").split(",") if t.strip().strip("'\"#")]
            else:
                v = v.strip("'\"")
            meta[k] = v
    return meta, body


def plain(md):
    """Markdown → 纯文本（给搜索和简介用）。"""
    s = re.sub(r"```.*?```", " ", md, flags=re.S)
    s = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", s)
    s = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", s)
    s = re.sub(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", lambda m: m.group(2) or m.group(1), s)
    s = re.sub(r"^[#>\-*+|\s]+", "", s, flags=re.M)
    s = re.sub(r"[`*_|]+", "", s)
    return re.sub(r"\s+", " ", s).strip()


def git_dates(path):
    rel = os.path.relpath(path, ROOT)
    try:
        out = subprocess.run(["git", "log", "--follow", "--format=%cs", "--", rel], cwd=ROOT,
                             capture_output=True, text=True, timeout=20).stdout.split()
    except Exception:
        out = []
    today = datetime.date.today().isoformat()
    if not out:
        return today, today
    dirty = subprocess.run(["git", "status", "--porcelain", "--", rel], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    return out[-1], (today if dirty else out[0])


def main():
    arts = []
    for name in sorted(os.listdir(HERE)):
        if not name.endswith(".md") or name in SKIP or name.startswith(("_", ".")):
            continue
        path = os.path.join(HERE, name)
        with open(path, encoding="utf-8") as f:
            meta, body = parse(f.read())
        h1 = re.search(r"^#\s+(.+)$", body, re.M)
        title = meta.get("title") or (h1.group(1).strip() if h1 else name[:-3])
        text = plain(body)
        summary = meta.get("summary")
        if not summary:
            first = next((p for p in re.split(r"\n\s*\n", body) if p.strip() and not p.lstrip().startswith(("#", "```", "|", ">"))), "")
            summary = plain(first)[:90]
        created, updated = git_dates(path)
        tags = meta.get("tags") or []
        if isinstance(tags, str):
            tags = [tags]
        arts.append({
            "slug": name[:-3], "title": title, "tags": tags, "summary": summary,
            "created": meta.get("created") or created, "updated": meta.get("updated") or updated,
            "words": len(re.sub(r"\s", "", text)), "text": text[:20000],
        })
    arts.sort(key=lambda a: (a["updated"], a["created"]), reverse=True)

    tags = {}
    for a in arts:
        for t in a["tags"]:
            tags[t] = tags.get(t, 0) + 1
    tag_list = sorted(tags.items(), key=lambda x: (-x[1], x[0]))
    with open(os.path.join(HERE, "index.json"), "w", encoding="utf-8") as f:
        json.dump({"tags": [t for t, _ in tag_list], "articles": arts}, f, ensure_ascii=False, separators=(",", ":"))

    # README：GitHub 上打开 kb/ 文件夹就能看到的目录
    L = ["# 📚 知识库", "",
         "长一点的科普和笔记，一篇一个 `.md` 文件。网页版：[kb.html](https://boliunew.github.io/tools/kb.html)。", "",
         "**写新文章**：在这个文件夹里新建 `英文小写-连字符.md`，开头写 `title` / `tags` / `summary`（可参考 [_template.md](_template.md)），推上去后目录会自动更新。"
         "这是公开仓库，私人笔记别放这里。", "",
         "> 这个文件由 `kb/build.py` 自动生成，手改会被覆盖。", ""]
    L += ["## 按标签", ""]
    for t, n in tag_list:
        L.append("**%s**（%d）：%s" % (t, n, " · ".join("[%s](%s.md)" % (a["title"], a["slug"]) for a in arts if t in a["tags"])))
        L.append("")
    untagged = [a for a in arts if not a["tags"]]
    if untagged:
        L += ["**未分类**：" + " · ".join("[%s](%s.md)" % (a["title"], a["slug"]) for a in untagged), ""]
    L += ["## 更新日志", ""]
    for a in arts[:30]:
        kind = "新增" if a["created"] == a["updated"] else "更新"
        L.append("- %s %s [%s](%s.md)" % (a["updated"], kind, a["title"], a["slug"]))
    L.append("")
    with open(os.path.join(HERE, "README.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print("%d 篇，%d 个标签 → kb/index.json, kb/README.md" % (len(arts), len(tag_list)))


if __name__ == "__main__":
    main()
