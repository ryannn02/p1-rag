"""登记表统计：验收口径的一键检查（总数、扫描件占比、按部门与格式分布）。"""

import csv
from collections import Counter
from pathlib import Path

rows = list(csv.DictReader(Path("meta/documents.csv").open(encoding="utf-8")))
total = len(rows)
scanned = sum(1 for r in rows if r["is_scanned"] == "true")

print(f"总条目      {total}")
if total:
    print(f"扫描件      {scanned}  ({scanned / total * 100:.1f}%)   目标 ≤20%")
    print(f"现行有效    {sum(1 for r in rows if r['status'] == 'effective')}")
print("\n按部门：")
for dept, n in Counter(r["dept"] for r in rows).most_common():
    print(f"  {dept:<10}{n:>5}")
print("\n按格式：")
for fmt, n in Counter(r["format"] for r in rows).most_common():
    print(f"  {fmt:<10}{n:>5}")
