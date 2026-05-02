-- RAG vector store for Custom Dashboard Chatbot.
-- Cohere embed-multilingual-v3.0 returns 1024-dimensional float embeddings.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS rag_chunks (
    id BIGSERIAL PRIMARY KEY,
    doctype TEXT NOT NULL,
    docname TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    embedding VECTOR(1024) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (doctype, docname, chunk_index)
);

CREATE INDEX IF NOT EXISTS rag_chunks_doctype_idx
    ON rag_chunks (doctype);

CREATE INDEX IF NOT EXISTS rag_chunks_docname_idx
    ON rag_chunks (docname);

CREATE INDEX IF NOT EXISTS rag_chunks_doctype_docname_idx
    ON rag_chunks (doctype, docname);

CREATE INDEX IF NOT EXISTS rag_chunks_metadata_gin_idx
    ON rag_chunks USING GIN (metadata);

CREATE INDEX IF NOT EXISTS rag_chunks_embedding_hnsw_idx
    ON rag_chunks USING hnsw (embedding vector_cosine_ops);

CREATE OR REPLACE FUNCTION set_rag_chunks_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS rag_chunks_set_updated_at ON rag_chunks;

CREATE TRIGGER rag_chunks_set_updated_at
BEFORE UPDATE ON rag_chunks
FOR EACH ROW
EXECUTE FUNCTION set_rag_chunks_updated_at();
