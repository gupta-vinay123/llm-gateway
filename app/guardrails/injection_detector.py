import re
from dataclasses import dataclass

@dataclass
class InjectionResult:
    is_injection: bool
    matched_pattern: str | None
    confidence: float
    reason: str | None

class InjectionDetector:
    def __init__(self):
        self.patterns = [
            # instruction override attempts
            (r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions?", "instruction_override"),
            (r"disregard\s+(all\s+)?(previous|prior|above)\s+instructions?", "instruction_override"),
            (r"forget\s+(all\s+)?(previous|prior|above)\s+instructions?", "instruction_override"),

            # role hijacking
            (r"you\s+are\s+now\s+a", "role_hijack"),
            (r"act\s+as\s+(a\s+)?(different|new|another)", "role_hijack"),
            (r"pretend\s+(you\s+are|to\s+be)", "role_hijack"),
            (r"roleplay\s+as", "role_hijack"),
            (r"your\s+new\s+(role|persona|identity)\s+is", "role_hijack"),

            # system prompt extraction
            (r"(reveal|show|print|display)\s+(your\s+)?(system\s+prompt|instructions|context)", "prompt_extraction"),
            (r"what\s+(are\s+your|is\s+your)\s+(instructions|system\s+prompt)", "prompt_extraction"),
            (r"repeat\s+(everything|all)\s+(above|before)", "prompt_extraction"),

            # jailbreak attempts
            (r"(do\s+anything\s+now|DAN)", "jailbreak"),
            (r"developer\s+mode", "jailbreak"),
            (r"jailbreak", "jailbreak"),
            (r"bypass\s+(your\s+)?(safety|filter|restriction|guideline)", "jailbreak"),

            # prompt delimiter injection
            (r"```\s*system", "delimiter_injection"),
            (r"<\s*system\s*>", "delimiter_injection"),
            (r"\[INST\]|\[\/INST\]", "delimiter_injection"),
        ]

        self.compiled = [
            (re.compile(p, re.IGNORECASE), label)
            for p, label in self.patterns
        ]

    def detect(self, text: str) -> InjectionResult:
        for pattern, label in self.compiled:
            match = pattern.search(text)
            if match:
                return InjectionResult(
                    is_injection=True,
                    matched_pattern=label,
                    confidence=0.95,
                    reason=f"Prompt injection detected: {label} — matched '{match.group()}'"
                )

        return InjectionResult(
            is_injection=False,
            matched_pattern=None,
            confidence=0.0,
            reason=None
        )

# singleton
injection_detector = InjectionDetector()