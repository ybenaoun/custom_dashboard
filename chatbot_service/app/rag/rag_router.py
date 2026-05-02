from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.config import settings
from app.rag import rag_service
from app.rag.schemas import (
    RagAskRequest,
    RagAskResponse,
    RagDeleteRequest,
    RagDeleteResponse,
    RagIndexRequest,
    RagIndexResponse,
    RagReindexBatchRequest,
)


logger = logging.getLogger("custom_dashboard.rag.router")
router = APIRouter(prefix="/rag", tags=["rag"])


def verify_internal_api_key(x_rag_api_key: Annotated[str | None, Header()] = None) -> None:
    if not settings.rag_internal_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RAG_INTERNAL_API_KEY is not configured",
        )
    if x_rag_api_key != settings.rag_internal_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid RAG API key")


@router.post("/index", response_model=RagIndexResponse)
async def index_document(req: RagIndexRequest, _: None = Depends(verify_internal_api_key)) -> RagIndexResponse:
    try:
        return await rag_service.index_document(req.document)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(
            "rag_index_failed",
            extra={"doctype": req.document.doctype, "docname": req.document.docname},
        )
        raise HTTPException(status_code=500, detail=f"RAG index failed: {exc}") from exc


@router.post("/delete", response_model=RagDeleteResponse)
async def delete_document(req: RagDeleteRequest, _: None = Depends(verify_internal_api_key)) -> RagDeleteResponse:
    try:
        return await rag_service.delete_document(req.doctype, req.docname)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("rag_delete_failed", extra={"doctype": req.doctype, "docname": req.docname})
        raise HTTPException(status_code=500, detail=f"RAG delete failed: {exc}") from exc


@router.post("/ask", response_model=RagAskResponse)
async def ask(req: RagAskRequest, _: None = Depends(verify_internal_api_key)) -> RagAskResponse:
    try:
        return await rag_service.ask(req)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("rag_ask_failed")
        raise HTTPException(status_code=500, detail=f"RAG ask failed: {exc}") from exc


@router.post("/reindex-batch")
async def reindex_batch(req: RagReindexBatchRequest, _: None = Depends(verify_internal_api_key)) -> dict:
    results = []
    for document in req.documents:
        results.append(await rag_service.index_document(document))
    return {"status": "indexed", "count": len(results), "results": results}
