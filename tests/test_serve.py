"""演示服务的入参校验。不启服务、不联网。"""

import sys

sys.path.insert(0, ".")
from scripts.serve import parse_question  # noqa: E402


def test_parse_question_accepts_normal_input():
    assert parse_question('{"question": "  图书馆借书  "}'.encode()) == ("图书馆借书", None)


def test_parse_question_rejects_empty_and_bad_body():
    assert parse_question('{"question": "   "}'.encode())[1] == "问题不能为空"
    assert parse_question(b"not json")[1] == "请求体不是合法 JSON"
    assert parse_question(b"")[1] == "问题不能为空"


def test_parse_question_rejects_overlong():
    body = '{"question": "' + "问" * 201 + '"}'
    question, error = parse_question(body.encode())
    assert question is None and "太长" in error
