from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import time

from app.core.metrics import metrics
from app.cache.semantic_cache import semantic_cache
from app.guardrails.pipeline import guardrails_pipeline
from app.providers.factory import get_provider
from app.providers.base import LLMRequest

router = APIRouter()

class ChatRequest(BaseModel):
    message: str
    provider: Optional[str] = "groq"
    system_prompt: Optional[str] = "You are a helpful DSA tutor."
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 1024

class ChatResponse(BaseModel):
    response: str
    cache_hit: bool
    cache_type: Optional[str] = None
    similarity: Optional[float] = None
    provider: Optional[str] = None
    tokens_used: Optional[int] = None
    pii_detected: list = []
    latency_ms: float

@router.post("/v1/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    start = time.time()

    # Step 1 — input guardrails
    guard_result = guardrails_pipeline.run_input(request.message)
    
    if not guard_result.passed:
        metrics.record_request(
            cache_type=None,
            blocked=True,
            block_reason=guard_result.blocked_reason,
            tokens=0,
            latency_ms=round((time.time() - start) * 1000, 2),
            pii_detected=bool(guard_result.pii_detected)
        )
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Request blocked by guardrails",
                "reason": guard_result.blocked_reason
            }
        )

    clean_query = guard_result.scrubbed_text

    # Step 2 — L1 exact cache
    cached = semantic_cache.get_exact(clean_query)
    if cached:
        latency = round((time.time() - start) * 1000, 2)
        metrics.record_request(
            cache_type="exact",
            blocked=False,
            block_reason=None,
            tokens=0,
            latency_ms=latency,
            pii_detected=bool(guard_result.pii_detected)
        )
        return ChatResponse(
            response=cached["response"],
            cache_hit=True,
            cache_type="exact",
            similarity=1.0,
            latency_ms=latency,
            pii_detected=guard_result.pii_detected
        )

    # Step 3 — L2 semantic cache
    cached = semantic_cache.get(clean_query)
    if cached:
        latency = round((time.time() - start) * 1000, 2)
        metrics.record_request(
            cache_type="semantic",
            blocked=False,
            block_reason=None,
            tokens=0,
            latency_ms=latency,
            pii_detected=bool(guard_result.pii_detected)
        )
        return ChatResponse(
            response=cached["response"],
            cache_hit=True,
            cache_type="semantic",
            similarity=cached["similarity"],
            latency_ms=latency,
            pii_detected=guard_result.pii_detected
        )

    # Step 4 — LLM call
    provider = get_provider(request.provider)

    llm_response = await provider.complete(LLMRequest(
        message=clean_query,
        system_prompt=request.system_prompt,
        temperature=request.temperature,
        max_tokens=request.max_tokens
    ))

    # Step 5 — output guardrails
    clean_output, output_pii = guardrails_pipeline.run_output(llm_response.content)

    # Step 6 — store in cache
    semantic_cache.set(clean_query, clean_output)

    latency = round((time.time() - start) * 1000, 2)
    metrics.record_request(
        cache_type=None,
        blocked=False,
        block_reason=None,
        tokens=llm_response.total_tokens,
        latency_ms=latency,
        pii_detected=bool(guard_result.pii_detected + output_pii)
    )
    return ChatResponse(
        response=clean_output,
        cache_hit=False,
        cache_type=None,
        provider=llm_response.provider,
        tokens_used=llm_response.total_tokens,
        latency_ms=latency,
        pii_detected=guard_result.pii_detected + output_pii
    )

@router.get("/health")
def health():
    return {"status": "ok"}

@router.get("/metrics")
def get_metrics():
    return metrics.summary()