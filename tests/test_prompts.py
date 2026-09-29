import json
from pathlib import Path

import pytest

PROMPTS = sorted(Path("prompts").glob("*/*.md"))


@pytest.mark.parametrize("p", PROMPTS, ids=lambda p: f"{p.parent.name}/{p.stem}")
def test_prompt_versioned(p):
    assert p.stem.startswith("v"), "提示词文件名必须带版本号，如 v1.md"


@pytest.mark.parametrize("p", PROMPTS, ids=lambda p: f"{p.parent.name}/{p.stem}")
def test_prompt_has_cases(p):
    cases = p.parent / "cases.jsonl"
    assert cases.exists(), f"{p} 缺少 cases.jsonl"
    for line in cases.read_text(encoding="utf-8").splitlines():
        if line.strip():
            json.loads(line)
