# 校园制度问答助手

已完成阶段 0–4：规格冻结 → 采集 → 解析切分 → 检索基线 → 生成与引用。

## 一、工具

| 项 | 选择 | 说明 |
| --- | --- | --- |
| 语言 | Python ≥3.11（本机 3.14.7） | 解析与向量库生态最省事 |
| 依赖管理 | `pyproject.toml` + `pip install -e .` | 版本锁死；另一台机器用 `uv` 装免安装 Python 3.12 |
| 虚拟环境 | `.venv` | 系统 Python 不装任何东西 |
| 测试 | `pytest` 9.1 | 29 项，**全部离线**（stub 模型），不联网不烧 token |

### Python 依赖

| 包 | 版本 | 干什么 |
| --- | --- | --- |
| `beautifulsoup4` | 4.15 | HTML 正文抽取 |
| `pymupdf` | 1.28 | PDF 取文字层 + 每页字符区间（用来给 chunk 标页码）；`pypdf` 6.19 作为备用 |
| `python-docx` | 1.2 | DOCX 段落与表格；读不到时回退扫 `word/*.xml`（制度常整篇塞在文本框里） |
| `numpy` | 2.5 | 向量矩阵与余弦相似度 |
| `sentence-transformers` + `torch` | 6.1 / 2.14 | 跑 bge 向量模型，Apple Silicon 走 MPS |
| `requests` | 2.34 | 采集，以及调模型（HTTP 就够） |
| `pydantic` | 2.13 | 接口契约 |
| `python-dotenv` | 1.2 | 读 `.env` |

### 外部服务

- **生成**：DeepSeek `deepseek-chat`
- **向量模型**：`BAAI/bge-small-zh-v1.5`

### 系统工具

- `textutil`（macOS 自带）/ `soffice`（LibreOffice）—— `.doc` 是二进制格式，没有纯 Python 解析库，用来转文本
- `git` + GitHub —— 代码托管 + release 附件分发 53 MB 原始语料（不进 Git）
- Python `zipfile` —— 打语料包。macOS 自带的 `zip` 不写 UTF-8 文件名标志，中文名会乱码，重建时全线报 `file_missing`

### 代码

| 脚本 | 职责 |
| --- | --- |
| `scripts/probe.py` | 试采：探一个栏目列表页，认出制度条目、抓正文、下附件、写登记表 |
| `scripts/collect_all.py` | 按 `meta/columns.csv` 批量跑 probe（部门站优先，信息公开最后） |
| `scripts/reparse_html.py` | 把「正文为空」的 HTML 条目重新解析（信息公开站很多正文是内嵌 PDF，采集时漏了） |
| `scripts/triage.py` | 登记表分诊：跨部门去重、误收附件标 `excluded` |
| `scripts/audit_versions.py` | 版本校对：把已被新版替代的旧制度标 `archived` |
| `scripts/import_manual.py` | 人工整理件（12 份 DOCX 汇编）的增量导入 |
| `scripts/build_corpus.py` | **解析 → 清洗 → 切分 → `data/chunks.jsonl`** |
| `scripts/build_index.py` | 建向量索引 → `data/index/` |
| `scripts/retrieval_smoke.py` | 20 条问题的检索基线，出 Recall@5 |
| `scripts/eval_answer.py` / `eval_batch.py` | 端到端评测（6 条 / 批量 200 条，断点续跑） |
| `scripts/ask.py` / `serve.py` | 命令行问答 / 网页演示 |
| `scripts/stats.py` | 验收口径的一键检查（总数、扫描件占比、部门与格式分布） |

---

## 二、知识库搭建

四步：**圈定来源 → 批量采集 → 分诊与版本校对 → 人工交叉校验**。

### 1. 圈定来源

`meta/columns.csv` 登记了 **25 个部门 / 学院站点、764 个栏目**，每个栏目记 url 和首页出现的制度文种词数（`rule_count`）。
`--min-rules 1` 能把翻页请求压到十分之一（764 个栏目里只有 107 个首页出现过文种词）。

### 2. 批量采集（`probe.py` + `collect_all.py`）

- 站点结构认两类：教务处一类是**列表页服务端渲染**，条目形如 `/2019/0621/c908a13000/page.htm`；
  信息公开一类**栏目本身就是一篇正文**，列表为空
- 从列表页找条目 → 抓正文 → 下载正文里的 PDF/Word 附件 → 落盘成
  `data/raw/<部门>/<年份>/部门_标题_年份.ext`（重名不覆盖）
- 只收**制度文种词结尾**的条目：办法 / 规定 / 细则 / 规程 / 制度 / 手册 / 条例 / 章程 / 准则 / 实施意见 / 汇编
- 重复的制度以**部门站版本为准**，信息公开最后采；礼貌抓取 1.5s 间隔 + 标识性 UA

### 3. 分诊与版本校对

- `triage.py`：**跨部门去重**（同一份制度在两个站各采到一次算重复，保留版本更新的；年份相同时部门站优先），
  误收的附件/表格标 `excluded`
- `audit_versions.py`：逐份在线比对新旧正文，把已被替代的标 `archived`。**只认直接证据**——
  名字像就归档会误伤（《"交流生"学籍管理办法》和《赴外"交流生"学籍管理办法》是两个适用对象）

### 4. 状态语义（`meta/documents.csv`，共 306 条在册）

| status | 条数 | 含义 |
| --- | --- | --- |
| `effective` | **263** | 现行有效，进检索 |
| `excluded` | 33 | 误收 / 重复 / 正文为空的空壳网页，压根不该在库里 |
| `archived` | 10 | 确实发布过，但已被新版替代；保留在册供追溯，**不进检索** |

### 5. 人工交叉校验

组员手工扒了 12 个 DOCX 汇编（桌面 5 份制度汇编 + `新建 DOCX 文件.docx` + `Downloads/监督工作,后勤保障和特色栏目/`），
逐条自带「发布日期＋原文形式＋来源」，共识别 **158 条条目**。与自动采集比对后**只导入 12 条增量**
（学校基本情况 3 条、规划计划 8 条、学生公寓服务管理规范 1 条），其余是重复或口径之外。
这 12 份同时充当采集器的质检：人按同一口径扒一遍，漏收哪些、误收哪些，一比就出来。

### 6. 落地形态

```
data/raw/<部门>/<年份>/      原始文件 53 MB（不进 Git，随 Release 分发）
meta/documents.csv           登记表：doc_id / dept / title / doc_no / year /
                             publish_date / source_url / page_url / format /
                             is_scanned / pages / status / local_path / fetched_at
data/parsed/<doc_id>.txt     每份制度清洗后的全文（清洗脚本重建时会清空重写）
data/chunks.jsonl            检索用的 chunk（进 Git）
```

---

## 三、文档切分

流水线全在 `scripts/build_corpus.py`：**解析 → 清洗 → 切分 → 合并碎片 → 落盘**。

### 1. 解析：按格式分派

| 格式 | 做法 |
| --- | --- |
| html（186 份） | BeautifulSoup；按一组正文选择器（`.wp_articlecontent` / `div.mm` / `.TRS_Editor` / `.v_news_content` …）取最长的一块，都没命中就退到最长的 `<div>`。**只在块级标签处断行**，不在每个文本节点之间断 |
| pdf（29 份） | PyMuPDF 逐页取文字，同时记下「每页的字符区间」→ 后面能让 chunk 带上页码；没有文字层的扫描件直接判失败 |
| docx（25 份） | python-docx 读段落和表格；段落文字太少就回退扫 `word/*.xml` 兜底 |
| doc（11 份） | 借系统工具转文本：`textutil` 优先，否则 `soffice`，并显式指定 UTF-8 |
| txt（12 份） | 人工整理件，直接读 |

### 2. 清洗 `clean_text`

- 折叠空白；按行剔除噪声（「版权所有」「沪ICP备」「浏览次数」「发布时间:」「分享到」…）
- 删重复行、删页码行。**页码规则只认带破折号的**——原先「任何独占一行的 1–3 位数字都当页码删」
  会吃掉正文数字（详见 `issues.md` I-13：227 份 HTML 里 80 份中招、共 1418 处）
- `join_short_lines`：把 `<span>` 拆出来的碎行并回句子，否则「根据 / 《财政部 / 教育部」会各占一行
- 整篇清洗后不足 120 字判失败，计入 `reports/parse_failures.csv`

### 3. 切分 `split_chunks`：以条款编号为主键

- 遇到 `第X条 / 第X章 / 第X节 / 第X编`（且整行 <60 字）就开新块，并维护「章 / 节」栈
- 每个 chunk 因此带上 `section` 路径，例如 `第二章 图书外借及归还 / 第三条`
- 没有条款编号的制度按段落聚合
- **上限 800 字**：超长段落先按 `。；！？` 拆句，再贪心合回 800 字以内，仍超就硬切
- **下限 50 字**：页眉页脚、表格残渣这类碎片先并进上一块；并进去仍不足 50 字就丢掉

### 4. 产出

`data/chunks.jsonl` 逐行一个 chunk：

```
chunk_id  doc_id  dept  title  year  section  page  text  chars  source_url
```

这些字段**正是引用面板要展示的全部内容**，所以后面「引用由代码回填」才成立。

### 5. 现状与重建纪律

**待解析 263 条 → 解析成功 261 条、失败 2 条**（两份整页扫描 PDF，没有文字层）
→ **4190 个 chunk，平均 303 字，最长 800 字**。
76% 的 chunk 带章节路径，2602 个（62%）带页码。

改了清洗或切分**必须重建**：`python -m scripts.build_corpus && python -m scripts.build_index`
（前者约 8 秒，后者约 1 分钟，会重新跑一遍 4190 条向量化）。

---

## 四、检索与生成

### 检索（`src/p1/retriever.py`）

- 索引 = `data/index/embeddings.npy`（**4190 × 512** float32，8.2 MB）+ `manifest.json`
  （记模型名、chunk 数、维度、查询前缀）。索引条数和 `chunks.jsonl` 行数对不上会直接报错让人重建
- 送进模型的文本是 `标题 + 正文`：条款正文常没有主语，单看「第十五条 …」不知道说的是哪份制度
- bge 的指令前缀（「为这个句子生成表示以用于检索相关文章：」）**只在查询侧加**，文档侧不加
- 召回：`vecs @ q` 暴力余弦，`k=5`
- `per_doc=2`：同一份文件最多占 2 席。《教学管理文件汇编》《学生手册》这类几百页的汇编把制度原文又收了一遍，
  向量几乎一样，不限制的话 top-5 会被它们整片占满，独立制度文件被挤出去

### 生成与强制引用（`src/p1/generator.py` + `prompts/answer/v2.md`）

- 把召回结果编成带编号的条款清单（`[1] 《文件名》 章节 / 第X页` + 正文），编号即模型能引用的**全部范围**
- 模型只输出 `{"answer": "...[1]", "used": [1,3], "confidence": ..., "refused": ...}` ——
  **只挑编号，不写引用元数据**；`file / page / section / score` 一律由 `to_citation()` 从检索结果回填
  → 「编造引用」这种失败模式在结构上不可能发生
- 答案里的编号最后按引用列表重排（`renumber`）：模型编出来的悬空编号整段删掉
- 同一段条款在汇编和独立制度里各出现一次时，按「剥掉条号、列表序号、标点后的正文」判重，
  保留分数高的那条，被丢掉的那条编号改指合并后那条（否则引用标号会悬空）
- 提示词进仓库、带版本号、配回归用例：`prompts/<名称>/vN.md` + `cases.jsonl`，
  **`v1.md` 永不删**，改动一律新建 `vN+1.md`

### 契约（`src/p1/contracts.py`，pydantic）

```
AnswerResult: question, answer, citations[Citation], confidence, refused, refuse_reason, suggested_contact
Citation:     file, page, section, snippet, score
```

命令行、网页、评测脚本三处**共用这一个契约**，所以加字段只改一个地方。

---

## 五、网站 demo

一个文件 `scripts/serve.py`，**只用标准库** `http.server`（`ThreadingHTTPServer`），不引 Web 框架。

- **两个路由**：`GET /` 返回一个内联的 HTML 页面；`POST /api/ask` 收 `{"question": "..."}`
- **返回体**就是上面那份 pydantic 契约的 JSON（`res.model_dump_json()`），和命令行输出同源
- **界面**：一个输入框 + 4 个示例问题按钮（图书馆借书 / 转专业 / 宿舍违规电器 / 一个库里没有的问题）。
  答案块显示正文 + 置信度，下面逐条列引用：`[1] 《文件名》 章节 第X页 · 匹配度 0.782` + 片段；
  拒答时换一套配色，显示拒答原因和建议咨询部门。前端就是一段原生 JS，没有构建步骤
- **输入校验放在服务端**：空问题、超 200 字、非法 JSON 一律 400
- **模型超时/网络错返回 502**，不把服务打挂

```bash
cd ~/proj/p1-rag
source .venv/bin/activate
python scripts/serve.py
```

---

## 六、数据现状一览

| 项 | 值 |
| --- | --- |
| 覆盖站点 / 栏目 | 25 个 / 764 个 |
| 在册条目 | 306 条（现行有效 263 / 误收 33 / 已替代 10） |
| 现行有效格式分布 | html 186、pdf 29、docx 25、txt 12、doc 11 |
| 解析结果 | 成功 261 / 失败 2（整页扫描 PDF，无文字层） |
| chunk | **4190 个**，平均 303 字，最长 800 字 |
| 向量索引 | 4190 × 512 float32，8.2 MB |
| 原始文件 | 53 MB（`data/raw/`，不进 Git） |
| 检索 | Recall@5 = 19/20 = 95%（20 条冒烟集） |
| 单元测试 | 29 项通过（离线） |
| 端到端 | 6/6 通过（打真模型），含 2 条拒答 |
| 250 题实测 | 逐题判定 ✓ 210 / △ 36 / ✗ 4 |

