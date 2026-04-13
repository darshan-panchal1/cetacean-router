"""
Cetacean-Aware Logistics Router — async CLI entry point.
"""

import asyncio
import logging
import sys
from typing import Tuple

from config.settings import settings
from graph.routing_graph import run_routing_optimization
from mcp_servers.obis_server import check_species_risk
from mcp_servers.route_calc_server import calculate_route_metrics

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("main")


# ---------------------------------------------------------------------------
# MCP tool wrappers
# ---------------------------------------------------------------------------

async def obis_tool(wkt_geometry: str, taxon: str = "Cetacea") -> dict:
    return await asyncio.to_thread(check_species_risk, wkt_geometry, taxon)


async def route_calc_tool(**kwargs) -> dict:
    if "waypoints" in kwargs:
        return await asyncio.to_thread(calculate_route_metrics, **kwargs)
    return {"success": True}


# ---------------------------------------------------------------------------
# Pre-defined routes
# ---------------------------------------------------------------------------

EXAMPLE_ROUTES = {
    "1": ("California → Oregon (Blue Whale Migration)", (34.4208, -119.6982), (45.5152, -122.6784)),
    "2": ("Transatlantic: New York → Lisbon",           (40.7128, -74.0060),  (38.7223, -9.1393)),
    "3": ("Pacific: Los Angeles → Honolulu",            (33.7701, -118.1937), (21.3099, -157.8581)),
    "4": ("North Atlantic: Halifax → Southampton",      (44.6488, -63.5752),  (50.9097, -1.4044)),
}


# ---------------------------------------------------------------------------
# Output formatter
# ---------------------------------------------------------------------------

def print_results(result: dict) -> None:
    selected = result.get("selected_route", {})
    risk = result.get("risk_assessments", [{}])[-1]

    print("\n" + "=" * 68)
    print("FINAL ROUTING DECISION")
    print("=" * 68)

    print(f"\n  Selected Route : {selected.get('route_name', 'N/A')}")
    print(f"  Distance       : {selected.get('distance_nm', '—')} nm")
    eta = selected.get("eta_hours", 0)
    print(f"  ETA            : {eta} h ({eta/24:.1f} days)")
    print(f"  Speed          : {selected.get('speed_knots', '—')} kn")
    print(f"  Waypoints      : {len(selected.get('waypoints', []))}")

    print(f"\n  Risk Level     : {risk.get('risk_level', '—')}")
    print(f"  Sightings      : {risk.get('sighting_count', 0)}")
    species = risk.get("species_list", [])
    if species:
        print(f"  Species        : {', '.join(species[:3])}")

    print(f"\n  Approved       : {'Yes' if result.get('approved') else 'No'}")
    print(f"  Iterations     : {result.get('iteration_count', 0)}")
    print(f"  Routes eval.   : {len(result.get('proposed_routes', []))}")

    rationale = result.get("decision_rationale", "")
    if rationale:
        # Wrap at ~65 chars
        words = rationale.split()
        lines, line = [], []
        for w in words:
            line.append(w)
            if len(" ".join(line)) > 62:
                lines.append("  " + " ".join(line))
                line = []
        if line:
            lines.append("  " + " ".join(line))
        print("\n  Rationale:")
        print("\n".join(lines))

    analysis = result.get("llm_analysis", "")
    if analysis and "unavailable" not in analysis.lower():
        print("\n  AI Analysis:")
        words = analysis.split()
        lines, line = [], []
        for w in words:
            line.append(w)
            if len(" ".join(line)) > 62:
                lines.append("  " + " ".join(line))
                line = []
        if line:
            lines.append("  " + " ".join(line))
        print("\n".join(lines))

    print("\n" + "=" * 68 + "\n")


# ---------------------------------------------------------------------------
# Runners
# ---------------------------------------------------------------------------

async def run_example(label: str, start: Tuple, end: Tuple) -> None:
    print(f"\n{'='*68}")
    print(f"  {label}")
    print(f"  {start}  →  {end}")
    print("=" * 68)
    result = await run_routing_optimization(
        start=start,
        end=end,
        obis_tool=obis_tool,
        route_calc_tool=route_calc_tool,
        max_iterations=3,
    )
    print_results(result)


async def run_custom() -> None:
    print("\n" + "=" * 68)
    print("  CUSTOM ROUTE")
    print("=" * 68)
    try:
        print("\nOrigin:")
        start_lat = float(input("  Latitude  (-90 to 90)  : "))
        start_lon = float(input("  Longitude (-180 to 180): "))
        print("\nDestination:")
        end_lat = float(input("  Latitude  (-90 to 90)  : "))
        end_lon = float(input("  Longitude (-180 to 180): "))
    except ValueError:
        print("\n  Invalid input — please enter numeric values.")
        return

    result = await run_routing_optimization(
        start=(start_lat, start_lon),
        end=(end_lat, end_lon),
        obis_tool=obis_tool,
        route_calc_tool=route_calc_tool,
        max_iterations=3,
    )
    print_results(result)


async def start_api() -> None:
    import uvicorn
    from api.main import app

    logger.info("Starting API server on %s:%d", settings.api_host, settings.api_port)
    config = uvicorn.Config(
        app,
        host=settings.api_host,
        port=settings.api_port,
        log_level=settings.log_level.lower(),
    )
    server = uvicorn.Server(config)
    await server.serve()


# ---------------------------------------------------------------------------
# Menu
# ---------------------------------------------------------------------------

async def main() -> None:
    print("\n" + "=" * 68)
    print("  CETACEAN-AWARE LOGISTICS ROUTER  v2.0")
    print("  Balancing shipping efficiency with marine conservation")
    print("=" * 68)

    if not settings.groq_configured:
        print("\n  WARNING: GROQ_API_KEY not set.")
        print("  LLM reasoning will be skipped; routing still works.\n")

    print("\n  Select an option:\n")
    for key, (label, *_) in EXAMPLE_ROUTES.items():
        print(f"  {key}.  {label}")
    print("  5.  Custom route")
    print("  6.  Run all examples")
    print("  7.  Start API server")
    print("  0.  Exit\n")

    choice = input("  Choice: ").strip()

    if choice in EXAMPLE_ROUTES:
        label, start, end = EXAMPLE_ROUTES[choice]
        await run_example(label, start, end)
    elif choice == "5":
        await run_custom()
    elif choice == "6":
        for label, start, end in EXAMPLE_ROUTES.values():
            await run_example(label, start, end)
    elif choice == "7":
        await start_api()
    elif choice == "0":
        print("\n  Goodbye.\n")
        sys.exit(0)
    else:
        print("\n  Invalid choice.")
        await main()


if __name__ == "__main__":
    asyncio.run(main())