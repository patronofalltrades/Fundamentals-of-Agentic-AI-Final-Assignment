"""OpenAI-compatible chat client for the text-generating roles (verify / group / memo).

OpenCode-owned model plumbing. Default route: **OpenRouter** → `deepseek/deepseek-v4.1-flash`
(`POST https://openrouter.ai/api/v1/chat/completions`, `OPENROUTER_API_KEY`). Alternative:
DeepSeek direct (`deepseek-flash` = V4.1-Flash, `https://api.deepseek.com/chat/completions`,
`DEEPSEEK_API_KEY`). Both speak OpenAI chat-completions; only the base URL, slug, and key change.

This client is deliberately separate from ``model_client.py`` (the Jev decisions client):
enrichment uses typed answers; these roles need text/JSON generation. It reuses the same error
taxonomy so the harness handles retries uniformly.

Usage notes:
- DeepSeek usage.prompt_tokens == prompt_cache_hit_tokens + prompt_cache_miss_tokens; both cache
  fields are captured so the cost calculator can subtract cached input before the uncached rate.
- Output tokens are billed (unlike Jev). Non-thinking mode is the default cheap setting.
- MockChatClient keeps everything offline; no paid call happens at import or in create_*.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from typing import Mapping, Protocol, Sequence

from .model_client import InvalidModelOutput, ModelClientError, TransientModelError

DEEPSEEK_ENDPOINT = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = "deepseek-flash"  # serves DeepSeek-V4.1-Flash; legacy "deepseek-v4-flash" routes here
OPENROUTER_CHAT_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
# OpenRouter slug for DeepSeek V4.1 Flash (released 2026-09-10); routed to DeepSeek providers.
OPENROUTER_MODEL = "deepseek/deepseek-v4.1-flash"
OPENROUTER_FREE_MODEL = "deepseek/deepseek-v4-flash:free"  # $0 older V4 variant, fallback only

# Reference pricing (USD per 1M tokens), DeepSeek direct, checked 2026-10 for planning only —
# the cost/ calculator must use its own dated rates.csv, not these constants.
PRICE_REF = {"input_per_mtok": 0.14, "input_cache_hit_per_mtok": 0.0028, "output_per_mtok": 0.28}


@dataclass(frozen=True)
class ChatMessage:
    role: str  # "system" | "user"
    content: str


@dataclass(frozen=True)
class ChatResult:
    request_id: str
    model: str            # served model id from the provider
    content: str          # assistant text (JSON string when json_mode=True)
    input_tokens: int
    output_tokens: int
    cached_input_tokens: int = 0   # prompt_cache_hit_tokens (DeepSeek); 0 elsewhere
    cost_usd: float | None = None  # provider-reported cost when available (e.g. OpenRouter)


class ChatClient(Protocol):
    def chat(self, messages: Sequence[ChatMessage], *, max_tokens: int = 2048,
             json_mode: bool = False) -> ChatResult:
        ...


class MockChatClient:
    """Deterministic offline chat client: canned content, zero usage. For dry-run/tests.

    Content-aware enough to satisfy the role wrappers offline: in json_mode it scans the
    conversation for review ids and returns structurally valid canned labels/issues.
    """

    def __init__(self, model=DEEPSEEK_MODEL):
        self.model = model

    def chat(self, messages, *, max_tokens=2048, json_mode=False):
        if json_mode:
            content = self._canned_json(messages)
        else:
            content = "mock memo: placeholder recommendation pending real run"
        return ChatResult(
            request_id="mock-" + uuid.uuid4().hex,
            model=self.model,
            content=content,
            input_tokens=0,
            output_tokens=0,
        )

    @staticmethod
    def _canned_json(messages):
        system = next((m.content for m in messages if m.role == "system"), "")
        user = "\n".join(m.content for m in messages if m.role != "system")
        ids = re.findall(r"\[([0-9a-f-]{8,})\]", user) or re.findall(r'"review_id":\s*"([^"]+)"', user)
        if system.startswith("You name recurring complaint issues"):
            issues = [{"issue_id": "mock-issue", "name": "Mock issue", "definition": "offline mock",
                       "member_review_ids": ids}]
            return json.dumps({"issues": issues})
        labels = {rid: {"topic": "other", "intent": "praise", "sentiment": 0.0,
                        "severity": 1, "needs_review": False, "reason": "mock"} for rid in ids}
        return json.dumps(labels)


class DeepSeekClient:
    """Real client for OpenAI-compatible chat completions (DeepSeek direct by default)."""

    def __init__(self, model=DEEPSEEK_MODEL, endpoint=DEEPSEEK_ENDPOINT, api_key=None,
                 timeout=120, temperature=0.0):
        self.model = model
        self.endpoint = endpoint
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")
        self.timeout = timeout
        self.temperature = temperature

    def chat(self, messages, *, max_tokens=2048, json_mode=False):
        if not self.api_key:
            raise InvalidModelOutput("no DEEPSEEK_API_KEY configured for real DeepSeekClient")
        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "max_tokens": max_tokens,
            "temperature": self.temperature,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        request = urllib.request.Request(
            self.endpoint, data=json.dumps(payload).encode("utf-8"), method="POST",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            code = e.code
            detail = e.read().decode("utf-8", "replace")[:300]
            if code in (400, 401, 402, 403, 404, 422):
                raise InvalidModelOutput(f"HTTP {code}: {detail}")
            raise TransientModelError(f"HTTP {code}: {detail}")
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise TransientModelError(str(e))
        except json.JSONDecodeError as e:
            raise InvalidModelOutput(f"non-JSON response: {e}")

        choices = data.get("choices")
        if not choices or not isinstance(choices, list):
            raise InvalidModelOutput("response missing 'choices'")
        message = choices[0].get("message") or {}
        content = message.get("content")
        if not isinstance(content, str) or not content:
            raise InvalidModelOutput("empty assistant content")
        usage = data.get("usage") or {}

        return ChatResult(
            request_id=str(data.get("id") or "req-" + uuid.uuid4().hex),
            model=str(data.get("model") or self.model),
            content=content,
            input_tokens=int(usage.get("prompt_tokens", 0) or 0),
            output_tokens=int(usage.get("completion_tokens", 0) or 0),
            cached_input_tokens=int(usage.get("prompt_cache_hit_tokens", 0) or 0),
            cost_usd=(usage.get("cost") if isinstance(usage.get("cost"), (int, float)) else None),
        )


def create_chat_client(config=None):
    """Factory. Real client when a key is configured; else MockChatClient (offline-safe).

    config keys: provider ("deepseek" default | "openrouter"), model, endpoint, api_key,
    timeout, temperature.
    """
    config = config or {}
    provider = config.get("provider", "openrouter").lower()
    if provider == "openrouter":
        model = config.get("model", OPENROUTER_MODEL)
        endpoint = config.get("endpoint", OPENROUTER_CHAT_ENDPOINT)
        key = config.get("api_key") or os.environ.get("OPENROUTER_API_KEY", "")
    elif provider == "deepseek":
        model = config.get("model", DEEPSEEK_MODEL)
        endpoint = config.get("endpoint", DEEPSEEK_ENDPOINT)
        key = config.get("api_key") or os.environ.get("DEEPSEEK_API_KEY", "")
    else:
        raise InvalidModelOutput(f"unsupported chat provider {provider!r}")
    if not key:
        return MockChatClient(model=model)
    return DeepSeekClient(
        model=model,
        endpoint=endpoint,
        api_key=key,
        timeout=int(config.get("timeout", 120)),
        temperature=float(config.get("temperature", 0.0)),
    )