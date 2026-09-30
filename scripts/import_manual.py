"""人工汇编增量导入：把手工整理的 docx 里自动化流水线漏掉的制度补进语料。

    python -m scripts.import_manual            # 只报告要补什么
    python -m scripts.import_manual --apply    # 写 data/raw/manual/ 并追加进 meta/documents.csv
    python -m scripts.import_manual --check    # 断言关键增量在场，供 CI/自查

只补增量，重复的一律丢弃；已经存在于 meta/documents.csv 的标题（含 excluded）不再入库。
"""

import argparse
import csv
import hashlib
import re
import sys
from pathlib import Path

sys.path.insert(0, ".")
from scripts.probe import FIELDS, MANUAL_WORDS, META, base_title, is_rule  # noqa: E402

# 信息公开栏目里的公示、名单、招生信息按既定口径不收
EXCLUDE = re.compile(r"招生|春招|秋招|转段|自主测试|贯通|专升本|三校生|插班生|考试|录取|"
                   r"名单|公示|一览表|分数线|简章|公告|大纲|查询|报告|结果|简介|议程")
NUMBERING = re.compile(r"^\s*\d+\s*[.、)）]\s*")
DEPT = "人工整理"

SOURCES = [
    Path.home() / "Desktop/上海第二工业大学-学校基本情况-规章制度汇编.docx",
    Path.home() / "Desktop/上海第二工业大学-学生事务管理-规章制度汇编.docx",
    Path.home() / "Desktop/上海第二工业大学-教师人事-规章制度汇编.docx",
    Path.home() / "Desktop/上海第二工业大学-规划计划-文件汇编.docx",
    Path.home() / "Desktop/上海第二工业大学信息公开网_教学管理_科研管理_普通高校招生信息_汇编.docx",
    Path.home() / "Desktop/新建 DOCX 文件.docx",
    Path.home() / "Desktop/校园制度.docx",
    *sorted((Path.home() / "Downloads/监督工作,后勤保障和特色栏目").glob("*.docx")),
]

DATE_RE = re.compile(r"发布(?:日期|时间)[:：]\s*([\d\-./]+)")
SRC_RE = re.compile(r"来源[:：]\s*(\S+)")
DOC_NO_RE = re.compile(r"[〔\[]\s*(20\d{2})\s*[〕\]]\s*\d+\s*号")


def paragraphs(path):
    import docx

    return [p.text.strip() for p in docx.Document(str(path)).paragraphs]


def split_doc(ps):
    """切出 [(title, meta_line, body)]。有「发布日期：」的按标记切，没有的整篇算一份。"""
    marks = [i for i, t in enumerate(ps) if t.startswith(("发布日期", "发布时间"))]
    if not marks:
        body = [t for t in ps if t]
        return [(body[0], "", "\n".join(body[1:]))] if body else []
    out = []
    for n, i in enumerate(marks):
        title = next((ps[j] for j in range(i - 1, max(-1, i - 4), -1) if ps[j]), "")
        end = len(ps)
        if n + 1 < len(marks):
            j = marks[n + 1]
            end = next((k for k in range(j - 1, max(-1, j - 4), -1) if ps[k]), j)
        out.append((title, ps[i], "\n".join(ps[i + 1:end])))
    return out


def make_row(title, body, meta_line, fallback_doc_no=""):
    m = DOC_NO_RE.search(fallback_doc_no or body[:400]) or DOC_NO_RE.search(title)
    date = DATE_RE.search(meta_line)
    publish = date.group(1).replace("/", "-").replace(".", "-") if date else ""
    src = SRC_RE.search(meta_line)
    src = src.group(1) if src and src.group(1).startswith("http") else ""
    year = publish[:4] if publish[:4].isdigit() else ""
    if not year:
        y = re.search(r"(20\d{2})", title)
        year = y.group(1) if y else "unknown"
    safe = re.sub(r"[/\\:*?\"<>|\s]", "", title)[:80]
    return {
        "doc_id": hashlib.md5(f"{title}|{src}".encode()).hexdigest()[:12],
        "dept": DEPT, "title": title,
        "doc_no": m.group(0).replace(" ", "") if m else "",
        "year": year, "publish_date": publish,
        "source_url": src, "page_url": "",
        "format": "txt", "is_scanned": "false", "pages": "",
        "status": "effective",
        "local_path": f"data/raw/manual/{year}/manual_{safe}_{year}.txt",
        "fetched_at": "2026-09-30 (人工整理)",
    }, body


def collect():
    rows = list(csv.DictReader(META.open(encoding="utf-8")))
    have = {base_title(r["title"]) for r in rows}  # 含 excluded，避免把分诊丢掉的又捞回来
    new, seen, stat = [], set(), []
    for path in SOURCES:
        if not path.exists():
            print(f"  缺文件，跳过：{path}", file=sys.stderr)
            continue
        ps = paragraphs(path)
        got = 0
        for title, meta_line, body in split_doc(ps):
            title = NUMBERING.sub("", title).strip()
            key = base_title(title)
            if not key or key in seen or key in have:
                continue
            if EXCLUDE.search(title) or not is_rule(title, MANUAL_WORDS):
                continue
            seen.add(key)
            row, body = make_row(title, body, meta_line, " ".join(ps[:6]))
            if len(body.strip()) < 120:
                continue
            new.append((row, body))
            got += 1
        stat.append((path.name, len(split_doc(ps)), got))
    return rows, new, stat


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    rows, new, stat = collect()
    print(f"人工源文件 {len(stat)} 个，已入库 {len(rows)} 条")
    for name, total, got in stat:
        print(f"  {name[:44]:<46} 识别 {total:>3}  增量 {got}")
    print(f"\n去重+口径过滤后增量 {len(new)} 条：")
    for row, body in new:
        print(f"  [{row['year']}] {row['title'][:52]}  ({len(body)} 字)")

    if args.check:
        keys = {base_title(r["title"]) for r, _ in new}
        must = {"上海第二工业大学教育发展“十四五”规划", "上海第二工业大学2024年党政工作要点",
                "上海第二工业大学推进依法治校工作方案", "上海第二工业大学学生公寓服务管理规范"}
        missing = must - keys
        assert not missing, f"关键增量缺失：{missing}"
        assert len(new) >= 12, f"增量少于预期（{len(new)}）"
        assert not any(EXCLUDE.search(r["title"]) for r, _ in new), "招生/公示类混进增量"
        print("\n--check 通过")
        return 0

    if not args.apply:
        print("\n（预演，加 --apply 才会写入）")
        return 0

    for row, body in new:
        p = Path(row["local_path"])
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
    with META.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        for row, _ in new:
            w.writerow(row)
    print(f"\n已写入 {len(new)} 份正文到 data/raw/manual/，meta/documents.csv 追加 {len(new)} 行")
    print("下一步：python -m scripts.build_corpus")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
