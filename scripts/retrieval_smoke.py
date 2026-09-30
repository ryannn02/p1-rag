"""阶段 3 冒烟：20 条问题跑检索基线，出 Recall@5 并写明细。

    python -m scripts.retrieval_smoke [--k 5]

口径：top-k 里任一 chunk 的 doc_id 命中标注的制度文件即算命中（标注到制度级，
不标到具体段落——同一事实在长篇制度里可能落在相邻条款）。明细进
reports/retrieval_smoke.csv，漏掉的题会单独列出来。
"""

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, ".")
from src.p1.retriever import Retriever  # noqa: E402

QUESTIONS = Path("eval/smoke_questions.jsonl")
REPORT = Path("reports/retrieval_smoke.csv")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--per-doc", type=int, default=2,
                    help="同一份文件最多占几席，0 表示不限制")
    ap.add_argument("--questions", type=Path, default=QUESTIONS)
    args = ap.parse_args()

    questions = [json.loads(l) for l in args.questions.read_text(encoding="utf-8").splitlines() if l.strip()]
    r = Retriever()
    print(f"索引 {r.vecs.shape[0]} 条 × {r.vecs.shape[1]} 维，模型 {r.manifest['model']}")
    print(f"跑 {len(questions)} 条问题，k={args.k}，同文件上限 {args.per_doc or '不限'}\n")

    rows, misses = [], []
    for q in questions:
        hits = r.search(q["question"], k=args.k, per_doc=args.per_doc or None)
        rank = next((h["rank"] for h in hits if h["doc_id"] == q["doc_id"]), 0)
        top = hits[0]
        rows.append({
            "id": q["id"], "question": q["question"],
            "expected_doc_id": q["doc_id"], "expected_title": q["title"],
            "hit": "Y" if rank else "N", "rank": rank or "",
            "top1_doc_id": top["doc_id"], "top1_title": top["title"],
            "top1_score": f"{top['score']:.4f}",
        })
        if not rank:
            misses.append((q, hits))

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    with REPORT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    hit = sum(1 for x in rows if x["hit"] == "Y")
    print(f"Recall@{args.k} = {hit}/{len(rows)} = {hit / len(rows):.0%}")
    if misses:
        print(f"\n漏掉的 {len(misses)} 条：")
        for q, hits in misses:
            print(f"  {q['id']} {q['question'][:38]}")
            print(f"      应为：{q['title'][:40]}")
            for h in hits[:2]:
                print(f"      实得：{h['score']:.3f} {h['title'][:40]}")
    print(f"\n明细：{REPORT}")
    return 0 if not misses else 1


if __name__ == "__main__":
    raise SystemExit(main())
