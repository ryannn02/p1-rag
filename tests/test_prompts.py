import json
import re
from pathlib import Path

import pytest

PROMPT_DIR = Path("prompts")
PROMPTS = sorted(PROMPT_DIR.glob("*/*.md"))


def _id(p):
    return f"{p.parent.name}/{p.stem}"


def _cases(p):
    path = p.parent / "cases.jsonl"
    assert path.exists(), f"{p} 缺少 cases.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_prompts_dir_not_empty():
    assert PROMPTS, "prompts/ 下没有任何提示词"


@pytest.mark.parametrize("p", PROMPTS, ids=_id)
def test_prompt_is_versioned(p):
    assert re.fullmatch(r"v\d+", p.stem), f"{p.name} 必须形如 v1.md"


@pytest.mark.parametrize("p", PROMPTS, ids=_id)
def test_v1_is_kept(p):
    assert (p.parent / "v1.md").exists(), f"{p.parent} 缺少 v1.md，历史链断了"


@pytest.mark.parametrize("p", PROMPTS, ids=_id)
def test_prompt_has_placeholder(p):
    assert "{{" in p.read_text(encoding="utf-8"), f"{p} 里没有 {{占位符}}"


@pytest.mark.parametrize("p", PROMPTS, ids=_id)
def test_cases_are_wellformed(p):
    rows = _cases(p)
    assert rows, f"{p.parent}/cases.jsonl 是空的"
    for i, row in enumerate(rows, 1):
        assert str(row.get("input", "")).strip(), f"第 {i} 行缺 input"
        assert str(row.get("expected", "")).strip(), f"第 {i} 行缺 expected"
        assert isinstance(row.get("note", ""), str), f"第 {i} 行的 note 必须是字符串"
