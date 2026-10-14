from pydantic import BaseModel, Field

# refuse_reason 是**机读 code**，给用户看的那句话放 answer。
# 谁来给也是设计的一部分：检索类由代码直接给（不过模型），条款类才轮到模型判。
RETRIEVAL_EMPTY = "retrieval_empty"            # 一条都没召回 —— 代码给
RETRIEVAL_LOW_SCORE = "retrieval_low_score"    # 召回了但分数低于前置阈值 —— 代码给
UNSUPPORTED_LANGUAGE = "unsupported_language"  # 非中文提问 —— 代码给（阶段 5 决定暂不支持）
BAD_MODEL_OUTPUT = "invalid_model_output"      # 模型输出不是合法 JSON —— 代码判
NO_VALID_CITATION = "no_valid_citation"        # 模型挑不出可核对的编号 —— 代码判
NO_EVIDENCE = "no_evidence_in_corpus"          # 条款在，但支撑不住这个问题 —— 模型判

# 全部取值，供校验/文档用
REFUSE_CODES = (RETRIEVAL_EMPTY, RETRIEVAL_LOW_SCORE, UNSUPPORTED_LANGUAGE,
                BAD_MODEL_OUTPUT, NO_VALID_CITATION, NO_EVIDENCE)


class Citation(BaseModel):
    file: str
    page: int | None = None
    section: str | None = None
    snippet: str
    score: float


class AnswerResult(BaseModel):
    question: str
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    confidence: float = 0.0
    refused: bool = False
    refuse_reason: str | None = None
    suggested_contact: str | None = None
    # 检索 top-1 分数：调阈值、复盘拒答都靠它，所以随结果一起返回
    top_retrieval_score: float | None = None
