"""OpenAI 兼容的对话接口。

DeepSeek、通义千问、智谱、Moonshot 都是同一套 `/chat/completions` 协议，
所以只写一个实现、用 `requests` 发（本来就是依赖），不为每家装一个 SDK。

配置走 `.env`：

    LLM_API_KEY=sk-...                                  # 必填
    LLM_BASE_URL=https://api.deepseek.com/v1            # 默认 DeepSeek
    LLM_MODEL=deepseek-chat                             # 默认 deepseek-chat
"""

import os

import requests
from dotenv import load_dotenv

load_dotenv()

DEFAULT_BASE_URL = "https://api.deepseek.com/v1"
DEFAULT_MODEL = "deepseek-chat"


def configured():
    return bool(os.getenv("LLM_API_KEY"))


def chat(prompt, system=None, temperature=0.0, timeout=120):
    key = os.getenv("LLM_API_KEY")
    if not key:
        raise SystemExit(
            "未设置 LLM_API_KEY。把 key 写进 .env 再跑：\n"
            "  LLM_API_KEY=sk-...\n"
            "  LLM_BASE_URL=https://api.deepseek.com/v1   # 或通义/智谱的兼容地址\n"
            "  LLM_MODEL=deepseek-chat\n"
            "（.env 已 gitignore，不会进仓库）"
        )
    base = os.getenv("LLM_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    messages = ([{"role": "system", "content": system}] if system else []) + [
        {"role": "user", "content": prompt}
    ]
    resp = requests.post(
        f"{base}/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={
            "model": os.getenv("LLM_MODEL", DEFAULT_MODEL),
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        },
        timeout=timeout,
    )
    if resp.status_code != 200:
        raise SystemExit(f"模型调用失败 {resp.status_code}：{resp.text[:400]}")
    return resp.json()["choices"][0]["message"]["content"]
