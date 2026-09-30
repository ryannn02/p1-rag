"""建检索索引（阶段 3）。

    python -m scripts.build_index                     # 默认 bge-small-zh-v1.5
    python -m scripts.build_index --model BAAI/bge-m3 # 换模型（索引要重建）
"""

import argparse
import sys
import time

sys.path.insert(0, ".")
from src.p1.retriever import build, default_model  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=None, help=f"默认 {default_model()}")
    ap.add_argument("--batch-size", type=int, default=64)
    args = ap.parse_args()

    t = time.time()
    shape = build(model_name=args.model, batch_size=args.batch_size)
    print(f"索引完成：{shape[0]} 条 × {shape[1]} 维，用时 {time.time() - t:.0f}s")
    print("模型与语料指纹记在 data/index/manifest.json，换模型或换语料都要重建。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
