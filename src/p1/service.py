from p1.contracts import AnswerResult


def answer(question: str) -> AnswerResult:
    return AnswerResult(
        question=question,
        answer="【骨架占位】检索与生成尚未接入。",
        refused=True,
        refuse_reason="not_implemented",
    )


if __name__ == "__main__":
    print(answer("缓考申请最晚什么时候交？").model_dump_json(indent=2))
