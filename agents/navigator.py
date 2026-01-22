from groq import Groq
from typing import List, Tuple, Dict
from config.settings import settings
from utils.geometry import calculate_route_distance, haversine_distance
import logging
import time


# ------------------------------------------------------------------
# Logging configuration
# ------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger("NavigatorAgent")


class NavigatorAgent:
    '''
    Agent A: The Navigator
    Calculates optimal routes based on distance and ETA.
    '''

    def __init__(self):
        logger.info("Initializing NavigatorAgent")
        self.client = Groq(api_key=settings.groq_api_key)
        self.model = settings.navigator_model
        logger.info("NavigatorAgent initialized | model=%s", self.model)

    def calculate_direct_route(
        self,
        start: Tuple[float, float],
        end: Tuple[float, float],
        speed_knots: float = None
    ) -> Dict:
        '''Calculate the most direct route between two points.'''
        logger.info("calculate_direct_route invoked")
        logger.debug("Start=%s End=%s Speed=%s", start, end, speed_knots)

        if speed_knots is None:
            speed_knots = settings.default_ship_speed_knots
            logger.debug("Using default speed: %s knots", speed_knots)

        distance = haversine_distance(start[0], start[1], end[0], end[1])
        eta_hours = distance / speed_knots

        logger.info(
            "Direct route computed | distance=%.2f nm eta=%.2f hrs",
            distance, eta_hours
        )

        return {
            "route_name": "Route Alpha (Direct)",
            "waypoints": [start, end],
            "distance_nm": round(distance, 2),
            "speed_knots": speed_knots,
            "eta_hours": round(eta_hours, 2),
            "route_type": "direct"
        }

    def calculate_detour_route(
        self,
        start: Tuple[float, float],
        end: Tuple[float, float],
        avoid_sector: Dict[str, float],
        speed_knots: float = None
    ) -> Dict:
        '''Calculate a detour route avoiding a specific sector.'''
        logger.info("calculate_detour_route invoked")
        logger.debug(
            "Start=%s End=%s Sector=%s Speed=%s",
            start, end, avoid_sector, speed_knots
        )

        if speed_knots is None:
            speed_knots = settings.default_ship_speed_knots
            logger.debug("Using default speed: %s knots", speed_knots)

        sector_center_lat = (avoid_sector["lat_min"] + avoid_sector["lat_max"]) / 2
        sector_center_lon = (avoid_sector["lon_min"] + avoid_sector["lon_max"]) / 2

        logger.debug(
            "Sector center | lat=%s lon=%s",
            sector_center_lat, sector_center_lon
        )

        # Determine detour orientation
        if abs(end[1] - start[1]) > abs(end[0] - start[0]):
            logger.info("Primarily east-west route detected")

            if start[0] < sector_center_lat:
                mid_lat = avoid_sector["lat_min"] - 1.0
                logger.info("Detouring south")
            else:
                mid_lat = avoid_sector["lat_max"] + 1.0
                logger.info("Detouring north")

            mid_lon = (start[1] + end[1]) / 2

        else:
            logger.info("Primarily north-south route detected")

            if start[1] < sector_center_lon:
                mid_lon = avoid_sector["lon_min"] - 1.0
                logger.info("Detouring west")
            else:
                mid_lon = avoid_sector["lon_max"] + 1.0
                logger.info("Detouring east")

            mid_lat = (start[0] + end[0]) / 2

        waypoints = [start, (mid_lat, mid_lon), end]
        logger.debug("Detour waypoints=%s", waypoints)

        distance = calculate_route_distance(waypoints)
        eta_hours = distance / speed_knots

        logger.info(
            "Detour route computed | distance=%.2f nm eta=%.2f hrs",
            distance, eta_hours
        )

        return {
            "route_name": "Route Beta (Detour)",
            "waypoints": waypoints,
            "distance_nm": round(distance, 2),
            "speed_knots": speed_knots,
            "eta_hours": round(eta_hours, 2),
            "route_type": "detour",
            "avoided_sector": avoid_sector
        }

    def calculate_slow_route(
        self,
        start: Tuple[float, float],
        end: Tuple[float, float],
        risk_sector: Dict[str, float]
    ) -> Dict:
        '''Calculate a route with reduced speed through risky area.'''
        logger.info("calculate_slow_route invoked")
        logger.debug("Start=%s End=%s Risk sector=%s", start, end, risk_sector)

        distance = haversine_distance(start[0], start[1], end[0], end[1])
        reduced_speed = settings.reduced_speed_knots
        eta_hours = distance / reduced_speed

        logger.info(
            "Reduced-speed route computed | distance=%.2f nm eta=%.2f hrs speed=%s",
            distance, eta_hours, reduced_speed
        )

        return {
            "route_name": "Route Gamma (Reduced Speed)",
            "waypoints": [start, end],
            "distance_nm": round(distance, 2),
            "speed_knots": reduced_speed,
            "eta_hours": round(eta_hours, 2),
            "route_type": "reduced_speed",
            "risk_sector": risk_sector
        }

    def reason_about_routes(self, routes: List[Dict]) -> str:
        '''Use LLM to reason about route options.'''
        logger.info("reason_about_routes invoked")
        logger.debug("Routes provided=%s", routes)

        prompt = f'''You are a maritime navigation expert. Analyze these route options:

{self._format_routes(routes)}

Provide a brief technical analysis focusing on:
1. Distance efficiency
2. Time trade-offs
3. Operational considerations

Keep response under 100 words.'''

        logger.debug("LLM prompt=%s", prompt)

        start_time = time.time()

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=200
            )

            elapsed = round(time.time() - start_time, 2)
            logger.info("Navigation reasoning generated in %ss", elapsed)

            return response.choices[0].message.content

        except Exception as e:
            logger.exception("Failed to generate navigation reasoning")
            return f"Navigation analysis unavailable: {str(e)}"

    def _format_routes(self, routes: List[Dict]) -> str:
        '''Format routes for LLM prompt.'''
        logger.debug("Formatting %s routes for LLM", len(routes))

        formatted = []
        for route in routes:
            formatted.append(
                f"- {route['route_name']}: "
                f"{route['distance_nm']} nm, "
                f"{route['eta_hours']} hrs @ {route['speed_knots']} knots"
            )

        return "\n".join(formatted)
