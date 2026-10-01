# P1 校园制度问答助手

面向全校师生的制度问答系统，重点考核「把模糊提问变成可靠回答」的完整 RAG 工程能力。

## 环境准备

```bash
python3 -m venv .venv
.venv/bin/pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -e . pytest
```

## 运行

```bash
python -m scripts.serve             # 网页演示 → http://127.0.0.1:8000
python -m scripts.ask "图书馆一次能借几本书"   # 命令行问一句
python -m scripts.eval_answer       # 6 条端到端用例打真模型，核对引用与拒答
pytest -q                           # 29 项单元测试，不联网不烧 token
```

需要 `.env` 里的 `LLM_API_KEY`（见下），且命令都在仓库根目录跑。首次提问要等约 15 秒
加载本地向量模型，之后每个问题不到 1 秒。

## 语料流水线

**语料不进 Git**（原始文件 53 MB）。从 [Releases](https://github.com/ryannn02/p1-rag/releases) 下载
`p1-rag-corpus-*.zip`，在**仓库根目录**解压即可直接落到 `data/raw/`（包内路径与 `meta/documents.csv`
的 `local_path` 一致），然后重建：

```bash
unzip ~/Downloads/p1-rag-corpus-v0.1.0-beta.zip   # → data/raw/<部门>/<年份>/<文件名>
python -m scripts.build_corpus    # 解析 + 切分
python -m scripts.build_index     # 建向量索引
```

以下是采集与维护流水线，只想跑问答的话不用看：

```bash
python -m scripts.probe <列表页URL> --dept 教务处   # 采集单个栏目（更多用法见 meta/README.md）
python -m scripts.collect_all --pages 2             # 按 columns.csv 批量采集
python -m scripts.collect_all --min-rules 1 --pages 4   # 补采：只跑首页出现过文种词的 107 个栏目
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

召回口径见 `src/p1/retriever.py`：暴力余弦，4583 条语料单查询约 15 ms，
语料上到十万级再换 FAISS。

## 生成与引用（阶段 4）

```bash
python -m scripts.ask "在宿舍里使用违规电器被查到会怎么处理"
```

**引用的元数据全部由代码回填，不由模型生成**：模型只能从召回结果里挑编号（`used: [1,3]`），
`file / page / section / score` 一律取自检索结果，挑不出有效编号就拒答。提示词在
`prompts/answer/v2.md`（v1 保留），回归用例在 `prompts/answer/cases.jsonl`。

需要 `.env`：

```
LLM_API_KEY=sk-...                                # 必填，.env 已 gitignore
LLM_BASE_URL=https://api.deepseek.com/v1          # 默认 DeepSeek
LLM_MODEL=deepseek-chat
HF_ENDPOINT=https://hf-mirror.com                 # 拉向量模型用镜像
```

`src/p1/llm.py` 走 OpenAI 兼容的 `/chat/completions`，换通义/智谱只改 `LLM_BASE_URL`。

## 约定

- 需求分析（33 条 FR + 9 条 NFR）：`docs/requirements.md`
- 实施方案（10 个阶段的排期与工具）：`docs/plan.md`
- 阶段进度报告（做了什么、数据在哪、踩过哪些坑）：`docs/progress.md`
- 协作与分支流程：`docs/contributing.md`
- 提示词版本与用例格式：`prompts/README.md`
- 接口契约唯一真源：`src/p1/contracts.py`
