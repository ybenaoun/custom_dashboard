#!/usr/bin/env bash
# Genere un secret JWT partage et le pose des deux cotes :
# - site_config.json de Frappe (chatbot_jwt_secret)
# - .env du service FastAPI (JWT_SECRET)
# Aussi : configure chatbot_fastapi_url cote Frappe.
set -e

BENCH_ROOT="$HOME/frappe/my-bench"
SITE="erpnext.localhost"
FASTAPI_URL="http://127.0.0.1:9001"
SERVICE_DIR="$BENCH_ROOT/apps/custom_dashboard/chatbot_service"
PROCFILE="$BENCH_ROOT/Procfile"
PROCFILE_NAME="chatbot_service"
PROCFILE_CMD="bash apps/custom_dashboard/chatbot_service/scripts/bench_start.sh"

SECRET=$(openssl rand -hex 32)
echo "[*] Secret JWT genere : ${SECRET:0:16}... (${#SECRET} chars)"

cd "$BENCH_ROOT"

echo "[*] Frappe: set-config chatbot_jwt_secret"
bench --site "$SITE" set-config chatbot_jwt_secret "$SECRET" >/dev/null

echo "[*] Frappe: set-config chatbot_fastapi_url=$FASTAPI_URL"
bench --site "$SITE" set-config chatbot_fastapi_url "$FASTAPI_URL" >/dev/null

echo "[*] FastAPI: mise a jour .env"
sed -i "s|^JWT_SECRET=.*|JWT_SECRET=$SECRET|" "$SERVICE_DIR/.env"

echo "[*] Bench: verification Procfile pour bench start"
if grep -q "^$PROCFILE_NAME:" "$PROCFILE"; then
  sed -i "s|^$PROCFILE_NAME:.*|$PROCFILE_NAME: $PROCFILE_CMD|" "$PROCFILE"
else
  printf '\n%s: %s\n' "$PROCFILE_NAME" "$PROCFILE_CMD" >> "$PROCFILE"
fi

echo
echo "=== Verification site_config.json ==="
grep -E '"chatbot_(jwt_secret|fastapi_url)"' "$BENCH_ROOT/sites/$SITE/site_config.json" \
  | sed -E 's/("chatbot_jwt_secret"\s*:\s*").{16}([^"]+)/\1***\2/'

echo
echo "=== Verification .env FastAPI ==="
grep -E "^(JWT_SECRET|COHERE_API_KEY|JWT_ALGORITHM)" "$SERVICE_DIR/.env" \
  | sed -E 's/(=.{8}).*/\1***/'

echo
echo "=== Verification Procfile ==="
grep -E "^$PROCFILE_NAME:" "$PROCFILE"
