"""阶段 4 生成与强制引用。

引用的元数据全部由代码回填，不由模型生成：模型只能从给定的编号里挑
（输出 `used: [1,3]`），`file/page/section/score` 一律取自检索结果。
模型挑不出有效编号就不给答案——这是「强制引用」的落实方式，
也是编造引用这种失败模式在结构上不可能发生的原因。

没有依据就拒答属于阶段 5，这里只实现「引用不成立就不作答」这条底线。
"""

import json
import re
from pathlib import Path

from p1.contracts import AnswerResult, Citation
from p1.retriever import Retriever

PROMPT_NAME = "answer"
PROMPT_VERSION = "v1"
SNIPPET_CHARS = 220
MAX_CITED = 3


def load_prompt(version=PROMPT_VERSION):
    path = Path("prompts") / PROMPT_NAME / f"{version}.md"
    return path.read_text(encoding="utf-8")


def build_context(hits):
    """把召回结果编成带编号的条款清单，编号即模型能引用的全部范围。"""
    blocks = []
    for i, h in enumerate(hits, 1):
        where = " / ".join(x for x in (h.get("section"), f"第 {h['page']} 页" if h.get("page") else None) if x)
        head = f"[{i}] 《{h['title']}》" + (f" {where}" if where else "")
        blocks.append(f"{head}\n{h['text']}")
    return "\n\n".join(blocks)


def extract_json(text):
    """模型偶尔会套一层 ```json 或前后带说明，抓第一个平衡的 JSON 对象。"""
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text).strip()
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def to_citation(hit):
    return Citation(
        file=hit["title"],
        page=int(hit["page"]) if hit.get("page") else None,
        section=hit.get("section") or None,
        snippet=hit["text"][:SNIPPET_CHARS],
        score=float(hit["score"]),
    )


def refusal(question, reason, contact=None):
    return AnswerResult(
        question=question, answer="", refused=True, refuse_reason=reason, suggested_contact=contact
    )


def answer_from_hits(question, hits, llm=None):
    if not hits:
        return refusal(question, "检索没有召回任何条款")
    llm = llm or _default_llm
    prompt = load_prompt().replace("{{question}}", question).replace("{{context}}", build_context(hits))
    raw = llm(prompt)
    data = extract_json(raw)
    if not isinstance(data, dict):
        return refusal(question, "模型输出不是合法 JSON，无法核对引用")

    if data.get("refused"):
        return refusal(question, data.get("refuse_reason") or "依据不足", data.get("suggested_contact"))

    picked, seen = [], set()
    for idx in data.get("used") or []:
        if isinstance(idx, int) and 1 <= idx <= len(hits) and idx not in seen:
            seen.add(idx)
            picked.append((idx, hits[idx - 1]))
        if len(picked) == MAX_CITED:
            break
    if not picked:
        return refusal(question, "模型没有给出可核对的条款引用", data.get("suggested_contact"))

    try:
        conf = min(max(float(data.get("confidence") or 0.0), 0.0), 1.0)
    except (TypeError, ValueError):
        conf = 0.0
    return AnswerResult(
        question=question,
        answer=str(data.get("answer") or "").strip(),
        citations=[to_citation(h) for _, h in picked],
        confidence=conf,
        suggested_contact=data.get("suggested_contact"),
    )


def answer(question, k=5, llm=None, retriever=None):
    r = retriever or Retriever()
    return answer_from_hits(question, r.search(question, k=k, per_doc=2), llm=llm)


def _default_llm(prompt):
    from p1.llm import chat

    return chat(prompt)
