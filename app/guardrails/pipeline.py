from dataclasses import dataclass
from app.guardrails.pii_detector import pii_detector
from app.guardrails.injection_detector import injection_detector
from app.guardrails.domain_policy import dsa_policy
from app.core.config import settings

@dataclass
class GuardrailResult:
    passed: bool
    scrubbed_text: str
    blocked_reason: str | None
    pii_detected: list
    injection_detected: bool
    domain_allowed: bool

class GuardrailsPipeline:
    def run_input(self, text: str) -> GuardrailResult:
        # Layer 1 — prompt injection (cheapest, no model needed)
        if settings.enable_domain_policy:
            injection_result = injection_detector.detect(text)
            if injection_result.is_injection:
                return GuardrailResult(
                    passed=False,
                    scrubbed_text=text,
                    blocked_reason=injection_result.reason,
                    pii_detected=[],
                    injection_detected=True,
                    domain_allowed=True
                )

        # Layer 2 — PII scrubbing
        scrubbed_text = text
        pii_found = []
        if settings.enable_pii_detection:
            scrubbed_text, pii_found = pii_detector.scrub(text)

        # Layer 3 — domain policy (embedding model)
        domain_allowed = True
        domain_reason = None
        if settings.enable_domain_policy:
            policy_result = dsa_policy.validate(scrubbed_text)
            domain_allowed = policy_result.is_allowed
            if not policy_result.is_allowed:
                domain_reason = policy_result.reason

        if not domain_allowed:
            return GuardrailResult(
                passed=False,
                scrubbed_text=scrubbed_text,
                blocked_reason=domain_reason,
                pii_detected=pii_found,
                injection_detected=False,
                domain_allowed=False
            )

        return GuardrailResult(
            passed=True,
            scrubbed_text=scrubbed_text,
            blocked_reason=None,
            pii_detected=pii_found,
            injection_detected=False,
            domain_allowed=True
        )

    def run_output(self, text: str) -> tuple[str, list]:
        # scrub PII from LLM output before returning to user
        if settings.enable_pii_detection:
            return pii_detector.scrub(text)
        return text, []

# singleton
guardrails_pipeline = GuardrailsPipeline()