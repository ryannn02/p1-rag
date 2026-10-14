"""把 250 题逐题的检索分数落盘，并离线扫一遍拒答阈值。

    python -m scripts.retrieval_scores           # 落盘 + 打印扫描表
    python -m scripts.retrieval_scores --plot    # 另存阈值曲线（需 matplotlib）

**只跑检索，不调大模型**，几分钱不花。产物：

- `reports/retrieval_scores_250.csv`：每题 top-5 分数、命中文件、期望行为
- `reports/threshold_sweep.png`：拒答阈值曲线（`--plot`）

为什么要单独落盘：`reports/batch_questions_250.csv` 只存了引用文件名，没存分数，
所以每次要扫阈值都得重跑检索。分数摊开来之后，调阈值就不用再碰模型。
"""

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, ".")
from p1.retriever import Retriever  # noqa: E402
from scripts.eval_batch import DEFAULT_SET, parse_set  # noqa: E402

OUT = Path("reports/retrieval_scores_250.csv")
PLOT = Path("reports/threshold_sweep.png")
TARGET_GROUP = "U"  # 问题集里标明「应当拒答」的那一组
TAUS = [round(0.35 + 0.05 * i, 2) for i in range(9)]  # 0.35 … 0.75


def score_all(rows, k=5):
    r = Retriever()
    print(f"模型 {r.manifest['model']}，索引 {r.vecs.shape[0]} 条，共 {len(rows)} 题\n", flush=True)
    out = []
    for i, row in enumerate(rows, 1):
        hits = r.search(row["question"] or "（空）", k=k, per_doc=2)
        scores = [round(h["score"], 4) for h in hits]
        out.append({
            "id": row["id"], "group": row["group"], "question": row["question"],
            "top1_file": hits[0]["title"] if hits else "",
            **{f"top{j + 1}": (scores[j] if j < len(scores) else "") for j in range(k)},
            "expect": row["expect"],
        })
        if i % 50 == 0:
            print(f"  已跑 {i}/{len(rows)}", flush=True)
    return out


def sweep(rows):
    """按 top-1 分数扫阈值。返回 [(τ, 误杀正常题, 漏放该拒的题)]。"""
    normal = [r for r in rows if r["group"] not in (TARGET_GROUP, "V")]
    target = [r for r in rows if r["group"] == TARGET_GROUP]
    table = []
    for tau in TAUS:
        killed = sum(1 for r in normal if r["top1"] < tau)
        passed = sum(1 for r in target if r["top1"] >= tau)
        table.append((tau, killed, passed))
    return table, len(normal), len(target)


def plot(table, n_normal, n_target, path=PLOT):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    taus = [t for t, _, _ in table]
    fig, ax = plt.subplots(figsize=(7, 4.2))
    ax.plot(taus, [k / n_normal * 100 for _, k, _ in table], "o-", label="误杀正常题（%）")
    ax.plot(taus, [p / n_target * 100 for _, _, p in table], "s-", label="漏放该拒的题（%）")
    ax.set_xlabel("拒答阈值 τ（top-1 余弦分数）")
    ax.set_ylabel("比例（%）")
    ax.set_title("拒答阈值扫描：两堆分数重叠，不存在可用的分值闸门")
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=140)
    print(f"曲线已存 {path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", type=Path, default=DEFAULT_SET)
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--plot", action="store_true")
    args = ap.parse_args()

    rows = score_all(parse_set(args.set), k=args.k)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(f"分数已存 {OUT}（{len(rows)} 题）\n")

    table, n_normal, n_target = sweep(rows)
    print(f"正常题 {n_normal} 道（不含 U/V 组）、该拒答题 {n_target} 道（U 组）\n")
    print("| τ | 误杀正常题 | 漏放该拒的题 |")
    print("| --- | --- | --- |")
    for tau, killed, passed in table:
        print(f"| {tau:.2f} | {killed}（{killed / n_normal:.1%}） | {passed}/{n_target} |")

    usable = [t for t, k, _ in table if k == 0]
    if usable:
        print(f"\n误杀为 0 的最大阈值：τ = {max(usable):.2f}"
              f"（再大会开始误杀正常题；这一档只当前置过滤，不承担判定）")
    if args.plot:
        plot(table, n_normal, n_target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
