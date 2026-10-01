"""阶段 4 的强制引用校验。全部用 stub 模型，不联网、不烧 token。"""

import json

import pytest

from p1.generator import answer_from_hits, build_context, extract_json

HITS = [
    {"title": "上海第二工业大学图书馆图书外借管理办法（修订）", "page": "", "section": "第一章 借书权限",
     "text": "全校教职工、全日制研究生、全日制本/专科生每人均可同时外借30册图书，外借期限为60天。",
     "score": 0.6748},
    {"title": "上海第二工业大学学生转专业实施办法（修订）", "page": "", "section": "",
     "text": "第六条：学生转专业后，必须在三周内办理学分认定手续。", "score": 0.6102},
]


def stub(payload):
    return lambda prompt: payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)


def test_context_numbers_every_clause():
    ctx = build_context(HITS)
    assert ctx.startswith("[1] 《上海第二工业大学图书馆图书外借管理办法（修订）》 第一章 借书权限")
    assert "[2] 《上海第二工业大学学生转专业实施办法（修订）》" in ctx


def test_extract_json_handles_code_fence_and_prose():
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('好的，结果如下：{"a": {"b": 2}} 以上就是答案') == {"a": {"b": 2}}
    assert extract_json("没有 JSON") is None


def test_citation_metadata_comes_from_retrieval_not_model():
    res = answer_from_hits(
        "图书馆一次能借几本",
        HITS,
        llm=stub({"answer": "每人可同时外借 30 册，期限 60 天 [1]", "used": [1],
                  "confidence": 0.9, "refused": False}),
    )
    assert not res.refused
    assert len(res.citations) == 1
    c = res.citations[0]
    assert c.file == HITS[0]["title"]
    assert c.section == HITS[0]["section"]
    assert c.score == pytest.approx(0.6748)
    assert "30册" in c.snippet
    assert res.confidence == pytest.approx(0.9)


def test_model_cannot_cite_outside_given_clauses():
    """模型编一个不存在的编号时，引用不成立，直接不给答案。"""
    res = answer_from_hits("随便问", HITS, llm=stub({"answer": "编的 [7]", "used": [7], "refused": False}))
    assert res.refused
    assert res.citations == []
    assert "引用" in res.refuse_reason


def test_empty_used_is_treated_as_refusal():
    res = answer_from_hits("随便问", HITS, llm=stub({"answer": "我不知道", "used": [], "refused": False}))
    assert res.refused and not res.citations


def test_garbage_output_is_refused_not_crashed():
    res = answer_from_hits("随便问", HITS, llm=stub("对不起，我不能回答这个问题。"))
    assert res.refused
    assert "JSON" in res.refuse_reason


def test_model_refusal_keeps_contact():
    res = answer_from_hits(
        "留学生奖学金条件",
        HITS,
        llm=stub({"refused": True, "refuse_reason": "现有条款未涉及留学生", "used": [],
                  "suggested_contact": "研究生院奖助办公室"}),
    )
    assert res.refused
    assert res.suggested_contact == "研究生院奖助办公室"


def test_no_hits_short_circuits_without_calling_model():
    def boom(prompt):
        raise AssertionError("没有召回结果时不该调用模型")

    res = answer_from_hits("随便问", [], llm=boom)
    assert res.refused
    assert "没有召回" in res.refuse_reason


def test_same_clause_from_compilation_is_merged():
    """汇编与独立制度里的同一条款（条号不同、换行不同）只留一条引用。"""
    hits = [
        {"title": "图书馆图书外借管理办法（修订）", "page": "", "section": "第二条 外借",
         "text": "第三条 外借\n2．每人均可同时外借30册图书，外借期限为60天。", "score": 0.65},
        {"title": "学生手册（2023版）", "page": 160, "section": "第二章",
         "text": "第十三条 外借\n2．每人均可同时外借30册图书，外借期限为\n60天。", "score": 0.63},
    ]
    res = answer_from_hits(
        "能借几本", hits, llm=stub({"answer": "30 册 [1][2]", "used": [1, 2], "refused": False})
    )
    assert [c.file for c in res.citations] == ["图书馆图书外借管理办法（修订）"]
    assert res.answer == "30 册 [1]"


def test_answer_markers_are_renumbered_to_match_citation_list():
    res = answer_from_hits(
        "问", HITS, llm=stub({"answer": "见 [2] 和 [1]", "used": [2, 1], "refused": False})
    )
    assert [c.file for c in res.citations] == [HITS[1]["title"], HITS[0]["title"]]
    assert res.answer == "见 [1] 和 [2]"


def test_used_index_is_deduped_and_capped():
    res = answer_from_hits(
        "问", HITS, llm=stub({"answer": "答 [1]", "used": [1, 1, 2], "refused": False})
    )
    assert [c.file for c in res.citations] == [HITS[0]["title"], HITS[1]["title"]]


def test_same_clause_from_three_sources_is_merged():
    """真实语料里的三份副本：汇编、学生手册、独立办法。

    正文只差条号、列表序号（`1．` / `1.` / 无）、标点和换行——只剥条号与空白
    是抓不到的（真实 badcase，转专业条件被引用三次）。
    """
    hits = [
        {"title": "教学管理文件汇编", "page": 42, "section": "第五章附则", "score": 0.772,
         "text": "第一条：申请转专业的基本条件\n1．学生确有专长，对转入专业感兴趣，转专业后更能发挥专长；\n"
                 "2．入学后因患某种疾病或生理缺陷（需有二级甲等及以上医院证明），或\n确有特殊困难（需学校认定），"
                 "不能在原专业学习，但仍能在其他专业学习者。"},
        {"title": "上海第二工业大学学生手册（2023版）", "page": 45, "section": "第四章 附 则", "score": 0.745,
         "text": "第一条：申请转专业的基本条件\n1.学生确有专长，对转入专业感兴趣，转专业后更能发挥专长；\n"
                 "入学后因患某种疾病或生理缺陷（需有二级甲等及以上医院证\n明），或确有特殊困难（需学校认定），"
                 "不能在原专业学习，但仍能在其他专业学习者。"},
        {"title": "上海第二工业大学学生转专业实施办法（修订）", "page": "", "section": "", "score": 0.697,
         "text": "第一条：申请转专业的基本条件\n学生确有专长，对转入专业感兴趣，转专业后更能发挥专长；\n"
                 "入学后因患某种疾病或生理缺陷（需有二级甲等及以上医院证明），或确有特殊困难（需学校认定），"
                 "不能在原专业学习，但仍能在其他专业学习者。"},
    ]
    res = answer_from_hits(
        "转专业需要什么条件", hits,
        llm=stub({"answer": "需要专长或身体原因 [1][2][3]", "used": [1, 2, 3], "refused": False}),
    )
    assert [c.file for c in res.citations] == ["教学管理文件汇编"]
    assert res.citations[0].page == 42
    assert res.answer == "需要专长或身体原因 [1]"


def test_dedupe_key_keeps_numbers_apart():
    """数字是条款内容（30 册 vs 10 册），不能当标点一样抹掉。"""
    from p1.generator import dedupe_key

    a = "第五条 教职工每人均可同时外借30册图书，外借期限为60天。"
    b = "第五条 教职工每人均可同时外借10册图书，外借期限为30天。"
    assert dedupe_key(a) != dedupe_key(b)
