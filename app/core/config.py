from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # LLM Providers
    openai_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None

    # Redis
    redis_url: str = "redis://localhost:6379"

    # Semantic Cache
    similarity_threshold: float = 0.85
    cache_ttl: int = 3600

    # Guardrails
    enable_pii_detection: bool = True
    enable_toxicity_check: bool = True
    enable_domain_policy: bool = True

    # App
    app_env: str = "development"
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()