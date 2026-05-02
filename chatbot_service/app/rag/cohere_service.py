from __future__ import annotations

import logging
from typing import Any

import cohere.errors as cohere_errors
from fastapi import HTTPException, status

from app.config import settings
from app.llm.cohere_client import get_client


logger = logging.getLogger("custom_dashboard.rag.cohere")

COHERE_EXCEPTIONS = (
    cohere_errors.TooManyRequestsError,
    cohere_errors.UnauthorizedError,
    cohere_errors.BadRequestError,
    cohere_errors.ForbiddenError,
    cohere_errors.InvalidTokenError,
    cohere_errors.UnprocessableEntityError,
    cohere_errors.InternalServerError,
    cohere_errors.ServiceUnavailableError,
    cohere_errors.GatewayTimeoutError,
)


def _cohere_http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, cohere_errors.TooManyRequestsError):
        return HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Cohere rate limit reached")
    if isinstance(exc, (cohere_errors.UnauthorizedError, cohere_errors.InvalidTokenError)):
        return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Cohere API key invalid")
    if isinstance(exc, cohere_errors.BadRequestError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Cohere bad request: {exc}")
    return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Cohere request failed: {exc}")


def _extract_text(message: Any) -> str:
    if not message or not message.content:
        return ""
    return "".join(block.text for block in message.content if block.type == "text")


async def embed_documents(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    client = get_client()
    try:
        response = await client.embed(
            model=settings.rag_embed_model,
            input_type="search_document",
            texts=texts,
            embedding_types=["float"],
        )
    except COHERE_EXCEPTIONS as exc:
        logger.exception("rag_embed_documents_failed", extra={"count": len(texts)})
        raise _cohere_http_error(exc) from exc
    return response.embeddings.float_ or []


async def embed_query(question: str) -> list[float]:
    client = get_client()
    try:
        response = await client.embed(
            model=settings.rag_embed_model,
            input_type="search_query",
            texts=[question],
            embedding_types=["float"],
        )
    except COHERE_EXCEPTIONS as exc:
        logger.exception("rag_embed_query_failed")
        raise _cohere_http_error(exc) from exc
    embeddings = response.embeddings.float_ or []
    return embeddings[0] if embeddings else []


async def rerank(question: str, documents: list[str], top_n: int) -> list[tuple[int, float]]:
    if not documents:
        return []
    client = get_client()
    try:
        response = await client.rerank(
            model=settings.rag_rerank_model,
            query=question,
            documents=documents,
            top_n=min(top_n, len(documents)),
        )
    except COHERE_EXCEPTIONS as exc:
        logger.exception("rag_rerank_failed", extra={"count": len(documents)})
        raise _cohere_http_error(exc) from exc
    return [(item.index, float(item.relevance_score)) for item in response.results]


async def answer_with_context(question: str, context: str, language: str) -> str:
    client = get_client()
    if language == "en":
        system = (
            "You are a RAG assistant for ERPNext. Answer only from the provided context. "
            "If the answer is not present in the context, say that the information does not exist "
            "in the indexed context. Do not use outside knowledge."
        )
    else:
        system = (
            "Tu es un assistant RAG pour ERPNext. Reponds uniquement a partir du contexte fourni. "
            "Si la reponse n'est pas presente dans le contexte, dis clairement que l'information "
            "n'existe pas dans le contexte indexe. N'utilise aucune connaissance externe."
        )

    try:
        response = await client.chat(
            model=settings.cohere_model,
            messages=[
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": (
                        "Contexte indexe:\n"
                        f"{context}\n\n"
                        f"Question: {question}"
                    ),
                },
            ],
            temperature=0.1,
            max_tokens=settings.cohere_max_tokens,
        )
    except COHERE_EXCEPTIONS as exc:
        logger.exception("rag_answer_failed")
        raise _cohere_http_error(exc) from exc
    return _extract_text(response.message).strip()

