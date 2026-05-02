#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."
source .venv/bin/activate

TOKEN=$(python scripts/generate_test_token.py Administrator)
echo "Token length: ${#TOKEN}"
echo "Token (start): ${TOKEN:0:40}..."
echo

echo "=== /health ==="
curl -sS http://127.0.0.1:9001/health
echo; echo

echo "=== POST /chat (FR) ==="
curl -sS -X POST http://127.0.0.1:9001/chat \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"message":"Bonjour ! Presente-toi en 2 phrases.","language":"fr"}'
echo; echo

echo "=== POST /chat (EN, with history) ==="
curl -sS -X POST http://127.0.0.1:9001/chat \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"message":"What did I just say?","language":"en","history":[{"role":"user","content":"My favorite number is 42"},{"role":"assistant","content":"Got it, 42 is noted."}]}'
echo
