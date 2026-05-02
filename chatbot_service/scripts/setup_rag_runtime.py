from __future__ import annotations

import json
import os
import pwd
import secrets
import subprocess
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
BENCH_ROOT = APP_ROOT.parents[2]
SITE_CONFIG = BENCH_ROOT / "sites" / "erpnext.localhost" / "site_config.json"
ENV_FILE = APP_ROOT / ".env"
RAG_SQL = APP_ROOT / "sql" / "001_rag_pgvector.sql"

DB_USER = "custom_dashboard_rag"
DB_NAME = "custom_dashboard_rag"
APP_USER = "youss"


def run(command: list[str], **kwargs) -> subprocess.CompletedProcess:
	return subprocess.run(command, check=True, **kwargs)


def psql(sql: str, db: str = "postgres") -> None:
	run(["runuser", "-u", "postgres", "--", "psql", "-d", db, "-v", "ON_ERROR_STOP=1", "-c", sql])


def postgres_scalar(sql: str) -> str:
	result = run(
		["runuser", "-u", "postgres", "--", "psql", "-tAc", sql],
		capture_output=True,
		text=True,
	)
	return result.stdout.strip()


def set_file_owner(path: Path) -> None:
	try:
		user = pwd.getpwnam(APP_USER)
	except KeyError:
		return
	os.chown(path, user.pw_uid, user.pw_gid)


def update_env(updates: dict[str, str]) -> None:
	lines = ENV_FILE.read_text().splitlines() if ENV_FILE.exists() else []
	seen: set[str] = set()
	out: list[str] = []
	for line in lines:
		key = line.split("=", 1)[0] if "=" in line else None
		if key in updates:
			out.append(f"{key}={updates[key]}")
			seen.add(key)
		else:
			out.append(line)

	if out and out[-1].strip():
		out.append("")
	for key, value in updates.items():
		if key not in seen:
			out.append(f"{key}={value}")

	ENV_FILE.write_text("\n".join(out) + "\n")
	set_file_owner(ENV_FILE)


def update_site_config(rag_key: str) -> None:
	cfg = json.loads(SITE_CONFIG.read_text())
	cfg["rag_fastapi_url"] = "http://127.0.0.1:9001"
	cfg["rag_internal_api_key"] = rag_key
	cfg["rag_index_enabled"] = 1
	SITE_CONFIG.write_text(json.dumps(cfg, indent=2, sort_keys=True) + "\n")
	set_file_owner(SITE_CONFIG)


def main() -> None:
	db_password = secrets.token_hex(24)
	rag_key = secrets.token_hex(32)
	safe_password = db_password.replace("'", "''")

	psql(
		"DO $$ "
		"BEGIN "
		f"IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '{DB_USER}') THEN "
		f"CREATE ROLE {DB_USER} LOGIN PASSWORD '{safe_password}'; "
		"ELSE "
		f"ALTER ROLE {DB_USER} LOGIN PASSWORD '{safe_password}'; "
		"END IF; "
		"END $$;"
	)

	if not postgres_scalar(f"SELECT 1 FROM pg_database WHERE datname='{DB_NAME}'"):
		psql(f"CREATE DATABASE {DB_NAME} OWNER {DB_USER}")

	psql(RAG_SQL.read_text(), db=DB_NAME)
	psql(
		f"ALTER TABLE rag_chunks OWNER TO {DB_USER}; "
		f"ALTER SEQUENCE rag_chunks_id_seq OWNER TO {DB_USER}; "
		f"ALTER FUNCTION set_rag_chunks_updated_at() OWNER TO {DB_USER};",
		db=DB_NAME,
	)

	database_url = f"postgresql://{DB_USER}:{db_password}@127.0.0.1:5432/{DB_NAME}"
	update_env(
		{
			"DATABASE_URL": database_url,
			"RAG_INTERNAL_API_KEY": rag_key,
			"RAG_EMBED_MODEL": "embed-multilingual-v3.0",
			"RAG_RERANK_MODEL": "rerank-v3.5",
			"RAG_CHUNK_SIZE": "1200",
			"RAG_CHUNK_OVERLAP": "150",
			"RAG_TOP_K": "24",
			"RAG_RERANK_TOP_N": "8",
			"RAG_MIN_RELEVANCE": "0.15",
			"RAG_DB_POOL_SIZE": "5",
		}
	)
	update_site_config(rag_key)
	print("RAG runtime configured")


if __name__ == "__main__":
	main()
