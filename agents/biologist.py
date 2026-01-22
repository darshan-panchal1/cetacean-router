from groq import Groq
from typing import List, Tuple, Dict
from config.settings import settings
from utils.geometry import create_route_buffer
import logging
import time
import json


# ------------------------------------------------------------------
# Logging configuration
# ------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger("BiologistAgent")


class BiologistAgent:
    '''
    Agent B: The Marine Biologist
    Assesses ecological risk along proposed routes.
    '''

    def __init__(self):
        logger.info("Initializing BiologistAgent")
        self.client = Groq(api_key=settings.groq_api_key)
        self.model = settings.biologist_model
        logger.info("BiologistAgent initialized | model=%s", self.model)

    def assess_route_risk(
        self,
        waypoints: List[Tuple[float, float]],
        obis_tool_function
    ) -> Dict:
        '''
        Assess ecological risk for a route using OBIS data.
        '''
        logger.info("assess_route_risk invoked")
        logger.debug("Waypoints received: %s", waypoints)

        start_time = time.time()

        # ------------------------------------------------------------------
        # Geometry preparation
        # ------------------------------------------------------------------
        wkt_geometry = create_route_buffer(waypoints, buffer_degrees=0.5)
        logger.debug("Generated route buffer WKT=%s", wkt_geometry)

        try:
            # ------------------------------------------------------------------
            # OBIS MCP call
            # ------------------------------------------------------------------
            logger.info("Calling OBIS MCP tool for cetacean risk assessment")
            obis_result = obis_tool_function(
                wkt_geometry=wkt_geometry,
                taxon="Cetacea"
            )

            logger.debug("OBIS result=%s", obis_result)

            if not obis_result.get("success", False):
                logger.warning("OBIS risk assessment unsuccessful")
                return {
                    "risk_level": "UNKNOWN",
                    "risk_score": 5,
                    "sighting_count": 0,
                    "species_list": [],
                    "recommendation": "Unable to assess risk - proceed with caution"
                }

            risk_level = obis_result["risk_level"]
            risk_score = obis_result["risk_score"]
            sighting_count = obis_result["sighting_count"]
            species_list = obis_result.get("species_list", [])

            logger.info(
                "Risk summary | level=%s score=%s sightings=%s",
                risk_level, risk_score, sighting_count
            )

            # ------------------------------------------------------------------
            # Recommendation logic
            # ------------------------------------------------------------------
            if risk_level == "HIGH":
                recommendation = (
                    "REJECT - High cetacean density detected. "
                    "Recommend detour or speed reduction."
                )
            elif risk_level == "MEDIUM":
                recommendation = (
                    "CAUTION - Moderate risk. "
                    "Consider speed reduction through this sector."
                )
            else:
                recommendation = "ACCEPTABLE - Low risk detected."

            elapsed = round(time.time() - start_time, 2)
            logger.info("Route risk assessed in %ss", elapsed)

            return {
                "risk_level": risk_level,
                "risk_score": risk_score,
                "sighting_count": sighting_count,
                "species_list": species_list,
                "recommendation": recommendation,
                "geometry_assessed": wkt_geometry
            }

        except Exception as e:
            logger.exception("Error during route risk assessment")
            return {
                "risk_level": "ERROR",
                "risk_score": 0,
                "error": str(e),
                "recommendation": "Risk assessment failed"
            }

    def identify_critical_sectors(
        self,
        waypoints: List[Tuple[float, float]],
        obis_tool_function
    ) -> List[Dict]:
        '''
        Break route into sectors and identify high-risk areas.
        '''
        logger.info("identify_critical_sectors invoked")
        logger.debug("Waypoints=%s", waypoints)

        critical_sectors = []

        for i in range(len(waypoints) - 1):
            start = waypoints[i]
            end = waypoints[i + 1]

            logger.info("Assessing sector %s | %s -> %s", i, start, end)

            sector = {
                "lat_min": min(start[0], end[0]) - 0.5,
                "lat_max": max(start[0], end[0]) + 0.5,
                "lon_min": min(start[1], end[1]) - 0.5,
                "lon_max": max(start[1], end[1]) + 0.5,
                "segment": i
            }

            wkt = create_route_buffer([start, end], buffer_degrees=0.5)
            logger.debug("Sector %s WKT=%s", i, wkt)

            try:
                result = obis_tool_function(
                    wkt_geometry=wkt,
                    taxon="Cetacea"
                )

                logger.debug("Sector %s OBIS result=%s", i, result)

                if result.get("risk_level") in ["HIGH", "MEDIUM"]:
                    logger.warning(
                        "Critical sector detected | segment=%s level=%s sightings=%s",
                        i, result["risk_level"], result["sighting_count"]
                    )

                    critical_sectors.append({
                        **sector,
                        "risk_level": result["risk_level"],
                        "sighting_count": result["sighting_count"]
                    })

            except Exception:
                logger.exception("Failed to assess sector %s", i)

        logger.info(
            "Critical sector identification complete | count=%s",
            len(critical_sectors)
        )

        return critical_sectors

    def generate_biological_report(
        self,
        risk_assessment: Dict,
        critical_sectors: List[Dict]
    ) -> str:
        '''
        Use LLM to generate biological assessment report.
        '''
        logger.info("generate_biological_report invoked")

        prompt = f'''You are a marine conservation biologist. Generate a brief report on this route assessment:

Overall Risk: {risk_assessment['risk_level']}
Cetacean Sightings: {risk_assessment['sighting_count']}
Critical Sectors: {len(critical_sectors)}

Species Detected: {', '.join(risk_assessment.get('species_list', [])[:5])}

Provide:
1. Conservation concern summary
2. Key species at risk
3. Recommendation

Keep under 150 words.'''

        logger.debug("LLM prompt=%s", prompt)

        start_time = time.time()

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4,
                max_tokens=250
            )

            elapsed = round(time.time() - start_time, 2)
            logger.info("Biological report generated in %ss", elapsed)

            return response.choices[0].message.content

        except Exception as e:
            logger.exception("Failed to generate biological report")
            return f"Biological report unavailable: {str(e)}"
