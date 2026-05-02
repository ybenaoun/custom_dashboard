from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from app.config import settings
from app.rag import cohere_service, vector_store
from app.rag.schemas import (
    RagAskRequest,
    RagAskResponse,
    RagChunk,
    RagDeleteResponse,
    RagDocument,
    RagIndexResponse,
    RagSource,
)


logger = logging.getLogger("custom_dashboard.rag.service")

SKIP_TEXT_KEYS = {
    "doctype",
    "name",
    "owner",
    "creation",
    "modified",
    "modified_by",
    "idx",
    "docstatus",
}


@dataclass
class RagRetrievalResult:
    context: str = ""
    sources: list[RagSource] = field(default_factory=list)
    retrieved_chunks: list[RagChunk] = field(default_factory=list)
    selected_chunks: list[RagChunk] = field(default_factory=list)
    confidence: float = 0.0

    @property
    def has_context(self) -> bool:
        return bool(self.selected_chunks and self.context)


def _flatten(value: Any, prefix: str = "") -> list[str]:
    lines: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key in SKIP_TEXT_KEYS or item in (None, "", [], {}):
                continue
            next_prefix = f"{prefix}.{key}" if prefix else str(key)
            lines.extend(_flatten(item, next_prefix))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            lines.extend(_flatten(item, f"{prefix}[{index}]"))
    else:
        lines.append(f"{prefix}: {value}")
    return lines


def document_to_text(document: RagDocument) -> str:
    if document.content and document.content.strip():
        return document.content.strip()
    header = [f"DocType: {document.doctype}", f"Document: {document.docname}"]
    return "\n".join(header + _flatten(document.data))


def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    text = " ".join(text.split())
    if not text:
        return []
    if chunk_size <= 0:
        return [text]
    overlap = max(0, min(overlap, chunk_size - 1))
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start = end - overlap
    return chunks


async def index_document(document: RagDocument) -> RagIndexResponse:
    text = document_to_text(document)
    chunks = chunk_text(text, settings.rag_chunk_size, settings.rag_chunk_overlap)
    metadata = dict(document.metadata or {})
    metadata.update(
        {
            "doctype": document.doctype,
            "docname": document.docname,
            "modified": document.modified or metadata.get("modified"),
        }
    )

    if not chunks:
        deleted = await vector_store.delete_document(document.doctype, document.docname)
        logger.info(
            "rag_empty_document_deleted",
            extra={"doctype": document.doctype, "docname": document.docname, "deleted": deleted},
        )
        return RagIndexResponse(status="empty", doctype=document.doctype, docname=document.docname, chunks=0)

    embeddings = await cohere_service.embed_documents(chunks)
    count = await vector_store.upsert_chunks(
        doctype=document.doctype,
        docname=document.docname,
        chunks=chunks,
        metadata=metadata,
        embeddings=embeddings,
    )
    return RagIndexResponse(status="indexed", doctype=document.doctype, docname=document.docname, chunks=count)


async def delete_document(doctype: str, docname: str) -> RagDeleteResponse:
    deleted = await vector_store.delete_document(doctype, docname)
    return RagDeleteResponse(status="deleted", doctype=doctype, docname=docname, deleted=deleted)


def _sources_from_chunks(chunks: list[RagChunk]) -> list[RagSource]:
    return [
        RagSource(
            doctype=chunk.doctype,
            docname=chunk.docname,
            chunk_index=chunk.chunk_index,
            score=chunk.score,
            rerank_score=chunk.rerank_score,
            metadata=chunk.metadata,
        )
        for chunk in chunks
    ]


def _context_from_chunks(chunks: list[RagChunk]) -> str:
    sections = []
    for index, chunk in enumerate(chunks, start=1):
        source = {
            "source": index,
            "doctype": chunk.doctype,
            "docname": chunk.docname,
            "chunk_index": chunk.chunk_index,
            "metadata": chunk.metadata,
        }
        sections.append(
            "[SOURCE]\n"
            f"{json.dumps(source, ensure_ascii=False, default=str)}\n"
            "[CONTENT]\n"
            f"{chunk.content}"
        )
    return "\n\n".join(sections)


async def retrieve(request: RagAskRequest) -> RagRetrievalResult:
    """Retrieve and rerank RAG chunks without generating the final answer."""
    if not request.user and not request.roles:
        return RagRetrievalResult()

    top_k = request.top_k or settings.rag_top_k
    rerank_top_n = request.rerank_top_n or settings.rag_rerank_top_n

    query_embedding = await cohere_service.embed_query(request.question)
    retrieved = await vector_store.search_similar(
        embedding=query_embedding,
        top_k=top_k,
        doctypes=request.doctypes,
        company=request.company,
        user=request.user,
        roles=request.roles,
    )
    if not retrieved:
        return RagRetrievalResult()

    reranked = await cohere_service.rerank(
        request.question,
        [chunk.content for chunk in retrieved],
        min(rerank_top_n, len(retrieved)),
    )
    selected: list[RagChunk] = []
    for index, score in reranked:
        chunk = retrieved[index]
        chunk.rerank_score = score
        if score >= settings.rag_min_relevance:
            selected.append(chunk)

    if not selected:
        return RagRetrievalResult(retrieved_chunks=retrieved)

    confidence = max((chunk.rerank_score or 0.0) for chunk in selected)
    return RagRetrievalResult(
        context=_context_from_chunks(selected),
        sources=_sources_from_chunks(selected),
        retrieved_chunks=retrieved,
        selected_chunks=selected,
        confidence=confidence,
    )


async def ask(request: RagAskRequest) -> RagAskResponse:
    retrieval = await retrieve(request)
    if not retrieval.has_context:
        return RagAskResponse(
            answer=_no_context_answer(request.language),
            sources=[],
            retrieved_chunks=retrieval.retrieved_chunks,
            confidence=0.0,
        )

    answer = await cohere_service.answer_with_context(request.question, retrieval.context, request.language)
    return RagAskResponse(
        answer=answer or _no_context_answer(request.language),
        sources=retrieval.sources,
        retrieved_chunks=retrieval.selected_chunks,
        confidence=retrieval.confidence,
    )


def _no_context_answer(language: str) -> str:
    if language == "en":
        return "I could not find this information in the indexed context."
    return "Je ne trouve pas cette information dans le contexte indexe."
