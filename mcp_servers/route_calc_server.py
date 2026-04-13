"""
Route Calculator MCP Server
Provides haversine-based maritime route metrics and detour waypoints.
"""

import logging
import math
import time
from typing import Dict, List

from fastmcp import FastMCP

# ------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("mcp.route_calc")

mcp = FastMCP("RouteCalculator")

_EARTH_RADIUS_NM = 3440.065


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in nautical miles."""
    rlat1, rlat2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    return _EARTH_RADIUS_NM * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def calculate_route_metrics(
    waypoints: List[List[float]],
    speed_knots: float = 18.0,
    fuel_consumption_rate: float = 1.0,
) -> dict:
    """
    Calculate comprehensive metrics for a proposed route.

    Args:
        waypoints: List of [lat, lon] pairs (at least 2).
        speed_knots: Ship speed in knots.
        fuel_consumption_rate: Base fuel consumption multiplier.

    Returns:
        total_distance_nm, eta_hours, estimated_fuel_tons, segment breakdown.
    """
    if len(waypoints) < 2:
        return {"success": False, "error": "At least 2 waypoints required."}

    t0 = time.monotonic()
    total_distance = 0.0
    segments = []

    for i in range(len(waypoints) - 1):
        lat1, lon1 = waypoints[i]
        lat2, lon2 = waypoints[i + 1]
        seg_dist = _haversine(lat1, lon1, lat2, lon2)
        total_distance += seg_dist
        segments.append({
            "from": waypoints[i],
            "to": waypoints[i + 1],
            "distance_nm": round(seg_dist, 2),
        })

    eta_hours = total_distance / speed_knots

    # Admiralty-style fuel estimate: cubic relationship with speed
    base_fuel = (total_distance / 100.0) * fuel_consumption_rate
    speed_factor = (speed_knots / 18.0) ** 3
    estimated_fuel = base_fuel * speed_factor

    elapsed = round(time.monotonic() - t0, 4)
    logger.info(
        "Route metrics | dist=%.1f nm | eta=%.1f h | fuel=%.1f t | elapsed=%ss",
        total_distance, eta_hours, estimated_fuel, elapsed,
    )

    return {
        "success": True,
        "total_distance_nm": round(total_distance, 2),
        "eta_hours": round(eta_hours, 2),
        "eta_days": round(eta_hours / 24, 2),
        "speed_knots": speed_knots,
        "estimated_fuel_tons": round(estimated_fuel, 2),
        "segments": segments,
        "waypoint_count": len(waypoints),
    }


@mcp.tool()
def generate_detour_waypoints(
    start: List[float],
    end: List[float],
    avoid_sector: Dict[str, float],
    detour_margin_degrees: float = 1.5,
) -> dict:
    """
    Generate waypoints that route around a risky sector.

    The detour midpoint is placed outside the sector bounding box with
    an additional safety margin.
    """
    try:
        start_lat, start_lon = start
        end_lat, end_lon = end
        sc_lat = (avoid_sector["lat_min"] + avoid_sector["lat_max"]) / 2
        sc_lon = (avoid_sector["lon_min"] + avoid_sector["lon_max"]) / 2

        if abs(end_lon - start_lon) > abs(end_lat - start_lat):
            # East-west route → detour north/south
            mid_lat = (
                avoid_sector["lat_min"] - detour_margin_degrees
                if start_lat < sc_lat
                else avoid_sector["lat_max"] + detour_margin_degrees
            )
            mid_lon = (start_lon + end_lon) / 2
        else:
            # North-south route → detour east/west
            mid_lon = (
                avoid_sector["lon_min"] - detour_margin_degrees
                if start_lon < sc_lon
                else avoid_sector["lon_max"] + detour_margin_degrees
            )
            mid_lat = (start_lat + end_lat) / 2

        waypoints = [start, [mid_lat, mid_lon], end]
        metrics = calculate_route_metrics(waypoints)

        logger.info("Detour generated | mid=(%.2f,%.2f)", mid_lat, mid_lon)

        return {
            "success": True,
            "detour_waypoints": waypoints,
            "metrics": metrics,
            "avoided_sector": avoid_sector,
        }

    except Exception as exc:
        logger.exception("Detour generation failed")
        return {"success": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logger.info("Starting RouteCalculator MCP server")
    mcp.run()