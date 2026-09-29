from pydantic import BaseModel, Field


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
