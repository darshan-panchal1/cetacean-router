import asyncio
import logging
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from groq import AsyncGroq

from config.settings import settings
from utils.geometry import create_route_buffer
from utils.resilience import (
    TTLCache,
    async_retry,
    get_breaker,
    CircuitOpenError,
    obis_cache,
)

# ------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------
logger = logging.getLogger("agents.biologist")


class BiologistAgent:
    """
    Agent B: The Marine Biologist
    Assesses ecological risk along proposed routes using OBIS data.
    Caches OBIS results (geometry hash → response) to avoid redundant
    API calls across iterations.
    """

    def __init__(self):
        logger.info("Initializing BiologistAgent | model=%s", settings.biologist_model)
        self._client: Optional[AsyncGroq] = (
            AsyncGroq(api_key=settings.groq_api_key)
            if settings.groq_configured
            else None
        )
        self.model = settings.biologist_model
        self._breaker = get_breaker(
            "groq_biologist",
            failure_threshold=settings.circuit_breaker_failure_threshold,
            recovery_timeout=settings.circuit_breaker_recovery_timeout,
        )

    # ------------------------------------------------------------------
    # Core risk assessment
    # ------------------------------------------------------------------

    async def assess_route_risk(
        self,
        waypoints: List[Tuple[float, float]],
        obis_tool_function: Callable,
    ) -> Dict:
        """
        Assess ecological risk for a route using OBIS data.
        Results are cached by geometry to avoid redundant OBIS calls.
        """
        wkt_geometry = create_route_buffer(waypoints, buffer_degrees=0.5)

        # Cache lookup
        cache_key = obis_cache.make_key(wkt_geometry, "Cetacea")
        cached = obis_cache.get(cache_key)
        if cached is not None:
            logger.info("OBIS cache hit | key=%s", cache_key)
            return cached

        t0 = time.monotonic()
        try:
            logger.info("OBIS query | wkt_len=%d", len(wkt_geometry))
            obis_result = await _call_obis(obis_tool_function, wkt_geometry, "Cetacea")

            if not obis_result.get("success", False):
                logger.warning("OBIS returned unsuccessful result")
                return _unknown_risk()

            risk_level = obis_result["risk_level"]
            risk_score = obis_result["risk_score"]
            sighting_count = obis_result["sighting_count"]
            species_list = obis_result.get("species_list", [])

            recommendation = _build_recommendation(risk_level)

            result = {
                "risk_level": risk_level,
                "risk_score": risk_score,
                "sighting_count": sighting_count,
                "species_list": species_list,
                "recommendation": recommendation,
                "geometry_assessed": wkt_geometry,
            }

            obis_cache.set(cache_key, result)
            elapsed = round(time.monotonic() - t0, 2)
            logger.info(
                "Route risk assessed | level=%s | sightings=%d | elapsed=%ss",
                risk_level, sighting_count, elapsed,
            )
            return result

        except Exception:
            logger.exception("Error during route risk assessment")
            return _unknown_risk()

    async def identify_critical_sectors(
        self,
        waypoints: List[Tuple[float, float]],
        obis_tool_function: Callable,
    ) -> List[Dict]:
        """
        Break route into segments and identify high/medium-risk sectors.
        Sectors are assessed concurrently for speed.
        """
        logger.info(
            "Identifying critical sectors | segments=%d", len(waypoints) - 1
        )

        async def _assess_segment(i: int) -> Optional[Dict]:
            start, end = waypoints[i], waypoints[i + 1]
            sector = {
                "lat_min": min(start[0], end[0]) - 0.5,
                "lat_max": max(start[0], end[0]) + 0.5,
                "lon_min": min(start[1], end[1]) - 0.5,
                "lon_max": max(start[1], end[1]) + 0.5,
                "segment": i,
            }
            wkt = create_route_buffer([start, end], buffer_degrees=0.5)
            try:
                result = await _call_obis(obis_tool_function, wkt, "Cetacea")
                if result.get("risk_level") in ("HIGH", "MEDIUM"):
                    logger.warning(
                        "Critical sector | seg=%d | level=%s | sightings=%d",
                        i, result["risk_level"], result["sighting_count"],
                    )
                    return {**sector, "risk_level": result["risk_level"],
                            "sighting_count": result["sighting_count"]}
            except Exception:
                logger.exception("Sector %d assessment failed", i)
            return None

        tasks = [_assess_segment(i) for i in range(len(waypoints) - 1)]
        results = await asyncio.gather(*tasks, return_exceptions=False)
        critical = [r for r in results if r is not None]

        logger.info("Critical sectors found: %d", len(critical))
        return critical

    # ------------------------------------------------------------------
    # LLM biological report
    # ------------------------------------------------------------------

    @async_retry(max_attempts=3, base_delay=1.0, exceptions=(Exception,))
    async def generate_biological_report(
        self,
        risk_assessment: Dict,
        critical_sectors: List[Dict],
    ) -> str:
        """Use LLM to generate a biological assessment report."""
        if not self._client:
            return "LLM unavailable — Groq API key not configured."

        if not self._breaker.is_available():
            raise CircuitOpenError("groq_biologist circuit is open")

        species_str = ", ".join(risk_assessment.get("species_list", [])[:5]) or "none identified"

        prompt = f"""You are a marine conservation biologist. Summarise this route assessment (≤120 words):

Overall Risk: {risk_assessment['risk_level']}
Cetacean Sightings: {risk_assessment['sighting_count']}
Critical Sectors: {len(critical_sectors)}
Species: {species_str}

Cover: (1) conservation concern, (2) key species at risk, (3) recommendation."""

        t0 = time.monotonic()
        try:
            resp = await self._client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=settings.llm_temperature_biologist,
                max_tokens=settings.llm_max_tokens,
            )
            self._breaker.record_success()
            logger.info(
                "Biological report generated | elapsed=%.2fs",
                time.monotonic() - t0,
            )
            return resp.choices[0].message.content
        except Exception as exc:
            self._breaker.record_failure()
            raise exc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _call_obis(fn: Callable, wkt: str, taxon: str) -> Dict:
    """
    Call the OBIS tool function.  Wraps synchronous or async callables
    so that sync tools (e.g. FastMCP) run in a thread-pool.
    """
    if asyncio.iscoroutinefunction(fn):
        return await fn(wkt_geometry=wkt, taxon=taxon)
    return await asyncio.to_thread(fn, wkt_geometry=wkt, taxon=taxon)


def _unknown_risk() -> Dict:
    return {
        "risk_level": "UNKNOWN",
        "risk_score": 5,
        "sighting_count": 0,
        "species_list": [],
        "recommendation": "Risk assessment unavailable — proceed with caution.",
    }


def _build_recommendation(risk_level: str) -> str:
    if risk_level == "HIGH":
        return (
            "REJECT — High cetacean density detected. "
            "Detour or significant speed reduction required."
        )
    if risk_level == "MEDIUM":
        return (
            "CAUTION — Moderate cetacean activity. "
            "Speed reduction through this sector recommended."
        )
    return "ACCEPTABLE — Low cetacean activity detected."