from __future__ import annotations

import json
import logging
import re
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.config import settings
from app.deps import get_current_user
from app.llm import cohere_client
from app.llm.prompts import system_prompt
from app.rag import rag_service
from app.rag.schemas import RagAskRequest
from app.schemas.chat import ChatRequest, ChatResponse


router = APIRouter()
logger = logging.getLogger("custom_dashboard.chat")


def _build_messages(req: ChatRequest) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt(req.language)}]
    for msg in req.history:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": req.message})
    return messages


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


def _clean_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item or "").strip()]


def _source_payload(retrieval: rag_service.RagRetrievalResult | None) -> list[dict[str, Any]]:
    if not retrieval:
        return []
    return [
        source.model_dump(mode="json", exclude_none=True)
        for source in retrieval.sources
    ]


def _rag_system_message(retrieval: rag_service.RagRetrievalResult, language: str) -> dict[str, str]:
    if language == "en":
        instructions = (
            "Indexed ERP context follows. It has already been filtered for the current user's "
            "permissions. Use it only when it is relevant. If the answer is not present in this "
            "context and no ERP tool result provides it, clearly say that the information is not "
            "available in the indexed context. Cite indexed sources as [source N] when you use them."
        )
    else:
        instructions = (
            "Contexte ERP indexe ci-dessous. Il a deja ete filtre selon les permissions de "
            "l'utilisateur courant. Utilise-le seulement lorsqu'il est pertinent. Si la reponse "
            "n'est pas presente dans ce contexte et qu'aucun tool ERP ne la fournit, dis clairement "
            "que l'information n'existe pas dans le contexte indexe. Cite les sources indexees sous "
            "la forme [source N] quand tu les utilises."
        )
    return {
        "role": "system",
        "content": f"{instructions}\n\n[RAG_CONTEXT]\n{retrieval.context}",
    }


def _no_rag_context_answer(language: str) -> str:
    if language == "en":
        return "I could not find this information in the indexed context."
    return "Je ne trouve pas cette information dans le contexte indexe."


def _metadata_task(req: ChatRequest) -> str:
    metadata = req.metadata or {}
    return str(metadata.get("task") or metadata.get("source") or "").strip()


def _json_object_from_text(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    try:
        payload = json.loads(text)
        return payload if isinstance(payload, dict) else None
    except json.JSONDecodeError:
        pass

    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        try:
            payload = json.loads(fenced.group(1))
            return payload if isinstance(payload, dict) else None
        except json.JSONDecodeError:
            pass

    inline = re.search(r"\{.*\}", text, re.DOTALL)
    if inline:
        try:
            payload = json.loads(inline.group())
            return payload if isinstance(payload, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def _chat_response(result: dict[str, Any], response: str, used_tools: list[str] | None = None) -> ChatResponse:
    return ChatResponse(
        response=response,
        model=settings.cohere_model,
        input_tokens=int(result.get("input_tokens") or 0),
        output_tokens=int(result.get("output_tokens") or 0),
        rag_sources=[],
        rag_confidence=None,
        used_tools=used_tools or [],
    )


async def _classify_intent(req: ChatRequest, user: dict[str, Any]) -> ChatResponse:
    valid_intents = req.metadata.get("valid_intents") if isinstance(req.metadata, dict) else None
    if not isinstance(valid_intents, list) or not valid_intents:
        valid_intents = ["general_chat"]
    valid_intents = [str(intent) for intent in valid_intents]

    messages = [
        {
            "role": "system",
            "content": (
                "Tu es un service de classification d'intentions pour un chatbot ERP. "
                "Retourne uniquement un objet JSON valide avec les cles intent, period, "
                "language et entity. L'intention doit appartenir a la liste fournie."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "message": req.message,
                    "language": req.language,
                    "valid_intents": valid_intents,
                },
                ensure_ascii=False,
            ),
        },
    ]
    result = await cohere_client.chat(messages, user=user, language=req.language, use_tools=False)
    payload = _json_object_from_text(result["text"]) or {}

    intent = str(payload.get("intent") or "general_chat")
    if intent not in valid_intents:
        intent = "general_chat" if "general_chat" in valid_intents else valid_intents[0]

    response_payload = {
        "intent": intent,
        "period": payload.get("period") or "all",
        "language": payload.get("language") or req.language,
        "entity": payload.get("entity"),
    }
    return _chat_response(result, json.dumps(response_payload, ensure_ascii=False))


async def _generate_bi_dashboard_spec(req: ChatRequest, user: dict[str, Any]) -> ChatResponse:
    """Generic JSON-only call used by bi_studio for dashboard spec generation.

    The caller passes:
      - req.message: the user prompt (already contains all dataset metadata)
      - req.metadata.system: optional system message override
      - req.metadata.repair: optional dict {invalid_json, errors, schema}
        triggering a repair-prompt flow (one shot).
    Returns ChatResponse with .response containing the raw JSON object as string.
    """
    metadata = req.metadata if isinstance(req.metadata, dict) else {}
    system_message = metadata.get("system") or (
        "You are an expert BI dashboard designer and data analyst. "
        "Your task is to design a dashboard specification as strict JSON. "
        "You do not calculate final metric values. "
        "The application language is French. All user-facing text values in the JSON "
        "must be written in French. JSON keys must remain in English. "
        "Return only valid JSON. Do not include markdown. Do not include explanations."
    )
    user_message = req.message
    repair = metadata.get("repair")
    if isinstance(repair, dict):
        user_message = (
            "Le JSON suivant est invalide. Corrige-le en respectant strictement le schema attendu. "
            "Retourne uniquement le JSON corrige, sans markdown ni explication.\n\n"
            f"JSON invalide:\n{json.dumps(repair.get('invalid_json'), ensure_ascii=False, default=str)}\n\n"
            f"Erreurs de validation:\n{json.dumps(repair.get('errors') or [], ensure_ascii=False)}\n\n"
            f"Schema attendu:\n{json.dumps(repair.get('schema') or {}, ensure_ascii=False)}"
        )

    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": user_message},
    ]
    result = await cohere_client.chat(messages, user=user, language=req.language, use_tools=False)
    payload = _json_object_from_text(result["text"])
    if payload is None:
        return _chat_response(result, json.dumps({"error": "invalid_json", "raw": result["text"]}, ensure_ascii=False))
    return _chat_response(result, json.dumps(payload, ensure_ascii=False, default=str))


async def _generate_dashboard_widget_insight(req: ChatRequest, user: dict[str, Any]) -> ChatResponse:
    metadata = req.metadata if isinstance(req.metadata, dict) else {}
    expected_schema = metadata.get("json_schema") or {
        "summary": "string",
        "anomalies": ["string"],
        "recommendations": ["string"],
    }
    messages = [
        {
            "role": "system",
            "content": (
                "Tu es un service d'analyse intelligente pour des widgets de tableau de bord ERP. "
                "Utilise uniquement le contexte fourni. Retourne uniquement un objet JSON valide "
                "respectant le schema attendu, sans markdown ni commentaire."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "widget_name": metadata.get("widget_name"),
                    "filters": metadata.get("filters") or {},
                    "context": metadata.get("context") or {},
                    "expected_schema": expected_schema,
                    "request": req.message,
                },
                ensure_ascii=False,
                default=str,
            ),
        },
    ]
    result = await cohere_client.chat(messages, user=user, language=req.language, use_tools=False)
    payload = _json_object_from_text(result["text"])
    if payload is None:
        payload = {
            "summary": result["text"],
            "anomalies": [],
            "recommendations": [],
        }
    return _chat_response(result, json.dumps(payload, ensure_ascii=False, default=str))


async def _retrieve_rag(req: ChatRequest, user: dict[str, Any]) -> rag_service.RagRetrievalResult | None:
    if not settings.rag_chat_enabled or not settings.database_url or not req.use_rag:
        return None

    rag_user = str(user.get("user") or user.get("sub") or "").strip() or None
    roles = _clean_list(user.get("roles"))
    company = req.company or user.get("company")

    try:
        retrieval = await rag_service.retrieve(
            RagAskRequest(
                question=req.message,
                language=req.language,
                user=rag_user,
                roles=roles,
                company=str(company).strip() if company else None,
                doctypes=req.doctypes,
            )
        )
    except Exception:
        logger.exception("chat_rag_retrieval_failed", extra={"user": rag_user})
        return None

    return retrieval if retrieval.has_context else None


def _with_rag_context(
    messages: list[dict[str, Any]],
    retrieval: rag_service.RagRetrievalResult | None,
    language: str,
) -> list[dict[str, Any]]:
    if not retrieval or not retrieval.has_context:
        return messages
    if not messages:
        return [_rag_system_message(retrieval, language)]
    return [messages[0], _rag_system_message(retrieval, language), *messages[1:]]


async def _sse_events(
    events: AsyncIterator[dict[str, Any]],
    retrieval: rag_service.RagRetrievalResult | None = None,
) -> AsyncIterator[str]:
    rag_sources = _source_payload(retrieval)
    try:
        if rag_sources:
            yield _sse(
                "rag_sources",
                {"sources": rag_sources, "confidence": retrieval.confidence if retrieval else None},
            )
        async for item in events:
            event = item.get("event", "message")
            data = item.get("data", {})
            if event == "done" and rag_sources:
                data = {
                    **data,
                    "rag_sources": rag_sources,
                    "rag_confidence": retrieval.confidence if retrieval else None,
                }
            yield _sse(event, data)
    except Exception as exc:
        yield _sse("error", {"message": str(exc)})


@router.post("/chat", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    user: dict = Depends(get_current_user),
) -> ChatResponse:
    task = _metadata_task(req)
    if task == "intent_classification":
        return await _classify_intent(req, user)
    if task in {"dashboard_widget_insight", "dashboard_ai_widget"}:
        return await _generate_dashboard_widget_insight(req, user)
    if task in {"bi_dashboard_generation", "bi_dashboard_repair"}:
        return await _generate_bi_dashboard_spec(req, user)

    retrieval = await _retrieve_rag(req, user)
    if req.use_rag and not req.use_tools and retrieval is None:
        return ChatResponse(
            response=_no_rag_context_answer(req.language),
            model=settings.cohere_model,
            input_tokens=0,
            output_tokens=0,
            rag_sources=[],
            rag_confidence=0.0,
            used_tools=[],
        )
    messages = _with_rag_context(_build_messages(req), retrieval, req.language)

    result = await cohere_client.chat(
        messages,
        user=user,
        language=req.language,
        use_tools=req.use_tools,
    )

    return ChatResponse(
        response=result["text"],
        model=settings.cohere_model,
        input_tokens=result["input_tokens"],
        output_tokens=result["output_tokens"],
        rag_sources=_source_payload(retrieval),
        rag_confidence=retrieval.confidence if retrieval else None,
        used_tools=result.get("used_tools", []),
    )


@router.post("/chat/stream")
async def chat_stream(
    req: ChatRequest,
    user: dict = Depends(get_current_user),
) -> StreamingResponse:
    retrieval = await _retrieve_rag(req, user)
    if req.use_rag and not req.use_tools and retrieval is None:
        async def no_context_events() -> AsyncIterator[str]:
            answer = _no_rag_context_answer(req.language)
            yield _sse("token", {"text": answer})
            yield _sse(
                "done",
                {
                    "response": answer,
                    "model": settings.cohere_model,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "rag_sources": [],
                    "rag_confidence": 0.0,
                    "used_tools": [],
                },
            )

        return StreamingResponse(
            no_context_events(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    messages = _with_rag_context(_build_messages(req), retrieval, req.language)
    events = cohere_client.chat_stream(
        messages,
        user=user,
        language=req.language,
        use_tools=req.use_tools,
    )
    return StreamingResponse(
        _sse_events(events, retrieval),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
