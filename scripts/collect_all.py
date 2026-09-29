"""按栏目清单批量采集。部门站先采，信息公开最后，重复的制度以部门站版本为准。

    python -m scripts.collect_all [--pages 2] [--limit 150]
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
    args = ap.parse_args()

    rows = list(csv.DictReader(Path("meta/columns.csv").open(encoding="utf-8")))
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
