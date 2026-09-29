"""登记表分诊：把误收的附件/表格和重复条目标成 excluded，不删除数据。

    python -m scripts.triage          # 只报告
    python -m scripts.triage --apply  # 写回 documents.csv
"""

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, ".")
from scripts.probe import FIELDS, META, base_title, is_rule  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    rows = list(csv.DictReader(META.open(encoding="utf-8")))
    seen, not_rule, dup = {}, [], []
    for r in rows:
        if r["status"] == "excluded":
            continue
        if not is_rule(r["title"]):
            not_rule.append(r)
            r["status"] = "excluded"
            continue
        key = (r["dept"], base_title(r["title"]))
        if key in seen:
            dup.append(r)
            r["status"] = "excluded"
        else:
            seen[key] = r

    print(f"总 {len(rows)} 条")
    print(f"  非制度条目（附件/表格/流程/模板）  {len(not_rule)}")
    for r in not_rule[:6]:
        print(f"      {r['dept']:<6}{r['title'][:40]}")
    print(f"  同部门重复条目                    {len(dup)}")
    for r in dup[:6]:
        print(f"      {r['dept']:<6}{r['title'][:40]}")
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
