from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # API Keys
    groq_api_key: str
    
    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    
    # MCP Server Ports
    obis_server_port: int = 8001
    route_calc_server_port: int = 8002
    
    # Agent Models
    navigator_model: str = "mixtral-8x7b-32768"
    biologist_model: str = "mixtral-8x7b-32768"
    risk_manager_model: str = "llama3-70b-8192"
    
    # Routing Parameters
    default_ship_speed_knots: float = 18.0
    reduced_speed_knots: float = 10.0
    risk_threshold_high: int = 50
    risk_threshold_medium: int = 10
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()