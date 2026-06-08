from fastapi import FastAPI
from app.api.routes import router

app = FastAPI(
    title="LLM Gateway",
    description="Semantic caching + guardrails layer for LLM APIs",
    version="1.0.0"
)

app.include_router(router)