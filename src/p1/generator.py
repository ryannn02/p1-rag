"""阶段 4 生成与强制引用。

引用的元数据全部由代码回填，不由模型生成：模型只能从给定的编号里挑
（输出 `used: [1,3]`），`file/page/section/score` 一律取自检索结果。
模型挑不出有效编号就不给答案——这是「强制引用」的落实方式，
也是编造引用这种失败模式在结构上不可能发生的原因。

没有依据就拒答属于阶段 5，这里先落实三条底线（都不是「判定」，只是不该答的时候别答）：

1. 引用不成立就不作答；
2. 非中文提问直接拒答——bge 是中文模型，英文查询的向量落不到中文语义空间，
   硬答会把「我没找到」讲成「学校没规定」（issues.md I-2）；
3. top-1 低于前置阈值时干脆不调模型，省一次调用（阈值见下）。

`refuse_reason` 一律是机读 code（见 contracts.py），给用户看的话放 `answer`。
"""

import json
import re
from pathlib import Path

from p1.contracts import (
    BAD_MODEL_OUTPUT,
    NO_EVIDENCE,
    NO_VALID_CITATION,
    RETRIEVAL_EMPTY,
    RETRIEVAL_LOW_SCORE,
    UNSUPPORTED_LANGUAGE,
    AnswerResult,
    Citation,
)
from p1.retriever import Retriever

PROMPT_NAME = "answer"
PROMPT_VERSION = "v2"
SNIPPET_CHARS = 220
MAX_CITED = 3
# 前置过滤阈值：reports/threshold_sweep.png 上「误杀正常题为 0」的最大值（τ=0.45）。
# 它只用来省掉明显无望的模型调用，不承担判定——分数区分不开「该答」与「该拒答」，
# 依据见 issues.md I-3 与 reports/retrieval_scores_250.csv。
LOW_SCORE_TAU = 0.45
# 提问里一个汉字都没有就按「非中文」处理（阶段 5 决定暂时只支持中文提问）
CJK = re.compile(r"[\u4e00-\u9fff]")

# code → 给用户看的一句话；模型判的拒答（NO_EVIDENCE）用模型自己那句话
MESSAGES = {
    RETRIEVAL_EMPTY: "在已收录的现行制度中没有检索到相关条款，无法给出可靠答复。",
    RETRIEVAL_LOW_SCORE: "检索到的条款与这个问题相关性过低，不足以作为依据。",
    UNSUPPORTED_LANGUAGE: "目前只支持用中文提问，无法可靠检索和回答其他语言的提问。",
    BAD_MODEL_OUTPUT: "模型输出无法解析，无法核对条款引用。",
    NO_VALID_CITATION: "没有可核对的条款引用，无法给出可信答复。",
    NO_EVIDENCE: "在已收录的现行制度中未找到能支撑该问题的条款。",
}


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


def dedupe_key(text):
    """同一条款在汇编与独立制度里的副本，正文只差条号、列表序号、标点和换行。

    这几样全剥掉再比：条号（第三条 / 第十三条）、列表序号（1．/ 2. / （一））、
    空白与标点。数字内容保留——「外借 30 册」和「外借 10 册」是两条不同条款，
    抹掉数字会把它们并成一条，引用就指错数了。
    """
    text = re.sub(r"第\s*[一二三四五六七八九十百零〇\d]+\s*[条章节]", "", text or "")
    text = re.sub(r"\d+\s*[．.、)）]", "", text)
    text = re.sub(r"[（(][一二三四五六七八九十\d]+[）)]", "", text)
    return re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]", "", text)


def dedupe_citations(picked):
    """同一段条款在汇编和独立制度里各出现一次时只留一条。

    保留分数高的那条（独立制度通常排在汇编前面），被丢掉的那条记住映射，
    免得答案里的引用标号变成悬空。

    判重键要剥掉「第十三条」这类条款序号和所有空白：汇编里的同一条款
    往往条号不同、换行位置也不同，只比原文字符串是抓不到的。
    """
    kept, alias, seen = [], {}, {}
    for idx, hit in picked:
        key = dedupe_key(hit["text"])
        if key in seen:
            alias[idx] = seen[key]
            continue
        seen[key] = idx
        kept.append((idx, hit))
    return kept, alias


def renumber(answer, picked, alias):
    """把答案里的条款编号改成引用列表里的编号，保证两边对得上。

    指向被合并条款的编号（alias）改指合并后那一条；模型自己编的、指向
    不存在条款的编号整段删掉，免得留下悬空引用。
    """
    pos = {idx: i for i, (idx, _) in enumerate(picked, 1)}
    pos.update({old: pos[new] for old, new in alias.items() if new in pos})
    for old in sorted(pos, reverse=True):
        answer = answer.replace(f"[{old}]", f"\x00{pos[old]}\x00")
    answer = re.sub(r"\[\d+\]", "", answer)
    answer = re.sub(r"\x00(\d+)\x00", r"[\1]", answer)
    answer = re.sub(r"\[(\d+)\](?:\s*\[\1\])+", r"[\1]", answer)
    return answer.strip()


def refusal(question, code, contact=None, text=None, top_score=None):
    """拒答：`answer` 给用户看，`refuse_reason` 是机读 code。"""
    return AnswerResult(
        question=question,
        answer=text or MESSAGES.get(code, ""),
        refused=True,
        refuse_reason=code,
        suggested_contact=contact,
        top_retrieval_score=top_score,
    )


def answer_from_hits(question, hits, llm=None):
    if not CJK.search(question or ""):
        return refusal(question, UNSUPPORTED_LANGUAGE)
    if not hits:
        return refusal(question, RETRIEVAL_EMPTY)
    top = float(hits[0]["score"])
    if top < LOW_SCORE_TAU:
        return refusal(question, RETRIEVAL_LOW_SCORE, top_score=top)
    llm = llm or _default_llm
    prompt = load_prompt().replace("{{question}}", question).replace("{{context}}", build_context(hits))
    raw = llm(prompt)
    data = extract_json(raw)
    if not isinstance(data, dict):
        return refusal(question, BAD_MODEL_OUTPUT, top_score=top)

    if data.get("refused"):
        # 模型判的「条款支撑不住」：话由模型说，code 由我们定
        return refusal(question, NO_EVIDENCE, data.get("suggested_contact"),
                       text=str(data.get("refuse_reason") or "") or None, top_score=top)

    picked, seen = [], set()
    for idx in data.get("used") or []:
        if isinstance(idx, int) and 1 <= idx <= len(hits) and idx not in seen:
            seen.add(idx)
            picked.append((idx, hits[idx - 1]))
        if len(picked) == MAX_CITED:
            break
    if not picked:
        return refusal(question, NO_VALID_CITATION, data.get("suggested_contact"), top_score=top)
    picked, alias = dedupe_citations(picked)

    try:
        conf = min(max(float(data.get("confidence") or 0.0), 0.0), 1.0)
    except (TypeError, ValueError):
        conf = 0.0
    return AnswerResult(
        question=question,
        answer=renumber(str(data.get("answer") or "").strip(), picked, alias),
        citations=[to_citation(h) for _, h in picked],
        confidence=conf,
        suggested_contact=data.get("suggested_contact"),
        top_retrieval_score=top,
    )


def answer(question, k=5, llm=None, retriever=None):
    r = retriever or Retriever()
    return answer_from_hits(question, r.search(question, k=k, per_doc=2), llm=llm)


def _default_llm(prompt):
    from p1.llm import chat

    return chat(prompt)
