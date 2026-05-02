from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import cohere
import cohere.errors as cohere_errors
from fastapi import HTTPException, status

from app.config import settings
from app.tools.frappe_tools import COHERE_TOOLS, execute_tool_calls


_client: cohere.AsyncClientV2 | None = None

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


def get_client() -> cohere.AsyncClientV2:
    global _client
    if _client is None:
        _client = cohere.AsyncClientV2(api_key=settings.cohere_api_key)
    return _client


def _message_text(message: Any) -> str:
    text = ""
    if message and message.content:
        text = "".join(
            block.text for block in message.content if block.type == "text"
        )
    return text


def _usage_tokens(response_or_delta: Any) -> tuple[int, int]:
    usage = response_or_delta.usage.tokens if response_or_delta.usage and response_or_delta.usage.tokens else None
    return (
        int(usage.input_tokens) if usage and usage.input_tokens else 0,
        int(usage.output_tokens) if usage and usage.output_tokens else 0,
    )


def _dump_model(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", exclude_none=True)
    return value


def _assistant_tool_message(message: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"role": "assistant"}
    if message.tool_calls:
        payload["tool_calls"] = [_dump_model(tool_call) for tool_call in message.tool_calls]
    if message.tool_plan:
        payload["tool_plan"] = message.tool_plan
    content = _message_text(message)
    if content:
        payload["content"] = content
    return payload


def _stream_text(event: Any) -> str:
    delta = event.delta
    message = delta.message if delta else None
    content = message.content if message else None
    return content.text if content and content.text else ""


def _stream_tool_plan(event: Any) -> str:
    delta = event.delta
    message = delta.message if delta else None
    return message.tool_plan if message and message.tool_plan else ""


def _stream_tool_start(event: Any) -> dict[str, Any] | None:
    delta = event.delta
    message = delta.message if delta else None
    tool_call = message.tool_calls if message else None
    if not tool_call:
        return None
    function = tool_call.function
    return {
        "id": tool_call.id,
        "type": tool_call.type,
        "function": {
            "name": function.name if function else None,
            "arguments": function.arguments if function and function.arguments else "",
        },
    }


def _stream_tool_arguments_delta(event: Any) -> str:
    delta = event.delta
    message = delta.message if delta else None
    tool_calls = message.tool_calls if message else None
    function = tool_calls.function if tool_calls else None
    return function.arguments if function and function.arguments else ""


def _tool_call_index(event: Any, fallback: int) -> int:
    return int(event.index) if event.index is not None else fallback


def _finalize_stream_tool_calls(tool_call_parts: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    tool_calls: list[dict[str, Any]] = []
    for _, tool_call in sorted(tool_call_parts.items()):
        function = tool_call.setdefault("function", {})
        function["arguments"] = function.get("arguments") or "{}"
        tool_calls.append(tool_call)
    return tool_calls


def _tool_call_name(tool_call: Any) -> str:
    if isinstance(tool_call, dict):
        function = tool_call.get("function") or {}
        return str(function.get("name") or "").strip()
    function = getattr(tool_call, "function", None)
    return str(getattr(function, "name", "") or "").strip()


def _cohere_error_response(exc: Exception) -> HTTPException:
    if isinstance(exc, cohere_errors.TooManyRequestsError):
        return HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Cohere rate limit reached, retry later",
        )
    if isinstance(exc, (cohere_errors.UnauthorizedError, cohere_errors.InvalidTokenError)):
        return HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Cohere API key invalid",
        )
    if isinstance(exc, cohere_errors.BadRequestError):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cohere bad request: {exc}",
        )
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"Cohere request failed: {exc}",
    )


async def chat(
    messages: list[dict[str, Any]],
    user: dict[str, Any] | None = None,
    language: str = "fr",
    use_tools: bool = True,
) -> dict[str, Any]:
    client = get_client()
    working_messages = list(messages)
    total_input_tokens = 0
    total_output_tokens = 0
    used_tools: list[str] = []

    for _ in range(max(1, settings.cohere_max_tool_rounds)):
        try:
            kwargs: dict[str, Any] = {
                "model": settings.cohere_model,
                "messages": working_messages,
                "temperature": settings.cohere_temperature,
                "max_tokens": settings.cohere_max_tokens,
            }
            if use_tools:
                kwargs["tools"] = COHERE_TOOLS
            response = await client.chat(**kwargs)
        except COHERE_EXCEPTIONS as exc:
            raise _cohere_error_response(exc) from exc

        input_tokens, output_tokens = _usage_tokens(response)
        total_input_tokens += input_tokens
        total_output_tokens += output_tokens

        tool_calls = response.message.tool_calls if response.message else None
        if use_tools and response.finish_reason == "TOOL_CALL" and tool_calls:
            used_tools.extend(name for name in (_tool_call_name(call) for call in tool_calls) if name)
            working_messages.append(_assistant_tool_message(response.message))
            tool_messages = await execute_tool_calls(tool_calls, user or {}, language)
            working_messages.extend(tool_messages)
            continue

        return {
            "text": _message_text(response.message),
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens,
            "used_tools": used_tools,
        }

    return {
        "text": "Je n'ai pas pu finaliser la réponse après plusieurs appels outils.",
        "input_tokens": total_input_tokens,
        "output_tokens": total_output_tokens,
        "used_tools": used_tools,
    }


async def chat_stream(
    messages: list[dict[str, Any]],
    user: dict[str, Any] | None = None,
    language: str = "fr",
    use_tools: bool = True,
) -> AsyncIterator[dict[str, Any]]:
    client = get_client()
    working_messages = list(messages)
    total_input_tokens = 0
    total_output_tokens = 0
    full_text_parts: list[str] = []
    used_tools: list[str] = []

    for _ in range(max(1, settings.cohere_max_tool_rounds)):
        finish_reason = None
        tool_call_parts: dict[int, dict[str, Any]] = {}

        try:
            kwargs: dict[str, Any] = {
                "model": settings.cohere_model,
                "messages": working_messages,
                "temperature": settings.cohere_temperature,
                "max_tokens": settings.cohere_max_tokens,
            }
            if use_tools:
                kwargs["tools"] = COHERE_TOOLS
            stream = client.chat_stream(**kwargs)

            async for event in stream:
                if event.type == "content-delta":
                    text = _stream_text(event)
                    if text:
                        full_text_parts.append(text)
                        yield {"event": "token", "data": {"text": text}}

                elif event.type == "tool-plan-delta":
                    plan = _stream_tool_plan(event)
                    if plan:
                        yield {"event": "tool_plan", "data": {"text": plan}}

                elif event.type == "tool-call-start":
                    tool_call = _stream_tool_start(event)
                    if tool_call:
                        index = _tool_call_index(event, len(tool_call_parts))
                        tool_call_parts[index] = tool_call
                        yield {
                            "event": "tool_call",
                            "data": {
                                "tool_call_id": tool_call["id"],
                                "name": tool_call["function"].get("name"),
                            },
                        }

                elif event.type == "tool-call-delta":
                    index = _tool_call_index(event, max(len(tool_call_parts) - 1, 0))
                    tool_call = tool_call_parts.setdefault(
                        index,
                        {"id": f"tool_{index}", "type": "function", "function": {}},
                    )
                    function = tool_call.setdefault("function", {})
                    function["arguments"] = (
                        function.get("arguments", "") + _stream_tool_arguments_delta(event)
                    )

                elif event.type == "message-end":
                    delta = event.delta
                    finish_reason = delta.finish_reason if delta else None
                    if delta and delta.usage:
                        input_tokens, output_tokens = _usage_tokens(delta)
                        total_input_tokens += input_tokens
                        total_output_tokens += output_tokens
        except COHERE_EXCEPTIONS as exc:
            error = _cohere_error_response(exc)
            yield {"event": "error", "data": {"message": error.detail}}
            return

        tool_calls = _finalize_stream_tool_calls(tool_call_parts)
        if use_tools and finish_reason == "TOOL_CALL" and tool_calls:
            used_tools.extend(name for name in (_tool_call_name(call) for call in tool_calls) if name)
            working_messages.append({"role": "assistant", "tool_calls": tool_calls})
            tool_messages = await execute_tool_calls(tool_calls, user or {}, language)
            for tool_message in tool_messages:
                yield {
                    "event": "tool_result",
                    "data": {
                        "tool_call_id": tool_message["tool_call_id"],
                        "content": tool_message["content"],
                    },
                }
            working_messages.extend(tool_messages)
            continue

        yield {
            "event": "done",
            "data": {
                "response": "".join(full_text_parts),
                "model": settings.cohere_model,
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
                "used_tools": used_tools,
            },
        }
        return

    yield {
        "event": "error",
        "data": {"message": "Tool calling interrompu: nombre maximum de tours atteint"},
    }
