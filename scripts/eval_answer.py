"""阶段 4 验收：prompts/answer/cases.jsonl 打真模型，核对引用与拒答。

    python -m scripts.eval_answer [--k 5]

每条用例核对三件事：拒答与否是否符合预期、引用文件是否命中、答案是否含
关键数字。明细进 reports/answer_eval.csv。需要 .env 里的 LLM_API_KEY。
"""

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, ".")
from p1.generator import answer  # noqa: E402
from p1.retriever import Retriever  # noqa: E402

CASES = Path("prompts/answer/cases.jsonl")
REPORT = Path("reports/answer_eval.csv")


def check(res, exp):
    fails = []
    if bool(exp["refused"]) != res.refused:
        fails.append(f"拒答应为 {exp['refused']}，实得 {res.refused}")
    if res.refused:
        if exp["refused"] and not res.suggested_contact:
            fails.append("拒答没给归口部门")
        return fails
    cited = " ".join(c.file for c in res.citations)
    if exp["must_cite_any"] and not any(t in cited for t in exp["must_cite_any"]):
        fails.append(f"引用不对：{cited or '（无引用）'}")
    for t in exp["must_contain"]:
        if t not in res.answer:
            fails.append(f"答案缺「{t}」")
    return fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=5)
    args = ap.parse_args()

    cases = [json.loads(l) for l in CASES.read_text(encoding="utf-8").splitlines() if l.strip()]
    r = Retriever()
    print(f"模型 {r.manifest['model']}，索引 {r.vecs.shape[0]} 条，跑 {len(cases)} 条用例\n")

    rows, failed = [], 0
    for i, case in enumerate(cases, 1):
        res = answer(case["input"], k=args.k, retriever=r)
        fails = check(res, case["expected"])
        failed += bool(fails)
        head = "OK  " if not fails else "FAIL"
        print(f"[{head}] {i}. {case['input']}")
        if res.refused:
            print(f"        拒答：{res.refuse_reason}｜咨询：{res.suggested_contact or '（缺）'}")
        else:
            print(f"        {res.answer}")
            for c in res.citations:
                print(f"          · 《{c.file}》 {c.section or ''} score {c.score:.3f}")
        for f in fails:
            print(f"        ! {f}")
        print()
        rows.append({
            "id": i, "question": case["input"], "pass": "N" if fails else "Y",
            "refused": res.refused, "refuse_reason": res.refuse_reason,
            "confidence": f"{res.confidence:.2f}",
            "citations": " | ".join(c.file for c in res.citations),
            "answer": res.answer, "fails": "；".join(fails),
        })

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    with REPORT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"通过 {len(rows) - failed}/{len(rows)}，明细：{REPORT}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
