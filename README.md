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

## 约定

- 协作与分支流程：`docs/contributing.md`
- 提示词版本与用例格式：`prompts/README.md`
- 接口契约唯一真源：`src/p1/contracts.py`
