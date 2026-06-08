from app.providers.base import BaseLLMProvider
from app.providers.groq_provider import GroqProvider

_providers: dict[str, BaseLLMProvider] = {}

def get_provider(name: str = "groq") -> BaseLLMProvider:
    if name not in _providers:
        if name == "groq":
            _providers[name] = GroqProvider()
        else:
            raise ValueError(f"Unknown provider: {name}")
    return _providers[name]