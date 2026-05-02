from __future__ import annotations

import json
import logging
from typing import Any

from app.config import settings
from app.rag.schemas import RagChunk


logger = logging.getLogger("custom_dashboard.rag.vector_store")

_pool: Any | None = None
_pool_opened = False


def _embedding_literal(embedding: list[float]) -> str:
    return "[" + ",".join(f"{float(value):.8f}" for value in embedding) + "]"


def get_pool() -> Any:
    global _pool
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is not configured")
    if _pool is None:
        from psycopg.rows import dict_row
        from psycopg_pool import AsyncConnectionPool

        _pool = AsyncConnectionPool(
            settings.database_url,
            min_size=1,
            max_size=settings.rag_db_pool_size,
            kwargs={"row_factory": dict_row},
            open=False,
        )
    return _pool


async def open_pool() -> None:
    global _pool_opened
    pool = get_pool()
    if _pool_opened:
        return
    await pool.open(wait=True)
    _pool_opened = True


async def close_pool() -> None:
    global _pool, _pool_opened
    if _pool is not None:
        await _pool.close()
        _pool = None
        _pool_opened = False


async def delete_document(doctype: str, docname: str) -> int:
    await open_pool()
    async with get_pool().connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM rag_chunks WHERE doctype = %s AND docname = %s",
                (doctype, docname),
            )
            deleted = cur.rowcount or 0
        await conn.commit()
    return deleted


async def upsert_chunks(
    *,
    doctype: str,
    docname: str,
    chunks: list[str],
    metadata: dict[str, Any],
    embeddings: list[list[float]],
) -> int:
    if len(chunks) != len(embeddings):
        raise ValueError("chunks and embeddings length mismatch")

    await open_pool()
    async with get_pool().connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM rag_chunks WHERE doctype = %s AND docname = %s",
                (doctype, docname),
            )
            for index, (content, embedding) in enumerate(zip(chunks, embeddings, strict=True)):
                chunk_metadata = dict(metadata)
                chunk_metadata["chunk_index"] = index
                await cur.execute(
                    """
                    INSERT INTO rag_chunks
                        (doctype, docname, chunk_index, content, metadata, embedding)
                    VALUES
                        (%s, %s, %s, %s, %s::jsonb, %s::vector)
                    """,
                    (
                        doctype,
                        docname,
                        index,
                        content,
                        json.dumps(chunk_metadata, ensure_ascii=False, default=str),
                        _embedding_literal(embedding),
                    ),
                )
        await conn.commit()
    logger.info("rag_chunks_upserted", extra={"doctype": doctype, "docname": docname, "chunks": len(chunks)})
    return len(chunks)


def _build_filters(
    *,
    doctypes: list[str],
    company: str | None,
    user: str | None,
    roles: list[str],
) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    params: list[Any] = []

    if doctypes:
        clauses.append("doctype = ANY(%s)")
        params.append(doctypes)

    if company:
        clauses.append("(metadata->>'company' = %s OR NOT (metadata ? 'company'))")
        params.append(company)

    access_clauses: list[str] = []
    if user:
        access_clauses.append("metadata->>'owner' = %s")
        params.append(user)
        access_clauses.append("(metadata->'allowed_users') ? %s")
        params.append(user)
    if roles:
        access_clauses.append("(metadata->'permitted_roles') ?| %s::text[]")
        params.append(roles)
    if access_clauses:
        clauses.append("(" + " OR ".join(access_clauses) + ")")

    if not clauses:
        return "", params
    return "WHERE " + " AND ".join(clauses), params


async def search_similar(
    *,
    embedding: list[float],
    top_k: int,
    doctypes: list[str],
    company: str | None,
    user: str | None,
    roles: list[str],
) -> list[RagChunk]:
    await open_pool()
    where_sql, params = _build_filters(doctypes=doctypes, company=company, user=user, roles=roles)
    embedding_text = _embedding_literal(embedding)
    sql = f"""
        SELECT
            id,
            doctype,
            docname,
            chunk_index,
            content,
            metadata,
            1 - (embedding <=> %s::vector) AS score
        FROM rag_chunks
        {where_sql}
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """
    async with get_pool().connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(sql, [embedding_text, *params, embedding_text, top_k])
            rows = await cur.fetchall()

    return [
        RagChunk(
            id=row["id"],
            doctype=row["doctype"],
            docname=row["docname"],
            chunk_index=row["chunk_index"],
            content=row["content"],
            metadata=row["metadata"] or {},
            score=float(row["score"]) if row["score"] is not None else None,
        )
        for row in rows
    ]
