# Windows 使用指南

对应 release **v0.1.0-beta.2 及以后**。更早的 `v0.1.0-beta` 少了 `.doc` 的 `soffice` 回退，
会少 11 份制度（见文末）。

本文假定你从没在这台机器上跑过 Python 项目。全程复制粘贴即可，命令用 **PowerShell**
（开始菜单搜「PowerShell」）。

---

## 1. 装三样东西

| 装什么 | 怎么装 | 不装会怎样 |
| --- | --- | --- |
| **Python 3.11+** | [python.org](https://www.python.org/downloads/) 下载安装，**安装时勾上 `Add python.exe to PATH`** | 什么都跑不了 |
| **Git** | [git-scm.com](https://git-scm.com/download/win) | 拿不到代码 |
| LibreOffice（可选） | [libreoffice.org](https://www.libreoffice.org/) | 少 11 份 `.doc` 制度（约 1% 语料） |

装完在 PowerShell 里验一下，能打印版本号就行：

```powershell
py -3 --version
git --version
```

> `python3` 这个命令在 Windows 上**不存在**（那是 macOS / Linux 的）。统一用 `py -3`。

---

## 2. 拿代码

```powershell
cd $HOME\Documents
git clone https://github.com/ryannn02/p1-rag.git
cd p1-rag
```

以后每条命令都要在这个目录里执行。脚本读 `data/`、`prompts/` 用的是相对路径，在别处跑会报找不到文件。

## 3. 建虚拟环境、装依赖

```powershell
py -3 -m venv .venv
.venv\Scripts\pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -e . pytest
```

装依赖要几分钟，装完 `.venv` 约 1.2 GB（大头是 torch 590 MB）。装完自检一下：

```powershell
.venv\Scripts\python -m pytest -q
```

预期输出 **`29 passed`**。这一步不需要网络也不需要语料，看到 29 passed 就说明 Python 环境完全正常，
后面出问题就不用再怀疑环境。

> **不建议 `activate`。** 网上教程会说 `.venv\Scripts\activate`，但 PowerShell 默认禁止运行
> 激活脚本，会报「在此系统上禁止运行脚本」，得先改执行策略。**直接用 `.venv\Scripts\python`
> 全路径调用即可**，效果完全一样，本文所有命令都这么写。

## 4. 写 `.env`

在仓库根目录建一个名为 `.env` 的文件（注意文件名以一个点开头，没有扩展名）：

```powershell
ni .env -Force
notepad .env
```

粘贴以下内容后保存：

```
LLM_API_KEY=sk-你的DeepSeek密钥
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat
HF_ENDPOINT=https://hf-mirror.com
```

> **坑：用记事本存 `.env` 容易变成 `.env.txt`。** 记事本「另存为」时把「保存类型」改成
> **所有文件**，文件名写成带引号的 `".env"`。存完在 PowerShell 里 `dir .env*` 确认一下，
> 只应该看到一个 `.env`。名字错了程序读不到，会提示「未设置 LLM_API_KEY」。
>
> `HF_ENDPOINT` 那行别删——国内直连 huggingface.co 会被拒，拉向量模型会失败。

`.env` 已在 `.gitignore` 里，不会被提交。

## 5. 拿语料

语料 **53 MB，不进 Git**，作为 release 附件单独下载。打开
[Releases 页面](https://github.com/ryannn02/p1-rag/releases)，在你用的那个版本下下载
`p1-rag-corpus-*.zip`（约 43 MB）。

**在仓库根目录**解压（下一行的 `-DestinationPath .` 指的是当前目录，别省略）：

```powershell
Expand-Archive -Path $HOME\Downloads\p1-rag-corpus-v0.1.0-beta.2.zip -DestinationPath . -Force
```

解压后应该出现 `data\raw\教务处\`、`data\raw\信息公开\` 这样的目录。
**如果中文目录名是乱码**（显示成 `鏁欏姟澶�` 之类），换 [7-Zip](https://www.7-zip.org/)
解压——压缩包本身没问题，是部分解压工具不认 UTF-8 文件名。

## 6. 验证语料完整，然后重建

```powershell
.venv\Scripts\python -m scripts.build_corpus
```

**期望输出**：

```
待解析 263 条
...
解析成功 261 条，失败 2 条（明细见 reports\parse_failures.csv）
切出 4583 个 chunk，平均 275 字，最长 800 字
```

数字对不上就照下表排查：

| 看到的现象 | 原因 | 怎么办 |
| --- | --- | --- |
| `待解析 263 条` 之外的数量 | 解压没到位或压到了子目录 | 确认 `data\raw\教务处\` 在仓库根目录下 |
| **失败 13 条**（而不是 2 条） | `.doc` 没有转换工具 | 装 LibreOffice；不装也能用，只是少 11 份制度 |
| 失败 263 条 / `待解析` 就报错 | 语料没解压 | 回到第 5 步 |
| 文件名乱码 | 解压工具问题 | 用 7-Zip 重解 |

失败明细在 `reports\parse_failures.csv`，可以拿记事本打开看原因。

接着建向量索引（约 1 分钟，要联网拉一次向量模型）：

```powershell
.venv\Scripts\python -m scripts.build_index
```

## 7. 跑起来

```powershell
.venv\Scripts\python -m scripts.serve
```

看到这两行就成了：

```
加载向量索引与模型…
就绪：http://127.0.0.1:8000  （Ctrl+C 停止）
```

浏览器打开 `http://127.0.0.1:8000` 提问。**第一个问题要等十几秒**（本地向量模型首次加载），
之后每个问题不到 1 秒。这个窗口会被服务占住，`Ctrl+C` 才停。

不想开浏览器就用命令行：

```powershell
.venv\Scripts\python -m scripts.ask "图书馆一次能借几本书"
```

---

## 命令对照表

文档里大部分示例是 macOS 写法，对照着替换：

| 文档里写的 | Windows 上写成 |
| --- | --- |
| `python3 -m venv .venv` | `py -3 -m venv .venv` |
| `source .venv/bin/activate` | `.venv\Scripts\activate`（不建议，见第 3 步） |
| `.venv/bin/python` | `.venv\Scripts\python` |
| `pytest -q` | `.venv\Scripts\python -m pytest -q` |
| `./scripts/xxx.py` | `.venv\Scripts\python -m scripts.xxx` |
| `unzip xxx.zip` | `Expand-Archive -Path xxx.zip -DestinationPath .` |
| 行末接 `&&` | 接 `;`，或者分两行写 |

## 常见报错

| 报错 | 原因与处理 |
| --- | --- |
| `python3 : 无法将"python3"项识别为 cmdlet...` | Windows 没有 `python3`，用 `py -3` |
| `...activate.ps1，因为在此系统上禁止运行脚本` | 别用 activate，直接 `.venv\Scripts\python` 全路径调用 |
| `No module named 'scripts'` | 当前目录不对，`cd` 到仓库根目录再跑 |
| `未设置 LLM_API_KEY` | `.env` 不存在、存成了 `.env.txt`，或不在仓库根目录 |
| `No such file or directory: 'data/chunks.jsonl'` | 语料没解压，或没跑 `build_corpus` |
| 终端里中文显示成方块/乱码 | PowerShell 5.1 控制台编码问题，先执行 `chcp 65001`；**只影响显示，不影响程序** |
| `Address already in use` | 端口被占：换端口 `.venv\Scripts\python -m scripts.serve 9000`，或任务管理器结束那个 python 进程 |
| 报错说 `file_missing_or_unsupported_format` 很多条 | 解压时文件名乱了，用 7-Zip 重解 |
| LibreOffice 装了但 `.doc` 仍失败 | 确认 `soffice.exe` 在 PATH 里，或重启 PowerShell 让 PATH 生效 |

## 与 macOS 的已知差异

- **`.doc` 解析**：macOS 用系统自带的 `textutil`，Windows 走 LibreOffice 的 `soffice`。
  两条路都在 `scripts/build_corpus.py` 里，代码会自动挑。
- **`git status` 显示一堆文件被改但你没动**：是 Windows 的换行符（CRLF）转换。仓库里有
  `.gitattributes` 已把它固定成 LF，如果仍然出现，执行 `git config core.autocrlf false`
  然后 `git checkout -- .` 还原。
- 其余全部一致：检索、生成、网页服务都是纯 Python，没有别的东西依赖特定系统。
