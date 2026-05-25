"""
LLM provider abstraction — with prompt caching and async support.

Key design points:
  • generate() takes structured system blocks (list of {type, text, cache_control})
    rather than a flat string. This lets us mark blocks as cacheable.
  • generate_many() runs multiple user prompts against the SAME system blocks
    in parallel — every call after the first is a CACHE HIT.
  • The Anthropic implementation reports cache stats so we can verify savings.
"""

from __future__ import annotations
import os
import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LLMConfig:
    """Generation parameters."""
    model: str = "claude-sonnet-4-6"
    max_tokens: int = 1600
    temperature: float = 0.55


@dataclass
class LLMResult:
    """Single completion + token usage telemetry."""
    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0   # tokens written to cache (1.25x cost)
    cache_read_tokens: int = 0       # tokens read from cache (0.10x cost)

    @property
    def cache_hit(self) -> bool:
        return self.cache_read_tokens > 0


class LLMProvider(ABC):
    """Minimal interface every backend must implement."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def generate(self,
                 system_blocks: list[dict],
                 user_prompt: str,
                 config: LLMConfig) -> LLMResult:
        """Single synchronous call."""

    @abstractmethod
    async def generate_async(self,
                             system_blocks: list[dict],
                             user_prompt: str,
                             config: LLMConfig) -> LLMResult:
        """Async equivalent of generate()."""

    async def generate_many(self,
                            system_blocks: list[dict],
                            user_prompts: list[str],
                            config: LLMConfig) -> list[LLMResult]:
        """
        Run N user prompts in parallel against the SAME system_blocks.
        Default implementation uses asyncio.gather — subclasses may override.
        """
        tasks = [self.generate_async(system_blocks, p, config) for p in user_prompts]
        return await asyncio.gather(*tasks)


# ---------------------------------------------------------------------------
# Anthropic implementation (sync + async)
# ---------------------------------------------------------------------------

class AnthropicProvider(LLMProvider):
    """
    Real Anthropic backend. Requires ANTHROPIC_API_KEY.
    Supports prompt caching via cache_control in system blocks.
    """

    def __init__(self, api_key: Optional[str] = None):
        try:
            import anthropic
        except ImportError as e:
            raise ImportError(
                "Install the Anthropic SDK first: pip install anthropic"
            ) from e
        self._anthropic = anthropic
        key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self._sync = anthropic.Anthropic(api_key=key)
        self._async = anthropic.AsyncAnthropic(api_key=key)

    @property
    def name(self) -> str:
        return "anthropic"

    @staticmethod
    def _build_result(msg) -> LLMResult:
        parts = []
        for block in msg.content:
            if getattr(block, "type", None) == "text":
                parts.append(block.text)
        usage = getattr(msg, "usage", None)
        return LLMResult(
            text="\n".join(parts).strip(),
            input_tokens=getattr(usage, "input_tokens", 0) if usage else 0,
            output_tokens=getattr(usage, "output_tokens", 0) if usage else 0,
            cache_creation_tokens=getattr(usage, "cache_creation_input_tokens", 0) if usage else 0,
            cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0) if usage else 0,
        )

    # Per-call timeout in seconds. The Anthropic SDK defaults to 600s
    # (10 minutes) which is far too long — a stuck section call would
    # tie up resources and continue burning tokens until the SDK gave
    # up. 90s is comfortable for our largest section size on Sonnet
    # 4.6 (~2400 output tokens, normally <60s) while ensuring failed
    # calls surface promptly.
    _CALL_TIMEOUT_SECONDS = 90

    def generate(self, system_blocks, user_prompt, config):
        msg = self._sync.with_options(
            timeout=self._CALL_TIMEOUT_SECONDS,
        ).messages.create(
            model=config.model,
            max_tokens=config.max_tokens,
            temperature=config.temperature,
            system=system_blocks,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return self._build_result(msg)

    async def generate_async(self, system_blocks, user_prompt, config):
        msg = await self._async.with_options(
            timeout=self._CALL_TIMEOUT_SECONDS,
        ).messages.create(
            model=config.model,
            max_tokens=config.max_tokens,
            temperature=config.temperature,
            system=system_blocks,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return self._build_result(msg)


# ---------------------------------------------------------------------------
# Echo provider — for offline tests
# ---------------------------------------------------------------------------

class EchoProvider(LLMProvider):
    """Returns a deterministic stub without making any API call."""

    @property
    def name(self) -> str:
        return "echo"

    def generate(self, system_blocks, user_prompt, config):
        sys_len = sum(len(b.get("text", "")) for b in system_blocks)
        return LLMResult(
            text=f"[EchoProvider — no LLM call]\n"
                 f"System: {sys_len} chars across {len(system_blocks)} blocks\n"
                 f"User:   {len(user_prompt)} chars\n",
        )

    async def generate_async(self, system_blocks, user_prompt, config):
        return self.generate(system_blocks, user_prompt, config)


# ---------------------------------------------------------------------------
# Ollama provider — fully offline local LLM
# ---------------------------------------------------------------------------

class OllamaProvider(LLMProvider):
    """
    Talks to a local Ollama server (default http://localhost:11434).
    Zero internet required — Ollama runs the model on your CPU/GPU.

    To use:
        1. Install Ollama from https://ollama.com (one-time, ~50MB)
        2. Pull a model:  `ollama pull llama3.1:8b`  (one-time, a few GB)
        3. Set env var ROOM48_USE_OLLAMA=1, or pass explicitly:
               provider = OllamaProvider(model="llama3.1:8b")

    Notes:
      - Ollama has no formal "prompt caching" pricing — it runs on your
        hardware. The cache_control flags in our system_blocks are
        silently ignored.
      - Default model is llama3.1:8b. For better quality, use
        llama3.1:70b (needs ~40GB RAM) or qwen2.5:14b.
    """

    DEFAULT_URL = "http://localhost:11434"
    DEFAULT_MODEL = "llama3.1:8b"

    def __init__(self,
                 base_url: Optional[str] = None,
                 model: Optional[str] = None,
                 timeout: int = 300):
        self.base_url = (base_url or os.getenv("OLLAMA_HOST")
                         or self.DEFAULT_URL).rstrip("/")
        self.model = model or os.getenv("OLLAMA_MODEL") or self.DEFAULT_MODEL
        self.timeout = timeout

    @property
    def name(self) -> str:
        return f"ollama:{self.model}"

    @staticmethod
    def _blocks_to_system_text(system_blocks: list[dict]) -> str:
        """Flatten cacheable blocks into a single system string for Ollama."""
        return "\n\n".join(b.get("text", "") for b in system_blocks)

    def _call(self, system_text: str, user_prompt: str,
              config: LLMConfig) -> str:
        """Synchronous HTTP call to Ollama /api/chat."""
        import urllib.request
        import urllib.error
        import json as _json

        payload = {
            "model": config.model if config.model.startswith("llama") or ":" in config.model
                     else self.model,
            "messages": [
                {"role": "system", "content": system_text},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "options": {
                "temperature": config.temperature,
                "num_predict": config.max_tokens,
            },
        }
        data = _json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                body = _json.loads(r.read())
        except urllib.error.URLError as e:
            raise RuntimeError(
                f"Could not reach Ollama at {self.base_url}. "
                f"Is `ollama serve` running? Original error: {e}"
            )
        return body.get("message", {}).get("content", "").strip()

    def generate(self, system_blocks, user_prompt, config):
        system_text = self._blocks_to_system_text(system_blocks)
        text = self._call(system_text, user_prompt, config)
        # Token usage isn't measured here — Ollama bills nothing, so we
        # leave the counts at zero. This keeps the telemetry interface
        # consistent without misleading "free" numbers.
        return LLMResult(text=text)

    async def generate_async(self, system_blocks, user_prompt, config):
        # Use a thread pool so we don't block the event loop on urllib
        return await asyncio.to_thread(
            self.generate, system_blocks, user_prompt, config
        )

    def health_check(self) -> bool:
        """Return True if the Ollama server is reachable."""
        import urllib.request
        import urllib.error
        try:
            with urllib.request.urlopen(
                    f"{self.base_url}/api/tags", timeout=2) as r:
                return r.status == 200
        except (urllib.error.URLError, Exception):
            return False


# ---------------------------------------------------------------------------
# Default provider selection
# ---------------------------------------------------------------------------

def default_provider() -> LLMProvider:
    """
    Pick a provider based on environment:
      1. If ROOM48_USE_OLLAMA=1 OR Ollama is detected → OllamaProvider
      2. Else if ANTHROPIC_API_KEY is set → AnthropicProvider
      3. Else → EchoProvider (no-op, for tests)
    """
    use_ollama = os.getenv("ROOM48_USE_OLLAMA", "").lower() in ("1", "true", "yes")
    if use_ollama:
        return OllamaProvider()
    # Auto-detect Ollama only if no Anthropic key is set (preserve cloud default)
    if not os.getenv("ANTHROPIC_API_KEY"):
        candidate = OllamaProvider()
        if candidate.health_check():
            return candidate
    if os.getenv("ANTHROPIC_API_KEY"):
        return AnthropicProvider()
    return EchoProvider()
