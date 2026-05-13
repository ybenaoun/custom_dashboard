# Chatbot Service — FastAPI + Cohere

Squelette du service chatbot pour Custom Dashboard.

## Setup

```bash
cd apps/custom_dashboard/chatbot_service
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edite .env : COHERE_API_KEY (https://dashboard.cohere.com/api-keys)
#              JWT_SECRET (genere avec `openssl rand -hex 32`)
```

## Lancer le service

```bash
./scripts/bench_start.sh
```

Le service ecoute sur `http://127.0.0.1:9001` par defaut. Doc OpenAPI : `http://127.0.0.1:9001/docs`.

Avec le bench, le service est lance automatiquement par `bench start` via le `Procfile` racine :

```Procfile
chatbot_service: bash apps/custom_dashboard/chatbot_service/scripts/bench_start.sh
```

Variables optionnelles pour le lanceur : `CHATBOT_SERVICE_HOST`, `CHATBOT_SERVICE_PORT`, `CHATBOT_SERVICE_RELOAD`.

## Tester

```bash
# 1. Health (pas d'auth)
curl http://127.0.0.1:9001/health

# 2. Chat (JWT requis)
TOKEN=$(python scripts/generate_test_token.py)
curl -X POST http://127.0.0.1:9001/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message":"Bonjour, tu peux te presenter ?","language":"fr"}'
```

## Structure

```
chatbot_service/
  app/
    main.py                # FastAPI app + CORS
    config.py              # Settings via .env
    deps.py                # Dependency injection
    core/auth.py           # JWT verification (HS256)
    llm/cohere_client.py   # Wrapper Cohere AsyncClientV2
    llm/prompts.py         # System prompts FR/EN
    schemas/chat.py        # Pydantic models
    api/health.py          # GET /health
    api/chat.py            # POST /chat
  scripts/
    bench_start.sh         # Lance FastAPI/Cohere depuis bench start
    generate_test_token.py # JWT de test pour curl
  requirements.txt
  .env.example
```

## Etapes suivantes (non incluses dans ce squelette)

- [ ] Bridge Frappe : endpoint `chatbot_proxy` qui signe un JWT et forward vers FastAPI
- [ ] Persistence : stockage des conversations dans Frappe DocTypes (deja existant) via REST
- [ ] Tool calling : exposer les fonctions ERPNext (ventes/stock/achats) comme tools Cohere
- [ ] RAG : embeddings Cohere + pgvector pour la doc ERPNext
- [ ] Streaming : `chat_stream()` + `StreamingResponse`
- [ ] Rate limiting : SlowAPI par utilisateur
- [ ] Logging structure : structlog
- [ ] Tests : pytest + httpx + cohere mocks
