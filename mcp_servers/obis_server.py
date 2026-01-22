from fastmcp import FastMCP
from pyobis import occurrences
from typing import Optional
import json
import logging
import time


# ------------------------------------------------------------------
# Logging configuration
# ------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger("MarineBiologyData")


mcp = FastMCP("MarineBiologyData")


@mcp.tool()
def check_species_risk(
    wkt_geometry: str,
    taxon: str = "Cetacea",
    days_back: int = 365
) -> dict:
    """
    Query OBIS for species occurrences within a given geometry.
    """
    logger.info("check_species_risk invoked")
    logger.debug("Input parameters | taxon=%s | days_back=%s", taxon, days_back)
    logger.debug("WKT geometry=%s", wkt_geometry)

    start_time = time.time()

    try:
        # ------------------------------------------------------------------
        # OBIS query
        # ------------------------------------------------------------------
        logger.info("Querying OBIS occurrences API")
        query = occurrences.search(
            geometry=wkt_geometry,
            scientificname=taxon,
            size=500
        )

        logger.debug("OBIS query object created: %s", query)

        data = query.execute()

        elapsed = round(time.time() - start_time, 2)
        logger.info("OBIS query executed in %ss", elapsed)

        # ------------------------------------------------------------------
        # Data validation
        # ------------------------------------------------------------------
        if data is None:
            logger.warning("OBIS returned no data (None)")
            count = 0
        else:
            count = len(data)
            logger.info("OBIS returned %s occurrence records", count)

        # ------------------------------------------------------------------
        # Risk calculation
        # ------------------------------------------------------------------
        risk_level = "LOW"
        risk_score = 2

        if count > 50:
            risk_level = "HIGH"
            risk_score = 8
        elif count > 10:
            risk_level = "MEDIUM"
            risk_score = 5

        logger.info(
            "Risk assessment completed | level=%s | score=%s",
            risk_level,
            risk_score
        )

        # ------------------------------------------------------------------
        # Species diversity extraction
        # ------------------------------------------------------------------
        species_list = []
        if data:
            species_list = list(set(
                record.get("species", "Unknown")
                for record in data
                if isinstance(record, dict)
            ))

        logger.info(
            "Species diversity calculated | unique_species=%s",
            len(species_list)
        )

        return {
            "success": True,
            "taxon": taxon,
            "sighting_count": count,
            "risk_level": risk_level,
            "risk_score": risk_score,
            "species_diversity": len(species_list),
            "species_list": species_list[:10],
            "data_source": "OBIS",
            "geometry": wkt_geometry
        }

    except Exception as e:
        logger.exception("Error while processing species risk")
        return {
            "success": False,
            "error": str(e),
            "taxon": taxon,
            "sighting_count": 0,
            "risk_level": "UNKNOWN"
        }


@mcp.tool()
def get_sector_details(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    taxon: str = "Cetacea"
) -> dict:
    """
    Get detailed marine mammal data for a rectangular sector.
    """
    logger.info("get_sector_details invoked")
    logger.debug(
        "Bounding box | lat_min=%s lat_max=%s lon_min=%s lon_max=%s taxon=%s",
        lat_min, lat_max, lon_min, lon_max, taxon
    )

    # Create WKT polygon from bounds
    wkt = (
        f"POLYGON(({lon_min} {lat_min}, "
        f"{lon_max} {lat_min}, "
        f"{lon_max} {lat_max}, "
        f"{lon_min} {lat_max}, "
        f"{lon_min} {lat_min}))"
    )

    logger.debug("Generated WKT polygon=%s", wkt)

    return check_species_risk(wkt, taxon)


if __name__ == "__main__":
    logger.info("Starting MarineBiologyData MCP server")
    mcp.run()
