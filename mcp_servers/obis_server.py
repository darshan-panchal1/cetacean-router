"""
OBIS Marine Biology MCP Server
Queries the Ocean Biodiversity Information System for cetacean sightings.
Includes TTL caching, circuit breaker, and structured logging.
"""

import asyncio
import logging
import time
from typing import Optional

from fastmcp import FastMCP
from pyobis import occurrences

from config.settings import settings
from utils.resilience import obis_cache, get_breaker, CircuitOpenError

# ------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("mcp.obis")

mcp = FastMCP("MarineBiologyData")

_breaker = get_breaker("obis_api", failure_threshold=5, recovery_timeout=120)

# Risk thresholds (sighting count) — sourced from settings for consistency
_HIGH_THRESHOLD   = settings.risk_threshold_high    # default 50
_MEDIUM_THRESHOLD = settings.risk_threshold_medium  # default 10


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def check_species_risk(
    wkt_geometry: str,
    taxon: str = "Cetacea",
    days_back: int = 365,
) -> dict:
    """
    Query OBIS for species occurrences within a given WKT geometry.

    Returns risk level, sighting count, and species diversity derived
    from real OBIS occurrence data.  Results are cached for 1 hour to
    reduce external API load.

    Performance note:
      We only fetch settings.obis_results_size records (default 60).
      Risk thresholds are 50 (HIGH) and 10 (MEDIUM), so 60 records is
      enough to classify any zone accurately while keeping query time
      under ~1 second instead of the ~6-7s seen with size=500.
    """
    cache_key = obis_cache.make_key(wkt_geometry, taxon)
    cached = obis_cache.get(cache_key)
    if cached is not None:
        logger.info("Cache hit | key=%s", cache_key)
        return cached

    if not _breaker.is_available():
        logger.error("OBIS circuit is OPEN — returning degraded response")
        return _degraded_response(taxon)

    t0 = time.monotonic()
    fetch_size = settings.obis_results_size  # 60 by default
    logger.info(
        "Querying OBIS | taxon=%s | wkt_len=%d | size=%d",
        taxon, len(wkt_geometry), fetch_size,
    )

    try:
        query = occurrences.search(
            geometry=wkt_geometry,
            scientificname=taxon,
            size=fetch_size,
        )
        data = query.execute()
        elapsed = round(time.monotonic() - t0, 2)
        logger.info("OBIS query completed | elapsed=%ss", elapsed)

        # pyobis returns a pandas DataFrame — never use bare truthiness on it
        import pandas as pd
        if data is None or (isinstance(data, pd.DataFrame) and data.empty):
            count = 0
        else:
            count = len(data)

        risk_level, risk_score = _classify_risk(count)

        species_list: list = []
        if count > 0 and isinstance(data, pd.DataFrame):
            try:
                col = next(
                    (c for c in ("species", "scientificName", "scientificname")
                     if c in data.columns),
                    None,
                )
                if col:
                    species_list = (
                        data[col].dropna().drop_duplicates().head(10).tolist()
                    )
            except Exception as sp_exc:
                logger.warning("Species extraction failed: %s", sp_exc)

        result = {
            "success": True,
            "taxon": taxon,
            "sighting_count": count,
            "risk_level": risk_level,
            "risk_score": risk_score,
            "species_diversity": len(species_list),
            "species_list": species_list,
            "data_source": "OBIS",
            "geometry": wkt_geometry,
        }

        obis_cache.set(cache_key, result)
        _breaker.record_success()

        logger.info(
            "Risk result | level=%s | score=%s | sightings=%d | species=%d",
            risk_level, risk_score, count, len(species_list),
        )
        return result

    except Exception as exc:
        _breaker.record_failure()
        logger.exception("OBIS query failed: %s", exc)
        return {
            "success": False,
            "error": str(exc),
            "taxon": taxon,
            "sighting_count": 0,
            "risk_level": "UNKNOWN",
        }


@mcp.tool()
def get_sector_details(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    taxon: str = "Cetacea",
) -> dict:
    """
    Get detailed marine mammal data for a rectangular bounding box.
    Delegates to check_species_risk with a WKT polygon.
    """
    logger.info(
        "Sector query | lat=[%.2f,%.2f] lon=[%.2f,%.2f] taxon=%s",
        lat_min, lat_max, lon_min, lon_max, taxon,
    )
    wkt = (
        f"POLYGON(({lon_min} {lat_min}, {lon_max} {lat_min}, "
        f"{lon_max} {lat_max}, {lon_min} {lat_max}, {lon_min} {lat_min}))"
    )
    return check_species_risk(wkt, taxon)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _classify_risk(count: int):
    if count > _HIGH_THRESHOLD:
        return "HIGH", 8
    if count > _MEDIUM_THRESHOLD:
        return "MEDIUM", 5
    return "LOW", 2


def _degraded_response(taxon: str) -> dict:
    """Returned when the OBIS circuit is open."""
    return {
        "success": False,
        "error": "OBIS service temporarily unavailable (circuit open).",
        "taxon": taxon,
        "sighting_count": 0,
        "risk_level": "UNKNOWN",
        "risk_score": 5,
        "species_list": [],
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logger.info("Starting MarineBiologyData MCP server")
    mcp.run()