# P1 校园制度问答助手

## 环境准备

```bash
python3 -m venv .venv
.venv/bin/pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -e . pytest
```

## 运行

```bash
.venv/bin/python -m p1.service      # 打印一条占位 JSON
.venv/bin/pytest -q                 # 提示词目录结构校验
```
