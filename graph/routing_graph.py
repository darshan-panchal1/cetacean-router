"""
Async LangGraph workflow for cetacean-aware route optimisation.

State uses operator.add for list fields so that route/risk entries
accumulate correctly across iterations.  The risk_manager node pairs
only the routes proposed in the *current* iteration with their
corresponding risk assessments — not the full accumulated history —
to avoid misaligned scoring.
"""

import asyncio
import logging
import operator
from typing import Annotated, Callable, Dict, List, Optional, Tuple, TypedDict

from langgraph.graph import StateGraph, END

from agents.navigator import NavigatorAgent
from agents.biologist import BiologistAgent
from agents.risk_manager import RiskManagerAgent

logger = logging.getLogger("graph.routing")


# ---------------------------------------------------------------------------
# Shared state definition
# ---------------------------------------------------------------------------

class RoutingState(TypedDict):
    # Input
    start_point: Tuple[float, float]
    end_point: Tuple[float, float]

    # Navigator outputs — accumulated across iterations
    proposed_routes: Annotated[List[Dict], operator.add]

    # Biologist outputs — accumulated across iterations
    risk_assessments: Annotated[List[Dict], operator.add]
    critical_sectors: List[Dict]

    # Risk Manager outputs
    selected_route: Dict
    decision_rationale: str
    llm_analysis: str
    approved: bool

    # Iteration control
    iteration_count: int
    max_iterations: int

    # MCP tool references (injected at runtime)
    obis_tool: Callable
    route_calc_tool: Callable

    # Track how many routes were added in this iteration
    # (used to slice the correct tail from accumulated lists)
    routes_this_iteration: int


# ---------------------------------------------------------------------------
# Node implementations
# ---------------------------------------------------------------------------

def _create_nodes(
    navigator: NavigatorAgent,
    biologist: BiologistAgent,
    risk_manager: RiskManagerAgent,
):
    async def navigator_node(state: RoutingState) -> Dict:
        """Propose route options for the current iteration."""
        logger.info("[Navigator] iteration=%d", state["iteration_count"])

        start = state["start_point"]
        end = state["end_point"]

        direct = navigator.calculate_direct_route(start, end)

        if state["iteration_count"] == 0 or not state.get("critical_sectors"):
            routes = [direct]
        else:
            avoid = state["critical_sectors"][0]
            detour = navigator.calculate_detour_route(start, end, avoid)
            slow = navigator.calculate_slow_route(start, end, avoid)
            routes = [direct, detour, slow]

        try:
            reasoning = await navigator.reason_about_routes(routes)
        except Exception as exc:
            reasoning = f"Reasoning unavailable: {exc}"
            logger.warning("Navigator LLM error: %s", exc)

        logger.info("[Navigator] reasoning: %s", reasoning[:120])

        return {
            "proposed_routes": routes,
            "routes_this_iteration": len(routes),
        }

    async def biologist_node(state: RoutingState) -> Dict:
        """Assess risk for the routes proposed in this iteration."""
        logger.info("[Biologist] assessing %d routes", state["routes_this_iteration"])

        # Only assess routes from the current iteration
        n = state["routes_this_iteration"]
        current_routes = state["proposed_routes"][-n:]

        tasks = [
            biologist.assess_route_risk(r["waypoints"], state["obis_tool"])
            for r in current_routes
        ]
        risk_assessments = await asyncio.gather(*tasks)

        for route, risk in zip(current_routes, risk_assessments):
            logger.info(
                "[Biologist] %s → %s (%d sightings)",
                route["route_name"], risk["risk_level"], risk["sighting_count"],
            )

        # Find critical sectors from the highest-risk route
        all_sectors: List[Dict] = []
        for route, risk in zip(current_routes, risk_assessments):
            if risk["risk_level"] in ("HIGH", "MEDIUM"):
                sectors = await biologist.identify_critical_sectors(
                    route["waypoints"], state["obis_tool"]
                )
                all_sectors.extend(sectors)

        return {
            "risk_assessments": list(risk_assessments),
            "critical_sectors": all_sectors,
        }

    async def risk_manager_node(state: RoutingState) -> Dict:
        """Select the best route from this iteration's candidates."""
        logger.info("[RiskManager] evaluating options")

        n = state["routes_this_iteration"]
        current_routes = state["proposed_routes"][-n:]
        current_risks = state["risk_assessments"][-n:]

        decision = risk_manager.evaluate_route_options(current_routes, current_risks)

        try:
            llm_analysis = await risk_manager.make_llm_decision(
                current_routes, current_risks
            )
        except Exception as exc:
            llm_analysis = f"LLM analysis unavailable: {exc}"
            logger.warning("RiskManager LLM error: %s", exc)

        approved = risk_manager.approve_route(
            decision["selected_route"], decision["risk_assessment"]
        )

        logger.info(
            "[RiskManager] selected=%s | score=%.1f | approved=%s",
            decision["selected_route"]["route_name"],
            decision["composite_score"],
            approved,
        )

        return {
            "selected_route": decision["selected_route"],
            "decision_rationale": decision["decision_rationale"],
            "llm_analysis": llm_analysis,
            "approved": approved,
            "iteration_count": state["iteration_count"] + 1,
        }

    def should_continue(state: RoutingState) -> str:
        if state["approved"]:
            return "end"
        if state["iteration_count"] >= state["max_iterations"]:
            logger.warning("[System] max iterations reached — using best available route")
            return "end"
        if state.get("critical_sectors"):
            logger.info("[System] iterating with alternative routes")
            return "continue"
        return "end"

    return navigator_node, biologist_node, risk_manager_node, should_continue


# ---------------------------------------------------------------------------
# Module-level singletons
# Built ONCE on cold start — reused on every warm invocation.
# This eliminates per-call agent instantiation and graph compilation
# overhead, which was the primary cause of slowness on RunPod serverless.
# ---------------------------------------------------------------------------

_navigator    = NavigatorAgent()
_biologist    = BiologistAgent()
_risk_manager = RiskManagerAgent()

_nav_node, _bio_node, _rm_node, _should_continue = _create_nodes(
    _navigator, _biologist, _risk_manager
)


def _build_graph():
    workflow = StateGraph(RoutingState)
    workflow.add_node("navigator", _nav_node)
    workflow.add_node("biologist", _bio_node)
    workflow.add_node("risk_manager", _rm_node)
    workflow.set_entry_point("navigator")
    workflow.add_edge("navigator", "biologist")
    workflow.add_edge("biologist", "risk_manager")
    workflow.add_conditional_edges(
        "risk_manager",
        _should_continue,
        {"continue": "navigator", "end": END},
    )
    return workflow.compile()


_compiled_graph = _build_graph()   # compiled once at import time


# ---------------------------------------------------------------------------
# Graph factory  (kept for API compatibility with api/main.py)
# ---------------------------------------------------------------------------

def create_routing_graph(obis_tool: Callable, route_calc_tool: Callable):
    """
    Returns the pre-compiled graph singleton.
    obis_tool / route_calc_tool are kept as params for API compatibility
    but are injected via RoutingState at runtime — no recompilation needed.
    """
    return _compiled_graph


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def run_routing_optimization(
    start: Tuple[float, float],
    end: Tuple[float, float],
    obis_tool: Callable,
    route_calc_tool: Callable,
    max_iterations: int = 3,
) -> Dict:
    """
    Run the complete async routing optimisation workflow.

    Args:
        start: Starting coordinates (lat, lon)
        end:   Ending coordinates (lat, lon)
        obis_tool: OBIS MCP tool callable (sync or async)
        route_calc_tool: Route calculation MCP tool callable
        max_iterations: Maximum optimisation iterations

    Returns:
        Final RoutingState dict
    """
    logger.info(
        "Starting optimisation | start=%s | end=%s | max_iter=%d",
        start, end, max_iterations,
    )

    initial_state: RoutingState = {
        "start_point": start,
        "end_point": end,
        "proposed_routes": [],
        "risk_assessments": [],
        "critical_sectors": [],
        "selected_route": {},
        "decision_rationale": "",
        "llm_analysis": "",
        "approved": False,
        "iteration_count": 0,
        "max_iterations": max_iterations,
        "obis_tool": obis_tool,
        "route_calc_tool": route_calc_tool,
        "routes_this_iteration": 0,
    }

    # Use the pre-compiled singleton — no rebuild cost per call
    final_state = await _compiled_graph.ainvoke(initial_state)

    logger.info(
        "Optimisation complete | selected=%s | approved=%s | iterations=%d",
        final_state.get("selected_route", {}).get("route_name"),
        final_state.get("approved"),
        final_state.get("iteration_count"),
    )

    return final_state