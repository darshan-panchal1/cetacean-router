from pydantic import BaseModel, Field
from typing import Dict, List, Optional


class Coordinates(BaseModel):
    latitude: float = Field(..., ge=-90, le=90, description="Latitude in decimal degrees")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude in decimal degrees")


class RouteRequest(BaseModel):
    start: Coordinates
    end: Coordinates
    max_iterations: Optional[int] = Field(default=3, ge=1, le=5)

    model_config = {
        "json_schema_extra": {
            "example": {
                "start": {"latitude": 34.4208, "longitude": -119.6982},
                "end": {"latitude": 45.5152, "longitude": -122.6784},
                "max_iterations": 3,
            }
        }
    }


class RouteResponse(BaseModel):
    success: bool
    selected_route: Dict
    risk_assessment: Dict
    decision_rationale: str
    llm_analysis: str
    approved: bool
    iterations: int
    all_routes_considered: List[Dict]
    elapsed_seconds: Optional[float] = None


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class RouteStatusResponse(BaseModel):
    event: str
    message: Optional[str] = None
    data: Optional[Dict] = None