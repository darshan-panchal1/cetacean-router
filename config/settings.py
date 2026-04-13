from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import Optional
import logging


class Settings(BaseSettings):
    # API Keys
    groq_api_key: Optional[str] = None

    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_level: str = "INFO"

    # MCP Server Ports
    obis_server_port: int = 8001
    route_calc_server_port: int = 8002

    # Agent Models
    navigator_model: str = "llama-3.3-70b-versatile"
    biologist_model: str = "llama-3.3-70b-versatile"
    risk_manager_model: str = "llama-3.3-70b-versatile"

    # Routing Parameters
    default_ship_speed_knots: float = 18.0
    reduced_speed_knots: float = 10.0
    risk_threshold_high: int = 50
    risk_threshold_medium: int = 10

    # OBIS caching
    obis_cache_ttl_seconds: int = 3600        # 1 hour
    obis_request_timeout_seconds: int = 30
    obis_max_retries: int = 3
    obis_results_size: int = 500

    # Circuit breaker
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_timeout: int = 60

    # Rate limiting
    api_rate_limit_per_minute: int = 30

    # Groq LLM
    llm_temperature_navigator: float = 0.3
    llm_temperature_biologist: float = 0.4
    llm_temperature_risk_manager: float = 0.5
    llm_max_tokens: int = 300

    @field_validator("groq_api_key")
    @classmethod
    def warn_missing_key(cls, v: Optional[str]) -> Optional[str]:
        if not v:
            logging.getLogger("Settings").warning(
                "GROQ_API_KEY not set — LLM reasoning will be unavailable"
            )
        return v

    @property
    def groq_configured(self) -> bool:
        return bool(self.groq_api_key)

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()