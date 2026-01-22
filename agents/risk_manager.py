from groq import Groq
from typing import List, Dict
from config.settings import settings
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
logger = logging.getLogger("RiskManagerAgent")


class RiskManagerAgent:
    '''
    Agent C: The Risk Manager (Supervisor)
    Mediates between Navigator and Biologist to select optimal route.
    '''

    def __init__(self):
        logger.info("Initializing RiskManagerAgent")
        self.client = Groq(api_key=settings.groq_api_key)
        self.model = settings.risk_manager_model
        logger.info("RiskManagerAgent initialized | model=%s", self.model)

    def evaluate_route_options(
        self,
        routes: List[Dict],
        risk_assessments: List[Dict]
    ) -> Dict:
        '''
        Evaluate all route options and select the best compromise.
        '''
        logger.info("evaluate_route_options invoked")
        logger.debug(
            "Routes count=%s | Risk assessments count=%s",
            len(routes), len(risk_assessments)
        )

        scored_routes = []

        # ------------------------------------------------------------------
        # Composite scoring
        # ------------------------------------------------------------------
        for idx, (route, risk) in enumerate(zip(routes, risk_assessments)):
            score = self._calculate_composite_score(route, risk)
            logger.info(
                "Route scored | index=%s name=%s score=%s",
                idx, route.get("route_name"), score
            )

            scored_routes.append({
                "route": route,
                "risk": risk,
                "composite_score": score
            })

        scored_routes.sort(
            key=lambda x: x["composite_score"],
            reverse=True
        )

        selected = scored_routes[0]
        logger.info(
            "Route selected | name=%s score=%s",
            selected["route"].get("route_name"),
            selected["composite_score"]
        )

        rationale = self._generate_rationale(selected, scored_routes)

        return {
            "selected_route": selected["route"],
            "risk_assessment": selected["risk"],
            "composite_score": selected["composite_score"],
            "all_options": scored_routes,
            "decision_rationale": rationale
        }

    def _calculate_composite_score(
        self,
        route: Dict,
        risk: Dict
    ) -> float:
        '''
        Calculate a composite score balancing efficiency and safety.
        '''
        logger.debug(
            "Calculating composite score | route=%s risk=%s",
            route.get("route_name"),
            risk.get("risk_level")
        )

        # ETA score (max 40)
        eta_score = max(
            0,
            40 - (route["eta_hours"] / 48.0 * 40)
        )

        # Distance score (max 30)
        distance_score = max(
            0,
            30 - (route["distance_nm"] / 1000.0 * 30)
        )

        # Risk score (max 30, inverse)
        risk_score_raw = risk.get("risk_score", 5)
        risk_score = 30 - (risk_score_raw / 10.0 * 30)

        total_score = eta_score + distance_score + risk_score

        logger.debug(
            "Score breakdown | eta=%.2f distance=%.2f risk=%.2f total=%.2f",
            eta_score, distance_score, risk_score, total_score
        )

        return round(total_score, 2)

    def _generate_rationale(
        self,
        selected: Dict,
        all_options: List[Dict]
    ) -> str:
        '''
        Generate human-readable decision rationale.
        '''
        route = selected["route"]
        risk = selected["risk"]

        logger.info(
            "Generating rationale for route=%s",
            route.get("route_name")
        )

        rationale = (
            f"Selected {route['route_name']} with composite score "
            f"{selected['composite_score']}/100. "
            f"Route covers {route['distance_nm']} nm in "
            f"{route['eta_hours']} hours. "
            f"Ecological risk: {risk['risk_level']} "
            f"({risk.get('sighting_count', 0)} cetacean sightings). "
        )

        if len(all_options) > 1:
            alternatives = [
                opt for opt in all_options if opt != selected
            ]
            rationale += (
                f"Rejected {len(alternatives)} alternative(s) "
                f"with lower composite scores."
            )

        logger.debug("Decision rationale=%s", rationale)
        return rationale

    def make_llm_decision(
        self,
        routes: List[Dict],
        risk_assessments: List[Dict]
    ) -> str:
        '''
        Use LLM to provide high-level strategic decision analysis.
        '''
        logger.info("make_llm_decision invoked")

        formatted_data = []
        for route, risk in zip(routes, risk_assessments):
            formatted_data.append({
                "route_name": route["route_name"],
                "distance_nm": route["distance_nm"],
                "eta_hours": route["eta_hours"],
                "speed_knots": route["speed_knots"],
                "risk_level": risk["risk_level"],
                "sightings": risk.get("sighting_count", 0)
            })

        logger.debug("LLM input data=%s", formatted_data)

        prompt = f'''You are a maritime risk manager balancing commercial logistics and marine conservation.

ROUTE OPTIONS:
{json.dumps(formatted_data, indent=2)}

Analyze the trade-offs and recommend the best route considering:
1. Delivery schedule impact
2. Ecological responsibility
3. Operational safety
4. Corporate reputation

Provide a decisive recommendation with brief justification (under 120 words).'''

        start_time = time.time()

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an expert maritime risk manager "
                            "specializing in sustainable shipping."
                        )
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.5,
                max_tokens=250
            )

            elapsed = round(time.time() - start_time, 2)
            logger.info("LLM decision generated in %ss", elapsed)

            return response.choices[0].message.content

        except Exception as e:
            logger.exception("Failed to generate LLM decision")
            return f"LLM decision analysis unavailable: {str(e)}"

    def approve_route(self, route: Dict, risk: Dict) -> bool:
        '''
        Final approval gate - reject routes that are too risky.
        '''
        logger.info(
            "approve_route invoked | route=%s risk=%s",
            route.get("route_name"),
            risk.get("risk_level")
        )

        # Hard rules
        if risk.get("risk_level") == "HIGH" and route.get("route_type") == "direct":
            logger.warning(
                "Route rejected: direct route through HIGH risk sector"
            )
            return False

        if risk.get("sighting_count", 0) > 100:
            logger.warning(
                "Route rejected: excessive cetacean density (%s sightings)",
                risk.get("sighting_count")
            )
            return False

        logger.info("Route approved")
        return True
