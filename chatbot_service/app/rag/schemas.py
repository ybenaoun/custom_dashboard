from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class RagDocument(BaseModel):
    doctype: str = Field(..., min_length=1, max_length=140)
    docname: str = Field(..., min_length=1, max_length=300)
    data: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    content: str | None = Field(default=None, max_length=500_000)
    modified: str | None = None


class RagIndexRequest(BaseModel):
    document: RagDocument


class RagDeleteRequest(BaseModel):
    doctype: str = Field(..., min_length=1, max_length=140)
    docname: str = Field(..., min_length=1, max_length=300)


class RagReindexBatchRequest(BaseModel):
    documents: list[RagDocument] = Field(..., min_length=1, max_length=200)


class RagAskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=4000)
    language: Literal["fr", "en"] = "fr"
    user: str | None = Field(default=None, max_length=300)
    roles: list[str] = Field(default_factory=list, max_length=100)
    company: str | None = Field(default=None, max_length=300)
    doctypes: list[str] = Field(default_factory=list, max_length=50)
    top_k: int | None = Field(default=None, ge=1, le=100)
    rerank_top_n: int | None = Field(default=None, ge=1, le=50)


class RagChunk(BaseModel):
    id: int
    doctype: str
    docname: str
    chunk_index: int
    content: str
    metadata: dict[str, Any]
    score: float | None = None
    rerank_score: float | None = None


class RagSource(BaseModel):
    doctype: str
    docname: str
    chunk_index: int
    score: float | None = None
    rerank_score: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RagIndexResponse(BaseModel):
    status: str
    doctype: str
    docname: str
    chunks: int


class RagDeleteResponse(BaseModel):
    status: str
    doctype: str
    docname: str
    deleted: int


class RagAskResponse(BaseModel):
    answer: str
    sources: list[RagSource] = Field(default_factory=list)
    retrieved_chunks: list[RagChunk] = Field(default_factory=list)
    confidence: float | None = None

