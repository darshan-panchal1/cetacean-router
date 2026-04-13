import logging
import time
from typing import Dict, List, Optional, Tuple

from groq import AsyncGroq

from config.settings import settings
from utils.geometry import calculate_route_distance, haversine_distance
from utils.resilience import async_retry, get_breaker, CircuitOpenError

# ------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------
logger = logging.getLogger("agents.navigator")


class NavigatorAgent:
    """
    Agent A: The Navigator
    Calculates optimal routes based on distance and ETA.
    All LLM calls are async with circuit-breaker protection.
    """

    def __init__(self):
        logger.info("Initializing NavigatorAgent | model=%s", settings.navigator_model)
        self._client: Optional[AsyncGroq] = (
            AsyncGroq(api_key=settings.groq_api_key)
            if settings.groq_configured
            else None
        )
        self.model = settings.navigator_model
        self._breaker = get_breaker(
            "groq_navigator",
            failure_threshold=settings.circuit_breaker_failure_threshold,
            recovery_timeout=settings.circuit_breaker_recovery_timeout,
        )

    # ------------------------------------------------------------------
    # Route calculators (synchronous math — no I/O)
    # ------------------------------------------------------------------

    def calculate_direct_route(
        self,
        start: Tuple[float, float],
        end: Tuple[float, float],
        speed_knots: Optional[float] = None,
    ) -> Dict:
        """Calculate the most direct route between two points."""
        speed_knots = speed_knots or settings.default_ship_speed_knots
        distance = haversine_distance(start[0], start[1], end[0], end[1])
        eta_hours = distance / speed_knots

        logger.info(
            "Direct route | distance=%.1f nm | eta=%.1f h", distance, eta_hours
        )
        return {
            "route_name": "Route Alpha (Direct)",
            "waypoints": [start, end],
            "distance_nm": round(distance, 2),
            "speed_knots": speed_knots,
            "eta_hours": round(eta_hours, 2),
            "route_type": "direct",
        }

    def calculate_detour_route(
        self,
        start: Tuple[float, float],
        end: Tuple[float, float],
        avoid_sector: Dict[str, float],
        speed_knots: Optional[float] = None,
    ) -> Dict:
        """Calculate a detour route that avoids a high-risk sector."""
        speed_knots = speed_knots or settings.default_ship_speed_knots

        sector_center_lat = (avoid_sector["lat_min"] + avoid_sector["lat_max"]) / 2
        sector_center_lon = (avoid_sector["lon_min"] + avoid_sector["lon_max"]) / 2

        # Choose detour direction based on route orientation
        if abs(end[1] - start[1]) > abs(end[0] - start[0]):
            # Primarily east-west → detour north or south
            if start[0] < sector_center_lat:
                mid_lat = avoid_sector["lat_min"] - 1.5
            else:
                mid_lat = avoid_sector["lat_max"] + 1.5
            mid_lon = (start[1] + end[1]) / 2
        else:
            # Primarily north-south → detour east or west
            if start[1] < sector_center_lon:
                mid_lon = avoid_sector["lon_min"] - 1.5
            else:
                mid_lon = avoid_sector["lon_max"] + 1.5
            mid_lat = (start[0] + end[0]) / 2

        waypoints = [start, (mid_lat, mid_lon), end]
        distance = calculate_route_distance(waypoints)
        eta_hours = distance / speed_knots

        logger.info(
            "Detour route | distance=%.1f nm | eta=%.1f h | mid=(%.2f,%.2f)",
            distance, eta_hours, mid_lat, mid_lon,
        )
        return {
            "route_name": "Route Beta (Detour)",
            "waypoints": waypoints,
            "distance_nm": round(distance, 2),
            "speed_knots": speed_knots,
            "eta_hours": round(eta_hours, 2),
            "route_type": "detour",
            "avoided_sector": avoid_sector,
        }

    def calculate_slow_route(
        self,
        start: Tuple[float, float],
        end: Tuple[float, float],
        risk_sector: Dict[str, float],
    ) -> Dict:
        """Direct route but at whale-safe reduced speed."""
        reduced_speed = settings.reduced_speed_knots
        distance = haversine_distance(start[0], start[1], end[0], end[1])
        eta_hours = distance / reduced_speed

        logger.info(
            "Reduced-speed route | distance=%.1f nm | eta=%.1f h | speed=%s kn",
            distance, eta_hours, reduced_speed,
        )
        return {
            "route_name": "Route Gamma (Reduced Speed)",
            "waypoints": [start, end],
            "distance_nm": round(distance, 2),
            "speed_knots": reduced_speed,
            "eta_hours": round(eta_hours, 2),
            "route_type": "reduced_speed",
            "risk_sector": risk_sector,
        }

    # ------------------------------------------------------------------
    # LLM reasoning
    # ------------------------------------------------------------------

    @async_retry(max_attempts=3, base_delay=1.0, exceptions=(Exception,))
    async def reason_about_routes(self, routes: List[Dict]) -> str:
        """Use Groq LLM to reason about route options."""
        if not self._client:
            return "LLM unavailable — Groq API key not configured."

        if not self._breaker.is_available():
            raise CircuitOpenError("groq_navigator circuit is open")

        prompt = f"""You are a maritime navigation expert. Analyse these route options:

{self._format_routes(routes)}

Provide a concise technical analysis (≤100 words) focusing on:
1. Distance and fuel efficiency
2. ETA trade-offs
3. Operational feasibility"""

        t0 = time.monotonic()
        try:
            resp = await self._client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=settings.llm_temperature_navigator,
                max_tokens=settings.llm_max_tokens,
            )
            self._breaker.record_success()
            elapsed = round(time.monotonic() - t0, 2)
            logger.info("Navigator LLM reasoning | elapsed=%ss", elapsed)
            return resp.choices[0].message.content
        except Exception as exc:
            self._breaker.record_failure()
            raise exc

    def _format_routes(self, routes: List[Dict]) -> str:
        lines = []
        for r in routes:
            lines.append(
                f"- {r['route_name']}: {r['distance_nm']} nm, "
                f"{r['eta_hours']} h @ {r['speed_knots']} kn"
            )
        return "\n".join(lines)