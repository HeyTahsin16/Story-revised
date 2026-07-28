"""
Abstract interface every AI provider implements. services/ai_service.py
(all the prompt content: episode generation, validation, DM classification)
talks only to this interface, so adding a new provider never requires
touching any of that higher-level logic -- just a new file in this package
plus one line in ai_providers/__init__.py's factory.
"""
from abc import ABC, abstractmethod


class AIProvider(ABC):
    @abstractmethod
    async def complete(self, system: str, user: str, max_tokens: int) -> str:
        """Return the model's plain-text response to a single system+user turn."""
        raise NotImplementedError
