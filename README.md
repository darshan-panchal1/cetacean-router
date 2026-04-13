# Cetacean-Aware Logistics Router

<p align="center">

  <!-- Core Stack -->
  <img src="https://img.shields.io/badge/Python-3.10+-blue?logo=python" />
  <img src="https://img.shields.io/badge/FastAPI-Backend-green?logo=fastapi" />
  <img src="https://img.shields.io/badge/React-18-blue?logo=react" />
  <img src="https://img.shields.io/badge/Vite-Bundler-purple?logo=vite" />

  <!-- AI / LLM -->
  <img src="https://img.shields.io/badge/LangGraph-Agent%20Orchestration-black" />
  <img src="https://img.shields.io/badge/Groq-LLM%20Inference-orange" />

  <!-- Data / Geo -->
  <img src="https://img.shields.io/badge/OBIS-Marine%20Data-blue" />
  <img src="https://img.shields.io/badge/Shapely-Geometry-yellow" />
  <img src="https://img.shields.io/badge/Haversine-Distance-lightgrey" />

  <!-- Infra -->
  <img src="https://img.shields.io/badge/Docker-Container-blue?logo=docker" />
  <img src="https://img.shields.io/badge/RunPod-Serverless-red" />

</p>

**AI-powered maritime route optimisation that balances shipping efficiency with cetacean conservation.**

A 3-agent LangGraph system — Navigator, Marine Biologist, Risk Manager — queries live OBIS cetacean sighting data and uses Groq LLMs to select the safest, most efficient shipping route. Deployable as a local FastAPI service or on RunPod Serverless.

---

## Contents

- [Architecture](#architecture)
- [Quickstart](#quickstart)
- [Environment variables](#environment-variables)
- [Running locally](#running-locally)
- [Docker](#docker)
- [RunPod Serverless](#runpod-serverless)
- [React UI](#react-ui)
- [API reference](#api-reference)
- [How it works](#how-it-works)
- [Production notes](#production-notes)
- [Limitations](#limitations)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      LangGraph Workflow                         │
│                                                                 │
│  ┌─────────────┐       ┌─────────────┐       ┌──────────────┐   │
│  │  Navigator  │──────▶│  Biologist  │──────▶│ Risk Manager │   │
│  │   Agent     │       │    Agent    │       │    Agent     │   │
│  └─────────────┘       └─────────────┘       └──────────────┘   │
│        │  ◀──────────────────────────────────────── │           │
│        │          (iterate if HIGH risk)            │           │
└────────┼────────────────────────────────────────────┼───────────┘
         │                                            │
    Route calc                                    OBIS API
    (Haversine)                              (pyobis · pandas)
```

### Agents

| Agent | Responsibility |
|---|---|
| **Navigator** | Computes direct, detour, and reduced-speed route options using Haversine great-circle geometry |
| **Biologist** | Queries the OBIS database for cetacean sightings along each route, classifies risk (LOW / MEDIUM / HIGH), identifies critical sectors |
| **Risk Manager** | Scores all routes on a 0–100 composite (ETA 40 pts, distance 30 pts, ecology 30 pts), calls the Groq LLM for strategic analysis, applies hard approval rules |

### Data sources

| Source | What it provides |
|---|---|
| **OBIS** (Ocean Biodiversity Information System) | Real cetacean occurrence records via `pyobis` |
| **Groq** | Fast LLM inference (llama-3.3-70b-versatile) for agent reasoning |
| **Haversine geometry** | Great-circle distance, ETA, fuel estimation |

---

## Quickstart

```bash
git clone <repo-url>
cd cetacean-router

# 1. Install dependencies
make install           # or: pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Add GROQ_API_KEY — all other defaults work locally

# 3. Start the API
make api               # FastAPI on http://localhost:8000

# 4. (Optional) Interactive CLI
make cli
```

---

## Environment variables

### Backend (`.env`)

| Variable | Default | Description |
|---|---|---|
| `GROQ_API_KEY` | — | **Required for LLM reasoning.** Get from [console.groq.com](https://console.groq.com). Without it, routing still works but LLM analysis is skipped. |
| `API_HOST` | `0.0.0.0` | FastAPI bind address |
| `API_PORT` | `8000` | FastAPI port |
| `LOG_LEVEL` | `INFO` | Python logging level |
| `CORS_ORIGINS` | `*` | Comma-separated allowed origins. Set to your frontend domain in production. |
| `NAVIGATOR_MODEL` | `llama-3.3-70b-versatile` | Groq model for the Navigator agent |
| `BIOLOGIST_MODEL` | `llama-3.3-70b-versatile` | Groq model for the Biologist agent |
| `RISK_MANAGER_MODEL` | `llama-3.3-70b-versatile` | Groq model for the Risk Manager agent |
| `DEFAULT_SHIP_SPEED_KNOTS` | `18` | Cruising speed used for direct and detour routes |
| `REDUCED_SPEED_KNOTS` | `10` | Speed used for reduced-speed whale-safe routes |
| `RISK_THRESHOLD_HIGH` | `50` | OBIS sightings count above which risk is classified HIGH |
| `RISK_THRESHOLD_MEDIUM` | `10` | OBIS sightings count above which risk is classified MEDIUM |
| `OBIS_CACHE_TTL_SECONDS` | `3600` | TTL for in-memory OBIS response cache |
| `CIRCUIT_BREAKER_FAILURE_THRESHOLD` | `5` | Consecutive failures before circuit opens |
| `CIRCUIT_BREAKER_RECOVERY_TIMEOUT` | `60` | Seconds before an open circuit probes again |
| `API_RATE_LIMIT_PER_MINUTE` | `30` | Requests per IP per minute (slowapi) |

### Frontend (`ui/.env.local`)

| Variable | Description |
|---|---|
| `VITE_RUNPOD_ENDPOINT_ID` | RunPod serverless endpoint ID. If blank, the UI falls back to `VITE_LOCAL_API_URL`. |
| `VITE_RUNPOD_API_KEY` | RunPod API key |
| `VITE_LOCAL_API_URL` | Local FastAPI base URL (default: `http://localhost:8000`) |

---

## Running locally

### API only

```bash
# Install + configure
pip install -r requirements.txt
cp .env.example .env   # add GROQ_API_KEY

# Start FastAPI
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# Health check
curl http://localhost:8000/health

# Test a route
curl -X POST http://localhost:8000/optimize-route \
  -H "Content-Type: application/json" \
  -d '{
    "start": {"latitude": 34.4208, "longitude": -119.6982},
    "end":   {"latitude": 45.5152, "longitude": -122.6784},
    "max_iterations": 3
  }'
```

### Interactive CLI

```bash
python main.py
# Choose from preset routes or enter custom coordinates
```

### MCP servers (optional, standalone)

```bash
# Terminal 1 — OBIS data server
python -m mcp_servers.obis_server

# Terminal 2 — Route calculator
python -m mcp_servers.route_calc_server
```

---

## Docker

### Single container

```bash
# Build
docker build -t cetacean-router:latest .

# Run API
docker run -p 8000:8000 --env-file .env cetacean-router:latest

# Run RunPod handler
docker run --env-file .env cetacean-router:latest python rp_handler.py
```

### Full stack (docker compose)

```bash
docker compose up --build        # starts API + both MCP servers
docker compose logs -f api       # tail logs
docker compose down              # stop everything
```

Services:

| Service | Port | Description |
|---|---|---|
| `api` | 8000 | FastAPI REST API |
| `obis-mcp` | 8001 | OBIS Marine Biology MCP server |
| `route-calc-mcp` | 8002 | Route Calculator MCP server |

---

## RunPod Serverless

### Deploy

1. Push the image to a registry:
   ```bash
   docker build -t your-registry/cetacean-router:latest .
   docker push your-registry/cetacean-router:latest
   ```

2. Create a RunPod Serverless endpoint using the image. Set the handler command:
   ```
   python rp_handler.py
   ```

3. Set environment variables in the RunPod endpoint settings (same as `.env`).

### Input schema

```json
{
  "input": {
    "start":          { "latitude": 34.42, "longitude": -119.70 },
    "end":            { "latitude": 45.52, "longitude": -122.68 },
    "max_iterations": 3
  }
}
```

### Output schema

```json
{
  "selected_route":      { "route_name": "Route Beta (Detour)", "distance_nm": 720.1, "eta_hours": 40.0, "speed_knots": 18, "waypoints": [...] },
  "risk_assessment":     { "risk_level": "MEDIUM", "sighting_count": 23, "species_list": ["Balaenoptera musculus"], "risk_score": 5 },
  "decision_rationale":  "Selected Route Beta (Detour) (score 76.2/100)…",
  "llm_analysis":        "Recommend Route Beta…",
  "approved":            true,
  "metadata": {
    "iterations":        2,
    "routes_evaluated":  3,
    "obis_cache_size":   4,
    "start":             [34.42, -119.70],
    "end":               [45.52, -122.68]
  }
}
```

---

## React UI

The UI is a standalone Vite + React application. It connects to either the RunPod endpoint or a local FastAPI server.

### Setup

```bash
cd ui
cp .env.example .env.local

# For RunPod deployment
echo "VITE_RUNPOD_ENDPOINT_ID=your-endpoint-id"  >> .env.local
echo "VITE_RUNPOD_API_KEY=your-api-key"           >> .env.local

# For local development (default)
echo "VITE_LOCAL_API_URL=http://localhost:8000"   >> .env.local

npm install
npm run dev      # http://localhost:5173
npm run build    # production build → dist/
```

### Features

- 3-agent pipeline visualisation with live state (idle / active / done / error)
- Preset routes for common maritime corridors
- SVG route map showing all evaluated routes
- Metrics: distance, ETA, speed, sightings
- Full routes comparison table
- Detected species list
- Agent log with timestamps
- Graceful degradation when RunPod is not configured (falls back to local API)

---

## API reference

### `GET /health`

Returns system status including circuit breaker states and OBIS cache size.

```json
{
  "api":              "operational",
  "groq_api":         "configured",
  "circuit_breakers": { "groq_navigator": "closed", "obis_api": "closed" },
  "obis_cache_size":  12
}
```

### `POST /optimize-route`

Synchronous route optimisation. Rate-limited to 30 req/min per IP.

**Request body:**

```json
{
  "start":          { "latitude": 34.42, "longitude": -119.70 },
  "end":            { "latitude": 45.52, "longitude": -122.68 },
  "max_iterations": 3
}
```

**Response:**

```json
{
  "success":               true,
  "selected_route":        { ... },
  "risk_assessment":       { ... },
  "decision_rationale":    "...",
  "llm_analysis":          "...",
  "approved":              true,
  "iterations":            2,
  "all_routes_considered": [ ... ],
  "elapsed_seconds":       14.2
}
```

### `POST /optimize-route/stream`

Server-Sent Events stream. Yields `status`, `result`, and `done` events. Useful for real-time progress in UIs.

```
event: status
data: {"message": "Navigator agent calculating routes…"}

event: result
data: { ...full result object... }

event: done
data: {}
```

---

## How it works

### Optimisation loop

```
Iteration 1:
  Navigator  → direct route only
  Biologist  → OBIS query → HIGH risk detected
  Risk Mgr   → score = 15/100, approved = false

Iteration 2:
  Navigator  → direct + detour + reduced-speed routes
  Biologist  → OBIS query on each → detour = MEDIUM, reduced = LOW
  Risk Mgr   → score detour = 76/100, approved = true → STOP
```

### Composite scoring (0–100)

```
eta_score      = max(0,  40 - (eta_hours  / 48)   × 40)
distance_score = max(0,  30 - (distance   / 1000)  × 30)
ecology_score  =         30 - (risk_score / 10)    × 30

composite = eta_score + distance_score + ecology_score
```

### Hard approval rules (override scoring)

- Direct route through a HIGH-risk sector → **rejected**
- Any route with > 100 sightings → **rejected**
- Direct route with UNKNOWN risk (OBIS failure) → **rejected** (fail-safe)

### Resilience

| Mechanism | Applies to | Behaviour |
|---|---|---|
| TTL cache | OBIS queries | 1-hour in-memory cache keyed by WKT geometry hash |
| Circuit breaker | Groq LLM + OBIS API | Opens after 5 failures, probes after 60 s |
| Async retry | All LLM calls | 3 attempts, exponential back-off (1 s, 2 s, 4 s) |
| Rate limiting | FastAPI `/optimize-route` | 30 req/min per IP (slowapi) |

---

## Production notes

1. **CORS**: Set `CORS_ORIGINS` to your frontend origin, not `*`.
2. **OBIS rate limiting**: The free OBIS API has no hard rate limit but is a shared scientific resource. The built-in TTL cache significantly reduces query volume. For high-throughput deployments, increase `OBIS_CACHE_TTL_SECONDS`.
3. **Workers**: The Dockerfile sets `--workers 1` intentionally. LangGraph's async graph is not designed for multi-worker shared state. To scale horizontally, run multiple containers behind a load balancer.
4. **Authentication**: The API has no authentication layer. Add OAuth2 / API keys for public deployments.
5. **Groq costs**: Each optimisation run makes 2–4 LLM calls. Monitor usage at [console.groq.com](https://console.groq.com).
6. **AIS integration**: For real commercial use, integrate AIS (Automatic Identification System) data for live ship traffic awareness. This system uses only static whale sighting records.

---

## Limitations

| Limitation | Notes |
|---|---|
| OBIS data is historical | Sighting records may not reflect current whale positions or seasonal migrations |
| No weather routing | Sea state, currents, and storm avoidance are not modelled |
| No AIS integration | Real-time ship traffic density is not considered |
| Simplified fuel model | Uses a cubic speed-power relationship; does not account for vessel class |
| OBIS query speed | Each query takes 5–15 s depending on geometry size. The TTL cache mitigates this on repeated routes. |
| Single waypoint detour | Detour routes use one intermediate waypoint. Multi-waypoint avoidance corridors would improve real-world accuracy. |

---

## Stack

| Layer | Technology |
|---|---|
| Agent orchestration | LangGraph |
| LLM inference | Groq (llama-3.3-70b-versatile) |
| Marine biology data | OBIS via pyobis |
| API framework | FastAPI + uvicorn |
| Containerisation | Docker (multi-stage) |
| Serverless | RunPod |
| Frontend | React 18 + Vite |
| Geospatial | Shapely, Haversine |

---

## License

For research and conservation use. Consult official maritime navigation authorities before voyage planning.

---

*🐋 Protecting marine life, one route at a time.*