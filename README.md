# P1 校园制度问答助手

面向全校师生的制度问答系统，重点考核「把模糊提问变成可靠回答」的完整 RAG 工程能力。

## 环境准备

```bash
python3 -m venv .venv
.venv/bin/pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -e . pytest
```

## 运行

```bash
.venv/bin/python -m p1.service      # 打印一条占位 JSON
.venv/bin/pytest -q                 # 提示词结构与用例校验
```

## 语料流水线

```bash
python -m scripts.probe <列表页URL> --dept 教务处   # 采集单个栏目（更多用法见 meta/README.md）
python -m scripts.collect_all --pages 2             # 按 columns.csv 批量采集
python -m scripts.reparse_html                      # 把正文为空、内容内嵌在 PDF 播放器里的条目升级
python -m scripts.triage --apply                    # 标出误收与重复条目
python -m scripts.build_corpus                      # 解析 + 切分，产出 data/parsed 与 data/chunks.jsonl
python -m scripts.stats                             # 语料验收口径统计
```

`.doc` 的解析依赖 macOS 自带的 `textutil`；Linux 上需要改用 LibreOffice。

## 检索基线（阶段 3）

```bash
python -m scripts.build_index                       # 建向量索引（默认 bge-small-zh-v1.5）
python -m scripts.retrieval_smoke                   # 20 条冒烟问题，出 Recall@5
python -m scripts.retrieval_smoke --per-doc 0       # 关掉「同文件限席」，看基线差异
```

索引落在 `data/index/`（不进 Git，换模型或换语料都要重建）。模型可用环境变量
`EMBED_MODEL` 覆盖，换模型后索引必须重建。

国内直连 huggingface.co 会被拒，`.env` 里设 `HF_ENDPOINT=https://hf-mirror.com`
拉模型（必须在 `huggingface_hub` 导入前生效，`src/p1/retriever.py` 已在模块顶部 load）。

召回口径见 `src/p1/retriever.py`：暴力余弦，4403 条语料单查询约 15 ms，
语料上到十万级再换 FAISS。

## 约定

- 协作与分支流程：`docs/contributing.md`
- 提示词版本与用例格式：`prompts/README.md`
- 接口契约唯一真源：`src/p1/contracts.py`
