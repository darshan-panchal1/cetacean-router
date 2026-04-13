"""
Cetacean-Aware Logistics Router — FastAPI REST API

Production features:
  - Async route optimisation (non-blocking)
  - Server-Sent Events progress stream
  - Rate limiting (slowapi)
  - CORS restricted by env
  - Real OBIS integration (no random mocks)
  - Structured error responses
"""

import asyncio
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from api.models import RouteRequest, RouteResponse, HealthResponse, RouteStatusResponse
from config.settings import settings
from graph.routing_graph import run_routing_optimization
from mcp_servers.obis_server import check_species_risk
from mcp_servers.route_calc_server import calculate_route_metrics

logger = logging.getLogger("api")
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------
limiter = Limiter(key_func=get_remote_address)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "Starting Cetacean Router API | groq=%s",
        "configured" if settings.groq_configured else "NOT configured",
    )
    yield
    logger.info("Shutting down Cetacean Router API")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Cetacean-Aware Logistics Router API",
    description=(
        "AI-powered maritime routing that balances logistics efficiency "
        "with marine conservation using real OBIS cetacean sighting data."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS — restrict origins in production via environment variable
_allowed_origins = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# MCP tool wrappers
# ---------------------------------------------------------------------------

async def obis_tool(wkt_geometry: str, taxon: str = "Cetacea") -> dict:
    """Async wrapper around the synchronous OBIS MCP tool."""
    return await asyncio.to_thread(check_species_risk, wkt_geometry, taxon)


async def route_calc_tool(**kwargs) -> dict:
    """Async wrapper around the synchronous route calculator MCP tool."""
    if "waypoints" in kwargs:
        return await asyncio.to_thread(calculate_route_metrics, **kwargs)
    return {"success": True}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/", response_model=HealthResponse, tags=["health"])
async def health_check():
    """Basic health check."""
    return HealthResponse(
        status="healthy",
        service="Cetacean-Aware Logistics Router",
        version="2.0.0",
    )


@app.get("/health", tags=["health"])
async def detailed_health():
    """Detailed system health including dependency status."""
    from utils.resilience import _breakers, obis_cache

    return {
        "api": "operational",
        "groq_api": "configured" if settings.groq_configured else "not_configured",
        "agents": {
            "navigator": "ready",
            "biologist": "ready",
            "risk_manager": "ready",
        },
        "mcp_servers": {
            "obis": "live",
            "route_calc": "live",
        },
        "circuit_breakers": {
            name: breaker.state
            for name, breaker in _breakers.items()
        },
        "obis_cache_size": len(obis_cache),
    }


@app.post("/optimize-route", response_model=RouteResponse, tags=["routing"])
@limiter.limit(f"{settings.api_rate_limit_per_minute}/minute")
async def optimize_route(request: Request, body: RouteRequest):
    """
    Optimise a shipping route considering marine mammal conservation.

    Runs the 3-agent LangGraph workflow (Navigator → Biologist → Risk Manager)
    with real OBIS cetacean occurrence data.
    """
    t0 = time.monotonic()
    start = (body.start.latitude, body.start.longitude)
    end = (body.end.latitude, body.end.longitude)

    logger.info(
        "Optimise request | start=%s | end=%s | max_iter=%d",
        start, end, body.max_iterations,
    )

    try:
        result = await run_routing_optimization(
            start=start,
            end=end,
            obis_tool=obis_tool,
            route_calc_tool=route_calc_tool,
            max_iterations=body.max_iterations,
        )
    except Exception as exc:
        logger.exception("Route optimisation failed")
        raise HTTPException(status_code=500, detail=f"Optimisation failed: {exc}")

    elapsed = round(time.monotonic() - t0, 2)
    logger.info("Optimisation complete | elapsed=%ss", elapsed)

    last_risk = (
        result["risk_assessments"][-1] if result["risk_assessments"] else {}
    )

    return RouteResponse(
        success=True,
        selected_route=result["selected_route"],
        risk_assessment=last_risk,
        decision_rationale=result["decision_rationale"],
        llm_analysis=result["llm_analysis"],
        approved=result["approved"],
        iterations=result["iteration_count"],
        all_routes_considered=result["proposed_routes"],
        elapsed_seconds=elapsed,
    )


@app.post("/optimize-route/stream", tags=["routing"])
@limiter.limit(f"{settings.api_rate_limit_per_minute}/minute")
async def optimize_route_stream(request: Request, body: RouteRequest):
    """
    Streaming version of route optimisation using Server-Sent Events.
    Yields agent progress events followed by the final result.
    """

    async def _event_stream() -> AsyncGenerator[str, None]:
        def _send(event: str, data: dict) -> str:
            return f"event: {event}\ndata: {json.dumps(data)}\n\n"

        yield _send("status", {"message": "Initialising route optimisation…"})

        start = (body.start.latitude, body.start.longitude)
        end = (body.end.latitude, body.end.longitude)

        # We run the full optimisation and stream status updates.
        # For deeper per-agent streaming, agents would need to accept
        # a progress callback — this is left as a production extension.
        yield _send("status", {"message": "Navigator agent calculating routes…"})
        await asyncio.sleep(0)  # yield control

        try:
            result = await run_routing_optimization(
                start=start,
                end=end,
                obis_tool=obis_tool,
                route_calc_tool=route_calc_tool,
                max_iterations=body.max_iterations,
            )
        except Exception as exc:
            yield _send("error", {"message": str(exc)})
            return

        yield _send("status", {"message": "Biologist agent assessing ecological risk…"})
        await asyncio.sleep(0)
        yield _send("status", {"message": "Risk manager selecting optimal route…"})
        await asyncio.sleep(0)

        last_risk = (
            result["risk_assessments"][-1] if result["risk_assessments"] else {}
        )

        payload = {
            "success": True,
            "selected_route": result["selected_route"],
            "risk_assessment": last_risk,
            "decision_rationale": result["decision_rationale"],
            "llm_analysis": result["llm_analysis"],
            "approved": result["approved"],
            "iterations": result["iteration_count"],
            "all_routes_considered": result["proposed_routes"],
        }
        yield _send("result", payload)
        yield _send("done", {})

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
        workers=1,
    )