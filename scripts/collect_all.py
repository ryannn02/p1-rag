"""按栏目清单批量采集。部门站先采，信息公开最后，重复的制度以部门站版本为准。

    python -m scripts.collect_all [--pages 2] [--limit 150]

`--min-rules 1` 只跑首页出现过文种词的栏目：764 个栏目里只有 107 个有，
翻页深度加大时能把请求量压到十分之一。栏目首页没出现文种词不代表后面几页
没有，所以补采时值得先用 0 全跑一遍、再用 1 加深翻页。
"""

import argparse
import csv
import subprocess
import sys
from pathlib import Path

ORDER = ["教务处", "财务处", "保卫处", "研究生处", "学生处", "后勤保障处", "信息公开"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=2)
    ap.add_argument("--limit", type=int, default=150)
    ap.add_argument("--only", default="", help="只跑某个部门，逗号分隔")
    ap.add_argument("--min-rules", type=int, default=0,
                    help="只跑 rule_count >= N 的栏目，0 表示全跑")
    args = ap.parse_args()

    rows = list(csv.DictReader(Path("meta/columns.csv").open(encoding="utf-8")))
    if args.min_rules:
        before = len(rows)
        rows = [r for r in rows if int(r["rule_count"] or 0) >= args.min_rules]
        print(f"按 rule_count >= {args.min_rules} 过滤：{before} -> {len(rows)} 个栏目")
    if args.only:
        want = args.only.split(",")
    else:
        seen = {r["dept"] for r in rows}
        want = [d for d in ORDER if d in seen] + sorted(seen - set(ORDER))

    for dept in want:
        cols = [r for r in rows if r["dept"] == dept]
        print(f"\n########## {dept}（{len(cols)} 个栏目） ##########", flush=True)
        for r in cols:
            cmd = [sys.executable, "-m", "scripts.probe", r["url"], "--dept", dept,
                   "--pages", str(args.pages), "--limit", str(args.limit)]
            subprocess.run(cmd, check=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
