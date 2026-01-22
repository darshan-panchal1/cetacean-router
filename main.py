'''
Cetacean-Aware Logistics Router - Main Execution Script

This is the primary entry point for running route optimizations.
'''

import sys
from typing import Tuple
from config.settings import settings
from graph.routing_graph import run_routing_optimization
from mcp_servers.obis_server import check_species_risk
from mcp_servers.route_calc_server import calculate_route_metrics


def mock_obis_wrapper(wkt_geometry: str, taxon: str = "Cetacea") -> dict:
    '''Wrapper for OBIS tool to match expected interface.'''
    return check_species_risk(wkt_geometry, taxon)


def mock_route_calc_wrapper(**kwargs) -> dict:
    '''Wrapper for route calc tool.'''
    if 'waypoints' in kwargs:
        return calculate_route_metrics(**kwargs)
    return {"success": True}


def example_california_to_oregon():
    '''Example: Route from Southern California to Oregon.'''
    print("\\n" + "="*70)
    print("EXAMPLE ROUTE: Southern California to Oregon Coast")
    print("="*70)
    
    # Santa Barbara, CA to Portland, OR (maritime route)
    start = (34.4208, -119.6982)  # Santa Barbara
    end = (45.5152, -122.6784)     # Portland (offshore)
    
    result = run_routing_optimization(
        start=start,
        end=end,
        obis_tool=mock_obis_wrapper,
        route_calc_tool=mock_route_calc_wrapper,
        max_iterations=3
    )
    
    print_results(result)


def example_transatlantic():
    '''Example: Transatlantic route.'''
    print("\\n" + "="*70)
    print("EXAMPLE ROUTE: New York to Portugal")
    print("="*70)
    
    start = (40.7128, -74.0060)   # New York
    end = (38.7223, -9.1393)      # Lisbon
    
    result = run_routing_optimization(
        start=start,
        end=end,
        obis_tool=mock_obis_wrapper,
        route_calc_tool=mock_route_calc_wrapper,
        max_iterations=3
    )
    
    print_results(result)


def example_pacific():
    '''Example: Pacific Ocean route.'''
    print("\\n" + "="*70)
    print("EXAMPLE ROUTE: Los Angeles to Honolulu")
    print("="*70)
    
    start = (33.7701, -118.1937)  # LA Port
    end = (21.3099, -157.8581)     # Honolulu
    
    result = run_routing_optimization(
        start=start,
        end=end,
        obis_tool=mock_obis_wrapper,
        route_calc_tool=mock_route_calc_wrapper,
        max_iterations=3
    )
    
    print_results(result)


def print_results(result: dict):
    '''Print formatted results.'''
    print("\\n" + "="*70)
    print("FINAL ROUTING DECISION")
    print("="*70)
    
    selected = result['selected_route']
    risk = result['risk_assessments'][-1] if result['risk_assessments'] else {}
    
    print(f"\\n✓ Selected Route: {selected['route_name']}")
    print(f"  Distance: {selected['distance_nm']} nautical miles")
    print(f"  ETA: {selected['eta_hours']} hours ({selected['eta_hours']/24:.1f} days)")
    print(f"  Speed: {selected['speed_knots']} knots")
    print(f"  Waypoints: {len(selected['waypoints'])}")
    
    print(f"\\n🐋 Ecological Assessment:")
    print(f"  Risk Level: {risk.get('risk_level', 'N/A')}")
    print(f"  Cetacean Sightings: {risk.get('sighting_count', 0)}")
    print(f"  Species Detected: {len(risk.get('species_list', []))}")
    
    print(f"\\n📊 Decision Metrics:")
    print(f"  Approved: {'✓ Yes' if result['approved'] else '✗ No'}")
    print(f"  Iterations: {result['iteration_count']}")
    print(f"  Routes Evaluated: {len(result['proposed_routes'])}")
    
    print(f"\\n💡 Rationale:")
    print(f"  {result['decision_rationale']}")
    
    if result['llm_analysis']:
        print(f"\\n🤖 AI Analysis:")
        print(f"  {result['llm_analysis']}")
    
    print("\\n" + "="*70)


def custom_route():
    '''Run a custom route with user input.'''
    print("\\n" + "="*70)
    print("CUSTOM ROUTE PLANNER")
    print("="*70)
    
    try:
        print("\\nEnter starting coordinates:")
        start_lat = float(input("  Latitude (-90 to 90): "))
        start_lon = float(input("  Longitude (-180 to 180): "))
        
        print("\\nEnter ending coordinates:")
        end_lat = float(input("  Latitude (-90 to 90): "))
        end_lon = float(input("  Longitude (-180 to 180): "))
        
        start = (start_lat, start_lon)
        end = (end_lat, end_lon)
        
        result = run_routing_optimization(
            start=start,
            end=end,
            obis_tool=mock_obis_wrapper,
            route_calc_tool=mock_route_calc_wrapper,
            max_iterations=3
        )
        
        print_results(result)
        
    except ValueError as e:
        print(f"\\n❌ Error: Invalid input - {e}")
    except Exception as e:
        print(f"\\n❌ Error: {e}")


def main():
    '''Main entry point.'''
    print("\\n" + "="*70)
    print("CETACEAN-AWARE LOGISTICS ROUTER")
    print("Balancing Shipping Efficiency with Marine Conservation")
    print("="*70)
    
    if not settings.groq_api_key or settings.groq_api_key == "your_groq_api_key_here":
        print("\\n⚠️  WARNING: Groq API key not configured!")
        print("Please set GROQ_API_KEY in your .env file")
        print("\\nContinuing with limited functionality...\\n")
    
    print("\\nSelect an option:")
    print("1. California to Oregon (Blue Whale Migration Route)")
    print("2. Transatlantic Route (New York to Portugal)")
    print("3. Pacific Route (Los Angeles to Honolulu)")
    print("4. Custom Route")
    print("5. Run All Examples")
    print("6. Start API Server")
    print("0. Exit")
    
    choice = input("\\nEnter choice (0-6): ").strip()
    
    if choice == "1":
        example_california_to_oregon()
    elif choice == "2":
        example_transatlantic()
    elif choice == "3":
        example_pacific()
    elif choice == "4":
        custom_route()
    elif choice == "5":
        example_california_to_oregon()
        example_transatlantic()
        example_pacific()
    elif choice == "6":
        print("\\nStarting API server...")
        from api.main import app
        import uvicorn
        uvicorn.run(
            app,
            host=settings.api_host,
            port=settings.api_port
        )
    elif choice == "0":
        print("\\nExiting...")
        sys.exit(0)
    else:
        print("\\n❌ Invalid choice")
        main()


if __name__ == "__main__":
    main()