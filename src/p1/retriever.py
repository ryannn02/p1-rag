"""阶段 3 检索基线：本地 bge 向量召回。

刻意不用 FAISS / Chroma：4403 个 chunk 的暴力余弦一次查询是毫秒级，
多引一个索引库只是多一份要同步的状态和一份要解释的构建流程。
    ponytail: 全量暴力检索，chunk 数上到十万级再换 FAISS/IVF。
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
from dotenv import load_dotenv

# 必须在任何 huggingface_hub 导入之前加载：HF_ENDPOINT 是在其模块导入时读定的
load_dotenv()

CHUNKS = Path("data/chunks.jsonl")
INDEX_DIR = Path("data/index")
EMB_FILE = "embeddings.npy"
MANIFEST = "manifest.json"
# bge 中文模型对短查询推荐的指令前缀，检索侧加、文档侧不加
QUERY_PREFIX = "为这个句子生成表示以用于检索相关文章："


def default_model():
    return os.getenv("EMBED_MODEL") or "BAAI/bge-small-zh-v1.5"


def read_chunks(path=CHUNKS):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def doc_text(chunk):
    """标题补进正文：条款正文经常没有主语，单看「第十五条 …」不知道说的是哪份制度。"""
    return f"{chunk['title']}\n{chunk['text']}"


def load_model(name=None, device=None):
    from sentence_transformers import SentenceTransformer

    if device is None:
        import torch

        device = "mps" if torch.backends.mps.is_available() else "cpu"
    return SentenceTransformer(name or default_model(), device=device)


def encode(texts, model, batch_size=64):
    texts = list(texts)
    return model.encode(
        texts,
        batch_size=batch_size,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=len(texts) > 200,
    )


def build(chunks_path=CHUNKS, index_dir=INDEX_DIR, model_name=None, batch_size=64):
    chunks = read_chunks(chunks_path)
    model = load_model(model_name)
    vecs = encode((doc_text(c) for c in chunks), model, batch_size).astype("float32")
    index_dir.mkdir(parents=True, exist_ok=True)
    np.save(index_dir / EMB_FILE, vecs)
    (index_dir / MANIFEST).write_text(
        json.dumps(
            {
                "model": model_name or default_model(),
                "chunks": len(chunks),
                "dim": int(vecs.shape[1]),
                "batch_size": batch_size,
                "chunks_file": str(chunks_path),
                "query_prefix": QUERY_PREFIX,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return vecs.shape


class Retriever:
    def __init__(self, index_dir=INDEX_DIR, chunks_path=CHUNKS):
        self.manifest = json.loads((index_dir / MANIFEST).read_text(encoding="utf-8"))
        self.vecs = np.load(index_dir / EMB_FILE)
        self.chunks = read_chunks(chunks_path)
        if len(self.chunks) != self.vecs.shape[0]:
            raise SystemExit(
                f"索引与语料对不上：索引 {self.vecs.shape[0]} 条，"
                f"{chunks_path} {len(self.chunks)} 条。重建索引：python -m scripts.build_index"
            )
        self._model = None

    @property
    def model(self):
        if self._model is None:
            self._model = load_model(self.manifest["model"])
        return self._model

    def search(self, query, k=5, per_doc=2):
        """per_doc 限制同一份文件在结果里最多占几席。

        《教学管理文件汇编》《学生手册》这类几百页的汇编把同一批制度原文又收了一遍，
        向量几乎一样，不限制的话 top-5 会被它们整片占满，独立制度文件被挤出去。
        """
        q = encode([QUERY_PREFIX + query], self.model)[0]
        scores = self.vecs @ q
        picked, used = [], {}
        for i in np.argsort(-scores):
            doc = self.chunks[int(i)]["doc_id"]
            if per_doc and used.get(doc, 0) >= per_doc:
                continue
            used[doc] = used.get(doc, 0) + 1
            picked.append(int(i))
            if len(picked) == k:
                break
        return [
            {**self.chunks[i], "score": float(scores[i]), "rank": r + 1}
            for r, i in enumerate(picked)
        ]
