from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from api.models import RouteRequest, RouteResponse, HealthResponse
from graph.routing_graph import run_routing_optimization
from config.settings import settings
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


app = FastAPI(
    title="Cetacean-Aware Logistics Router API",
    description="AI-powered maritime routing that balances logistics efficiency with marine conservation",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Mock MCP tool functions for API deployment
# In production, these would connect to running MCP servers
def mock_obis_tool(wkt_geometry: str, taxon: str = "Cetacea") -> dict:
    '''Mock OBIS tool for API testing.'''
    # In production, this would call the actual MCP server
    import random
    sighting_count = random.randint(0, 100)
    
    if sighting_count > 50:
        risk_level = "HIGH"
        risk_score = 8
    elif sighting_count > 10:
        risk_level = "MEDIUM"
        risk_score = 5
    else:
        risk_level = "LOW"
        risk_score = 2
    
    return {
        "success": True,
        "taxon": taxon,
        "sighting_count": sighting_count,
        "risk_level": risk_level,
        "risk_score": risk_score,
        "species_list": ["Balaenoptera musculus", "Megaptera novaeangliae"],
        "data_source": "OBIS"
    }


def mock_route_calc_tool(**kwargs) -> dict:
    '''Mock route calculation tool.'''
    return {"success": True}


@app.get("/", response_model=HealthResponse)
async def health_check():
    '''Health check endpoint.'''
    return HealthResponse(
        status="healthy",
        service="Cetacean-Aware Logistics Router",
        version="1.0.0"
    )


@app.post("/optimize-route", response_model=RouteResponse)
async def optimize_route(request: RouteRequest):
    '''
    Optimize a shipping route considering marine mammal conservation.
    
    This endpoint runs the multi-agent optimization workflow to find
    the best balance between logistics efficiency and ecological safety.
    '''
    try:
        # Convert coordinates to tuples
        start = (request.start.latitude, request.start.longitude)
        end = (request.end.latitude, request.end.longitude)
        
        # Run optimization
        result = run_routing_optimization(
            start=start,
            end=end,
            obis_tool=mock_obis_tool,
            route_calc_tool=mock_route_calc_tool,
            max_iterations=request.max_iterations
        )
        
        # Format response
        return RouteResponse(
            success=True,
            selected_route=result['selected_route'],
            risk_assessment=result['risk_assessments'][-1] if result['risk_assessments'] else {},
            decision_rationale=result['decision_rationale'],
            llm_analysis=result['llm_analysis'],
            approved=result['approved'],
            iterations=result['iteration_count'],
            all_routes_considered=result['proposed_routes']
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Route optimization failed: {str(e)}"
        )


@app.get("/health")
async def detailed_health():
    '''Detailed health check with system status.'''
    return {
        "api": "operational",
        "agents": {
            "navigator": "ready",
            "biologist": "ready",
            "risk_manager": "ready"
        },
        "mcp_servers": {
            "obis": "mock_mode",
            "route_calc": "mock_mode"
        },
        "groq_api": "configured" if settings.groq_api_key else "not_configured"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True
    )