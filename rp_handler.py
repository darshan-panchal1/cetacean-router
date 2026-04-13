# rp_handler.py
"""
RunPod Serverless handler for the Cetacean-Aware Logistics Router.

Expected input schema:
{
  "input": {
    "start": {"latitude": 34.42, "longitude": -119.70},
    "end":   {"latitude": 45.52, "longitude": -122.68},
    "max_iterations": 3           // optional, default 3
  }
}

Output:
{
  "selected_route": {...},
  "risk_assessment": {...},
  "decision_rationale": "...",
  "llm_analysis": "...",
  "approved": true,
  "metadata": {
    "iterations": 2,
    "routes_evaluated": 3,
    "obis_cache_size": 4
  }
}
"""

import asyncio
import logging
import os
from typing import Any, Dict

import runpod
from dotenv import load_dotenv

load_dotenv()

# Import after load_dotenv so settings picks up the env file
from graph.routing_graph import run_routing_optimization
from mcp_servers.obis_server import check_species_risk
from mcp_servers.route_calc_server import calculate_route_metrics
from utils.resilience import obis_cache

logger = logging.getLogger("rp_handler")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)


# ---------------------------------------------------------------------------
# MCP tool wrappers (sync OBIS / route_calc → async-safe via to_thread)
# ---------------------------------------------------------------------------

async def _obis_tool(wkt_geometry: str, taxon: str = "Cetacea") -> dict:
    return await asyncio.to_thread(check_species_risk, wkt_geometry, taxon)


async def _route_calc_tool(**kwargs) -> dict:
    if "waypoints" in kwargs:
        return await asyncio.to_thread(calculate_route_metrics, **kwargs)
    return {"success": True}


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

class InputValidationError(ValueError):
    pass


def _validate_coord(obj: Any, name: str) -> tuple:
    if not isinstance(obj, dict):
        raise InputValidationError(f"'{name}' must be an object with latitude/longitude.")
    lat = obj.get("latitude")
    lon = obj.get("longitude")
    if lat is None or lon is None:
        raise InputValidationError(f"'{name}' must have 'latitude' and 'longitude'.")
    if not (-90 <= float(lat) <= 90):
        raise InputValidationError(f"'{name}.latitude' must be between -90 and 90.")
    if not (-180 <= float(lon) <= 180):
        raise InputValidationError(f"'{name}.longitude' must be between -180 and 180.")
    return (float(lat), float(lon))


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------

async def handler(job: Dict) -> Dict:
    """
    RunPod async job handler.
    """
    job_input = job.get("input", {})

    # --- Validate ---
    try:
        start = _validate_coord(job_input.get("start"), "start")
        end = _validate_coord(job_input.get("end"), "end")
    except InputValidationError as exc:
        logger.warning("Validation error: %s", exc)
        return {"error": str(exc)}

    max_iterations = int(job_input.get("max_iterations", 3))
    max_iterations = max(1, min(max_iterations, 5))  # clamp to [1, 5]

    logger.info(
        "Job received | start=%s | end=%s | max_iter=%d",
        start, end, max_iterations,
    )

    # --- Run optimisation ---
    try:
        result = await run_routing_optimization(
            start=start,
            end=end,
            obis_tool=_obis_tool,
            route_calc_tool=_route_calc_tool,
            max_iterations=max_iterations,
        )
    except Exception as exc:
        logger.exception("Optimisation failed")
        return {"error": f"Optimisation failed: {exc}"}

    last_risk = (
        result["risk_assessments"][-1] if result["risk_assessments"] else {}
    )

    return {
        "selected_route": result["selected_route"],
        "risk_assessment": last_risk,
        "decision_rationale": result["decision_rationale"],
        "llm_analysis": result["llm_analysis"],
        "approved": result["approved"],
        "metadata": {
            "iterations": result["iteration_count"],
            "routes_evaluated": len(result["proposed_routes"]),
            "obis_cache_size": len(obis_cache),
            "start": list(start),
            "end": list(end),
        },
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})