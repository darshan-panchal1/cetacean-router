import json
import logging
import time
from typing import Dict, List, Optional

from groq import AsyncGroq

from config.settings import settings
from utils.resilience import async_retry, get_breaker, CircuitOpenError

# ------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------
logger = logging.getLogger("agents.risk_manager")


class RiskManagerAgent:
    """
    Agent C: The Risk Manager (Supervisor)
    Mediates between Navigator and Biologist to select the optimal route.
    Composite scoring: ETA efficiency (40 pts) + distance (30 pts) + ecology (30 pts).

    Fixes vs original:
      1. _composite_score now applies a hard penalty to routes that
         approve_route() would reject (HIGH risk + direct type).  This
         stops the scorer from repeatedly picking Route Alpha as "best"
         only to have it rejected, which was forcing 3 full iterations.

      2. approve_route no longer rejects detour/reduced-speed routes
         purely because sightings > 100.  In highly active cetacean
         zones (e.g. the California coast), every route has 500+
         sightings — blanket rejection was making all routes
         un-approvable and forcing the loop to exhaust max_iterations.
         The rule now only applies to direct routes, consistent with
         the intent of "force a detour or speed reduction".
    """

    def __init__(self):
        logger.info("Initializing RiskManagerAgent | model=%s", settings.risk_manager_model)
        self._client: Optional[AsyncGroq] = (
            AsyncGroq(api_key=settings.groq_api_key)
            if settings.groq_configured
            else None
        )
        self.model = settings.risk_manager_model
        self._breaker = get_breaker(
            "groq_risk_manager",
            failure_threshold=settings.circuit_breaker_failure_threshold,
            recovery_timeout=settings.circuit_breaker_recovery_timeout,
        )

    # ------------------------------------------------------------------
    # Scoring & selection
    # ------------------------------------------------------------------

    def evaluate_route_options(
        self,
        routes: List[Dict],
        risk_assessments: List[Dict],
    ) -> Dict:
        """
        Evaluate all route/risk pairs and select the best composite score.
        Routes and risk_assessments must be index-aligned.
        """
        if not routes or not risk_assessments:
            raise ValueError("Cannot evaluate: no routes or risk assessments provided")

        pairs = list(zip(routes, risk_assessments))

        scored = []
        for route, risk in pairs:
            score = self._composite_score(route, risk)
            logger.info(
                "Scored | route=%s | score=%.1f | risk=%s",
                route.get("route_name"), score, risk.get("risk_level"),
            )
            scored.append({"route": route, "risk": risk, "composite_score": score})

        scored.sort(key=lambda x: x["composite_score"], reverse=True)
        best = scored[0]

        rationale = self._rationale(best, scored)
        logger.info(
            "Route selected | name=%s | score=%.1f",
            best["route"].get("route_name"), best["composite_score"],
        )

        return {
            "selected_route": best["route"],
            "risk_assessment": best["risk"],
            "composite_score": best["composite_score"],
            "all_options": scored,
            "decision_rationale": rationale,
        }

    def _composite_score(self, route: Dict, risk: Dict) -> float:
        """
        Composite score (0-100):
          ETA score    – max 40 pts (penalises routes > 48 h linearly)
          Distance     – max 30 pts (penalises routes > 1 000 nm linearly)
          Ecology      – max 30 pts (inverse of risk_score/10)

        Hard penalty: routes that approve_route() would auto-reject
        (HIGH risk + direct type) receive -60 pts, ensuring an
        approvable alternative always outscores them when one exists.
        This prevents the system from repeatedly selecting Route Alpha
        only to reject it, which was causing 3 full wasted iterations.
        """
        eta_score  = max(0.0, 40.0 - (route["eta_hours"] / 48.0) * 40.0)
        dist_score = max(0.0, 30.0 - (route["distance_nm"] / 1000.0) * 30.0)
        eco_score  = 30.0 - (risk.get("risk_score", 5) / 10.0) * 30.0

        # Penalise routes that will be hard-rejected by approve_route
        if (
            risk.get("risk_level") == "HIGH"
            and route.get("route_type") == "direct"
        ):
            eco_score -= 60.0

        total = round(eta_score + dist_score + eco_score, 2)
        logger.debug(
            "Score breakdown | route=%s | eta=%.1f dist=%.1f eco=%.1f total=%.1f",
            route.get("route_name"), eta_score, dist_score, eco_score, total,
        )
        return total

    def _rationale(self, selected: Dict, all_options: List[Dict]) -> str:
        route = selected["route"]
        risk = selected["risk"]
        rejected = len(all_options) - 1
        return (
            f"Selected {route['route_name']} (score {selected['composite_score']}/100). "
            f"Distance: {route['distance_nm']} nm, ETA: {route['eta_hours']} h. "
            f"Ecological risk: {risk['risk_level']} "
            f"({risk.get('sighting_count', 0)} cetacean sightings). "
            + (f"Rejected {rejected} lower-scoring alternative(s)." if rejected else "")
        )

    # ------------------------------------------------------------------
    # LLM strategic analysis
    # ------------------------------------------------------------------

    @async_retry(max_attempts=3, base_delay=1.0, exceptions=(Exception,))
    async def make_llm_decision(
        self,
        routes: List[Dict],
        risk_assessments: List[Dict],
    ) -> str:
        """Use LLM to provide strategic analysis and final recommendation."""
        if not self._client:
            return "LLM unavailable — Groq API key not configured."

        if not self._breaker.is_available():
            raise CircuitOpenError("groq_risk_manager circuit is open")

        payload = [
            {
                "route": r["route_name"],
                "distance_nm": r["distance_nm"],
                "eta_hours": r["eta_hours"],
                "speed_knots": r["speed_knots"],
                "risk_level": a.get("risk_level"),
                "sightings": a.get("sighting_count", 0),
            }
            for r, a in zip(routes, risk_assessments)
        ]

        prompt = f"""You are a maritime risk manager balancing commercial logistics and marine conservation.

ROUTE OPTIONS:
{json.dumps(payload, indent=2)}

Analyse trade-offs and recommend the best route (≤120 words) considering:
1. Delivery schedule impact
2. Ecological responsibility  
3. Operational safety
4. Regulatory / reputational risk"""

        t0 = time.monotonic()
        try:
            resp = await self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an expert maritime risk manager "
                            "specialising in sustainable shipping and IMO compliance."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=settings.llm_temperature_risk_manager,
                max_tokens=settings.llm_max_tokens,
            )
            self._breaker.record_success()
            logger.info(
                "LLM decision generated | elapsed=%.2fs", time.monotonic() - t0
            )
            return resp.choices[0].message.content
        except Exception as exc:
            self._breaker.record_failure()
            raise exc

    # ------------------------------------------------------------------
    # Approval gate
    # ------------------------------------------------------------------

    def approve_route(self, route: Dict, risk: Dict) -> bool:
        """
        Hard approval rules:

          1. Direct route through HIGH-risk sector → reject.
             Forces the navigator to propose a detour or speed reduction.

          2. Sighting count > 100 on a DIRECT route → reject.
             For non-direct routes (detour, reduced_speed) this rule is
             removed: in highly active cetacean zones every path has
             500+ sightings, so applying the threshold to all route
             types made the loop always exhaust max_iterations with no
             approvable result.

          3. UNKNOWN risk on direct route → reject (fail-safe).
        """
        risk_level = risk.get("risk_level", "UNKNOWN")
        sightings  = risk.get("sighting_count", 0)
        route_type = route.get("route_type", "")

        # Rule 1 — direct route through HIGH-risk area
        if risk_level == "HIGH" and route_type == "direct":
            logger.warning("REJECTED: direct route through HIGH-risk sector")
            return False

        # Rule 2 — excessive density, but only penalise direct routes
        # (detour/reduced-speed alternatives are doing the right thing)
        if sightings > 100 and route_type == "direct":
            logger.warning(
                "REJECTED: direct route with excessive cetacean density (%d sightings)",
                sightings,
            )
            return False

        # Rule 3 — unknown risk on direct route (fail-safe)
        if risk_level == "UNKNOWN" and route_type == "direct":
            logger.warning("REJECTED: direct route with UNKNOWN risk (fail-safe)")
            return False

        logger.info(
            "APPROVED: %s | risk=%s | sightings=%d",
            route.get("route_name"), risk_level, sightings,
        )
        return True