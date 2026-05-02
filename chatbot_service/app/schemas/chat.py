from __future__ import annotations

from typing import Any
from typing import Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str = Field(..., min_length=1, max_length=20000)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=20000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=20)
    language: Literal["fr", "en"] = "fr"
    company: str | None = Field(default=None, max_length=300)
    doctypes: list[str] = Field(default_factory=list, max_length=50)
    use_rag: bool = True
    use_tools: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    response: str
    model: str
    input_tokens: int
    output_tokens: int
    rag_sources: list[dict[str, Any]] = Field(default_factory=list)
    rag_confidence: float | None = None
    used_tools: list[str] = Field(default_factory=list)
