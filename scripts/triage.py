"""登记表分诊：把误收的附件/表格和重复条目标成 excluded，不删除数据。

    python -m scripts.triage          # 只报告
    python -m scripts.triage --apply  # 写回 documents.csv

去重是**跨部门**的：同一份制度在研究生处站和信息公开站各采到一次算重复，
保留版本更新的那份；年份相同时部门站优先，信息公开站重复的丢掉。
"""

import argparse
import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, ".")
from scripts.probe import FIELDS, MANUAL_WORDS, META, base_title, is_rule  # noqa: E402


def version_year(title, fallback=""):
    """标题里的修订年份优先，没有就用登记表年份。"""
    m = re.search(r"(20\d{2})\s*年?\s*(?:修订|版)", title or "")
    if m:
        return int(m.group(1))
    return int(fallback) if (fallback or "").isdigit() else 0


def rank(row):
    """版本新的排前面；同年份时部门站优先于信息公开站。"""
    return (version_year(row["title"], row["year"]), 0 if row["dept"] == "信息公开" else 1)


def dedupe(rows):
    """按 base_title 跨部门归并，返回被排除的行。"""
    groups = {}
    for r in rows:
        if r["status"] == "excluded":
            continue
        groups.setdefault(base_title(r["title"]), []).append(r)
    dup = []
    for group in groups.values():
        if len(group) < 2:
            continue
        group.sort(key=rank, reverse=True)
        for r in group[1:]:
            r["status"] = "excluded"
            dup.append(r)
    return dup


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    rows = list(csv.DictReader(META.open(encoding="utf-8")))
    not_rule = []
    for r in rows:
        if r["status"] != "excluded" and not is_rule(r["title"], MANUAL_WORDS):
            not_rule.append(r)
            r["status"] = "excluded"
    dup = dedupe(rows)

    print(f"总 {len(rows)} 条")
    print(f"  非制度条目（附件/表格/流程/模板）  {len(not_rule)}")
    for r in not_rule[:6]:
        print(f"      {r['dept']:<6}{r['title'][:40]}")
    print(f"  重复条目（跨部门同制度，保留新版）  {len(dup)}")
    for r in dup:
        print(f"      {r['dept']:<6}{r['year']:<7}{r['title'][:44]}")
    live = [r for r in rows if r["status"] != "excluded"]
    print(f"\n排除后可用 {len(live)} 条")

    if args.apply:
        META.write_text("", encoding="utf-8")
        with META.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            w.writeheader()
            w.writerows(rows)
        print(f"已写回 {META}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
