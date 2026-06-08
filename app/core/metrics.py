import time
from dataclasses import dataclass, field
from typing import List

@dataclass
class MetricsStore:
    total_requests: int = 0
    cache_hits_exact: int = 0
    cache_hits_semantic: int = 0
    cache_misses: int = 0
    blocked_injection: int = 0
    blocked_domain: int = 0
    blocked_pii_scrubbed: int = 0
    total_tokens_used: int = 0
    latencies_ms: List[float] = field(default_factory=list)

    def record_request(
        self,
        cache_type: str | None,
        blocked: bool,
        block_reason: str | None,
        tokens: int,
        latency_ms: float,
        pii_detected: bool
    ):
        self.total_requests += 1
        self.latencies_ms.append(latency_ms)

        if blocked:
            if block_reason and "injection" in block_reason.lower():
                self.blocked_injection += 1
            else:
                self.blocked_domain += 1
            return

        if pii_detected:
            self.blocked_pii_scrubbed += 1

        if cache_type == "exact":
            self.cache_hits_exact += 1
        elif cache_type == "semantic":
            self.cache_hits_semantic += 1
        else:
            self.cache_misses += 1
            self.total_tokens_used += tokens or 0

    @property
    def cache_hit_rate(self) -> float:
        total_cacheable = self.cache_hits_exact + self.cache_hits_semantic + self.cache_misses
        if total_cacheable == 0:
            return 0.0
        return round((self.cache_hits_exact + self.cache_hits_semantic) / total_cacheable * 100, 2)

    @property
    def avg_latency_ms(self) -> float:
        if not self.latencies_ms:
            return 0.0
        return round(sum(self.latencies_ms) / len(self.latencies_ms), 2)

    def summary(self) -> dict:
        return {
            "total_requests": self.total_requests,
            "cache_hit_rate_percent": self.cache_hit_rate,
            "cache_hits": {
                "exact": self.cache_hits_exact,
                "semantic": self.cache_hits_semantic,
            },
            "cache_misses": self.cache_misses,
            "blocked": {
                "injection_attempts": self.blocked_injection,
                "off_topic": self.blocked_domain,
                "pii_scrubbed": self.blocked_pii_scrubbed,
            },
            "tokens_used": self.total_tokens_used,
            "avg_latency_ms": self.avg_latency_ms,
        }

# singleton
metrics = MetricsStore()