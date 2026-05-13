#!/usr/bin/env bash
# Launch the FastAPI/Cohere service from the bench Procfile.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
SERVICE_DIR="$(cd -- "$SCRIPT_DIR/.." >/dev/null 2>&1 && pwd)"
UVICORN_BIN="$SERVICE_DIR/.venv/bin/uvicorn"

read_env_value() {
	local key="$1"
	local default="$2"
	local line value

	if [[ -f "$SERVICE_DIR/.env" ]]; then
		while IFS= read -r line || [[ -n "$line" ]]; do
			case "$line" in
				"$key"=*)
					value="${line#*=}"
					value="${value%\"}"
					value="${value#\"}"
					value="${value%\'}"
					value="${value#\'}"
					printf '%s' "$value"
					return
					;;
			esac
		done < "$SERVICE_DIR/.env"
	fi

	printf '%s' "$default"
}

if [[ ! -f "$SERVICE_DIR/.env" ]]; then
	echo "Missing $SERVICE_DIR/.env. Copy .env.example and configure COHERE_API_KEY/JWT_SECRET." >&2
	exit 1
fi

if [[ ! -x "$UVICORN_BIN" ]]; then
	echo "Missing uvicorn at $UVICORN_BIN." >&2
	echo "Run: cd apps/custom_dashboard/chatbot_service && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
	exit 1
fi

HOST="${CHATBOT_SERVICE_HOST:-$(read_env_value CHATBOT_SERVICE_HOST 127.0.0.1)}"
PORT="${CHATBOT_SERVICE_PORT:-$(read_env_value CHATBOT_SERVICE_PORT 9001)}"
APP_MODULE="${CHATBOT_SERVICE_APP:-app.main:app}"
RELOAD="${CHATBOT_SERVICE_RELOAD:-$(read_env_value CHATBOT_SERVICE_RELOAD true)}"

cd "$SERVICE_DIR"

args=("$UVICORN_BIN" "$APP_MODULE" "--host" "$HOST" "--port" "$PORT")
case "${RELOAD,,}" in
	0|false|no|off)
		;;
	*)
		args+=("--reload")
		;;
esac

exec "${args[@]}"
