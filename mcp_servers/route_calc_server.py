from fastmcp import FastMCP
import math
import logging
import time
from typing import List, Dict


# ------------------------------------------------------------------
# Logging configuration
# ------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger("RouteCalculator")


mcp = FastMCP("RouteCalculator")


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great circle distance in nautical miles."""
    logger.debug(
        "Calculating haversine distance | (%s,%s) -> (%s,%s)",
        lat1, lon1, lat2, lon2
    )

    R = 3440.065  # Earth radius in nautical miles

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad)
        * math.cos(lat2_rad)
        * math.sin(delta_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    distance = R * c
    logger.debug("Segment distance computed: %.2f nm", distance)

    return distance


@mcp.tool()
def calculate_route_metrics(
    waypoints: List[List[float]],
    speed_knots: float = 18.0,
    fuel_consumption_rate: float = 1.0
) -> dict:
    """
    Calculate comprehensive metrics for a proposed route.
    """
    logger.info("calculate_route_metrics invoked")
    logger.debug(
        "Inputs | waypoints=%s speed_knots=%s fuel_rate=%s",
        waypoints, speed_knots, fuel_consumption_rate
    )

    start_time = time.time()

    try:
        if len(waypoints) < 2:
            logger.warning("Insufficient waypoints: %s", len(waypoints))
            return {"success": False, "error": "Need at least 2 waypoints"}

        total_distance = 0.0
        segments = []

        # ------------------------------------------------------------------
        # Distance calculation
        # ------------------------------------------------------------------
        for i in range(len(waypoints) - 1):
            lat1, lon1 = waypoints[i]
            lat2, lon2 = waypoints[i + 1]

            segment_distance = haversine_distance(lat1, lon1, lat2, lon2)
            total_distance += segment_distance

            logger.info(
                "Segment %s -> %s | %.2f nm",
                waypoints[i], waypoints[i + 1], segment_distance
            )

            segments.append({
                "from": waypoints[i],
                "to": waypoints[i + 1],
                "distance_nm": round(segment_distance, 2)
            })

        logger.info("Total route distance: %.2f nm", total_distance)

        # ------------------------------------------------------------------
        # ETA calculation
        # ------------------------------------------------------------------
        eta_hours = total_distance / speed_knots
        logger.info("ETA calculated: %.2f hours", eta_hours)

        # ------------------------------------------------------------------
        # Fuel estimation
        # ------------------------------------------------------------------
        base_fuel = (total_distance / 100.0) * fuel_consumption_rate
        speed_factor = (speed_knots / 18.0) ** 3
        estimated_fuel = base_fuel * speed_factor

        logger.info(
            "Fuel estimation | base=%.2f speed_factor=%.2f total=%.2f tons",
            base_fuel, speed_factor, estimated_fuel
        )

        elapsed = round(time.time() - start_time, 2)
        logger.info("Route metrics computed in %ss", elapsed)

        return {
            "success": True,
            "total_distance_nm": round(total_distance, 2),
            "eta_hours": round(eta_hours, 2),
            "eta_days": round(eta_hours / 24, 2),
            "speed_knots": speed_knots,
            "estimated_fuel_tons": round(estimated_fuel, 2),
            "segments": segments,
            "waypoint_count": len(waypoints)
        }

    except Exception as e:
        logger.exception("Error calculating route metrics")
        return {
            "success": False,
            "error": str(e)
        }


@mcp.tool()
def generate_detour_waypoints(
    start: List[float],
    end: List[float],
    avoid_sector: Dict[str, float],
    detour_margin_degrees: float = 1.0
) -> dict:
    """
    Generate alternative waypoints to avoid a risky sector.
    """
    logger.info("generate_detour_waypoints invoked")
    logger.debug(
        "Inputs | start=%s end=%s sector=%s margin=%s",
        start, end, avoid_sector, detour_margin_degrees
    )

    try:
        start_lat, start_lon = start
        end_lat, end_lon = end

        sector_center_lat = (avoid_sector["lat_min"] + avoid_sector["lat_max"]) / 2
        sector_center_lon = (avoid_sector["lon_min"] + avoid_sector["lon_max"]) / 2

        logger.debug(
            "Sector center | lat=%s lon=%s",
            sector_center_lat, sector_center_lon
        )

        # Determine route orientation
        if abs(end_lon - start_lon) > abs(end_lat - start_lat):
            logger.info("Primarily east-west route detected")

            if start_lat < sector_center_lat:
                mid_lat = avoid_sector["lat_min"] - detour_margin_degrees
                logger.info("Detouring south")
            else:
                mid_lat = avoid_sector["lat_max"] + detour_margin_degrees
                logger.info("Detouring north")

            mid_lon = (start_lon + end_lon) / 2
            waypoints = [start, [mid_lat, mid_lon], end]

        else:
            logger.info("Primarily north-south route detected")

            if start_lon < sector_center_lon:
                mid_lon = avoid_sector["lon_min"] - detour_margin_degrees
                logger.info("Detouring west")
            else:
                mid_lon = avoid_sector["lon_max"] + detour_margin_degrees
                logger.info("Detouring east")

            mid_lat = (start_lat + end_lat) / 2
            waypoints = [start, [mid_lat, mid_lon], end]

        logger.info("Detour waypoints generated: %s", waypoints)

        # ------------------------------------------------------------------
        # Calculate metrics for detour
        # ------------------------------------------------------------------
        metrics = calculate_route_metrics(waypoints)

        return {
            "success": True,
            "detour_waypoints": waypoints,
            "metrics": metrics,
            "avoided_sector": avoid_sector
        }

    except Exception as e:
        logger.exception("Error generating detour waypoints")
        return {
            "success": False,
            "error": str(e)
        }


if __name__ == "__main__":
    logger.info("Starting RouteCalculator MCP server")
    mcp.run()
