"""端到端问答（阶段 4）。

    python -m scripts.ask "图书馆一次能借几本书"
"""

import argparse
import sys

sys.path.insert(0, ".")
from p1.generator import answer  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("-k", type=int, default=5)
    args = ap.parse_args()

    res = answer(args.question, k=args.k)
    print(f"\n问题：{res.question}")
    if res.refused:
        print(f"拒答：{res.refuse_reason}")
        if res.suggested_contact:
            print(f"建议咨询：{res.suggested_contact}")
    else:
        print(f"回答（confidence {res.confidence:.2f}）：\n{res.answer}")
    for i, c in enumerate(res.citations, 1):
        where = " / ".join(x for x in (c.section, f"第 {c.page} 页" if c.page else None) if x)
        print(f"\n  [{i}] 《{c.file}》{(' ' + where) if where else ''}  (score {c.score:.3f})")
        print(f"      {c.snippet[:120]}…")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
