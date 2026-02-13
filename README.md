# astronomIA - Agentic Galaxy Analysis Backend

Backend profesional y escalable para un chatbot agéntico de análisis de galaxias.
`n8n` vive fuera de este repositorio y consumirá el endpoint HTTP `POST /analyze`.

## Stack y objetivos

- **API:** FastAPI
- **Arquitectura:** modular estilo DDD (`domain` / `application` / `infrastructure` / `interfaces`)
- **Core DS:** `packages/galaxy_core` (sin dependencias de LangChain)
- **Capa agente:** `packages/galaxy_agent` (tools + orquestador + scaffolding LangChain)
- **Observabilidad:** logging JSON estructurado + scaffolding LangSmith
- **Infra:** Docker CPU + opción GPU (NVIDIA)

## Estructura

```text
.
├── apps/
│   └── api/
├── packages/
│   ├── galaxy_core/
│   └── galaxy_agent/
├── tests/
├── artifacts/
├── notebooks/
├── scripts/
├── docs/
└── docker/
```

## Requisitos

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (gestor de entorno/dependencias)

## Levantar en local

1. Crear `.env` desde el ejemplo:

   ```bash
   cp .env.example .env
   ```

2. Instalar dependencias:

   ```bash
   make install
   ```

3. Ejecutar API:

   ```bash
   make run
   ```

   También funciona directamente:

   ```bash
   uv run uvicorn apps.api.main:app --reload
   ```

## Levantar con Docker

1. Crea `.env` en la raíz (copia de `.env.example`) y **rellena `OPENAI_API_KEY`**.
2. Desde la raíz: `docker compose up --build`.
3. API en `http://localhost:8000`. Health: `curl http://localhost:8000/health`.  
   Si sale "container name already in use": `docker rm -f astronomia-api` y vuelve a levantar.  
   **GPU (NVIDIA):** `docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build`.

   **E2E real (prompt → imagen en disco):** con la API levantada, `python scripts/e2e_real.py`. Comprueba que la imagen queda en `artifacts/test-1/image.jpg`.

## Tests, lint y type-check

```bash
make test
make lint
make format
make typecheck
```

## Endpoints MVP

- `GET /health` -> `{"status":"ok"}`
- `POST /analyze`

### Request `/analyze`

```json
{
  "request_id": "req-001",
  "target": { "name": "NGC 1300" },
  "task": "morphology_summary",
  "image_url": null,
  "options": {}
}
```

### Response `/analyze` (shape)

```json
{
  "request_id": "req-001",
  "status": "success",
  "summary": "Detected galaxy-like structure with area ~...",
  "results": {},
  "artifacts": [{ "type": "mask", "path": "artifacts/req-001/mask.png" }],
  "provenance": {
    "timestamp": "2026-01-01T00:00:00+00:00",
    "versions": {
      "galaxy_core": "0.1.0",
      "galaxy_agent": "0.1.0"
    }
  },
  "warnings": []
}
```

## Ejemplos curl

Health:

```bash
curl -s http://localhost:8000/health
```

Analyze (con API key):

```bash
curl -s -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -H "X-API-Key: change-me" \
  -d '{
    "request_id":"req-001",
    "target":{"name":"NGC 1300"},
    "task":"morphology_summary",
    "options":{}
  }'
```

Para desarrollo sin API key, usar en `.env`:

```env
REQUIRE_API_KEY=false
```

### Ejecutar comandos dentro del contenedor

Desde la raíz del repo (con el mismo compose):

```bash
docker compose run --rm api python scripts/run_pipeline.py M81
```

Si hay problemas de SSL (proxy): en `.env` añade `REQUESTS_VERIFY_SSL=false`.

## Variables de entorno

Ver `.env.example`:

- `OPENAI_API_KEY` — necesario para el agente
- `OPENAI_MODEL` — modelo OpenAI (default `gpt-4.1-mini`)
- `API_KEY`, `REQUIRE_API_KEY`, `ARTIFACT_DIR`, `LOG_LEVEL`
- `LANGSMITH_API_KEY`, `LANGSMITH_TRACING` (opcional)
- `REQUESTS_VERIFY_SSL` (opcional; `false` si hay problemas de certificado)
- `SKYVIEW_TIMEOUT` (opcional, default 240)

