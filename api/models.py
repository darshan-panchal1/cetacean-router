from pydantic import BaseModel, Field
from typing import List, Tuple, Optional, Dict


class Coordinates(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


class RouteRequest(BaseModel):
    start: Coordinates
    end: Coordinates
    max_iterations: Optional[int] = Field(default=3, ge=1, le=5)
    
    class Config:
        json_schema_extra = {
            "example": {
                "start": {"latitude": 34.0, "longitude": -120.0},
                "end": {"latitude": 37.0, "longitude": -122.0},
                "max_iterations": 3
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


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str