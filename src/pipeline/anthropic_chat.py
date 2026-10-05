"""Claude Haiku 4.5 chat client for the verify / group / memo roles.

Implements the chat shape from docs/INTERFACES.md §3 and returns ``context.ChatResult``.

Offline safety: the ``anthropic`` SDK is imported only when a client is constructed, and
``build_anthropic_chat`` returns None when ANTHROPIC_API_KEY is unset, so the offline replay,
export and tests never need the SDK or a key. Live runs need Python >= 3.10 and
``pip install anthropic`` (see configs/README.md).

Retries are owned by the pipeline, not the SDK (``max_retries=0``), so every attempt is
logged in calls.jsonl and counted by the spend ledger.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from .context import ChatResult

DEFAULT_MODEL = "claude-haiku-4-5"
PROVIDER = "anthropic"


def _errors():
    """The shared error types from the labelling contract, with a local fallback."""
    try:
        from labelling.model_client import InvalidModelOutput, ModelClientError, TransientModelError
    except Exception:  # pragma: no cover - only when src/labelling is absent
        class ModelClientError(Exception):
            pass

        class TransientModelError(ModelClientError):
            pass

        class InvalidModelOutput(ModelClientError):
            pass
    return ModelClientError, TransientModelError, InvalidModelOutput


def _strip_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[1] if "\n" in stripped else ""
        if stripped.rstrip().endswith("```"):
            stripped = stripped.rstrip()[:-3]
    return stripped.strip()


class AnthropicChat:
    """``complete(messages, *, max_tokens, temperature=0.0, response_format=None) -> ChatResult``.

    ``messages`` uses the OpenAI-style list the role modules build: an optional leading
    ``{"role": "system"}`` entry becomes the top-level ``system`` prompt; the rest are passed
    through as user/assistant turns. No thinking parameter is sent: Haiku 4.5 runs without
    extended thinking by default, which is the cheapest setting for these bounded tasks.
    """

    provider = PROVIDER

    def __init__(self, model: str = DEFAULT_MODEL, api_key: Optional[str] = None,
                 timeout: float = 60.0, sdk: Any = None):
        if sdk is None:
            import anthropic as sdk  # noqa: PLC0415 - deliberate lazy import (offline safety)
        self._sdk = sdk
        self.model = model
        self._client = sdk.Anthropic(api_key=api_key, timeout=timeout, max_retries=0)

    def complete(self, messages: List[Dict[str, str]], *, max_tokens: int,
                 temperature: float = 0.0, response_format: Optional[str] = None) -> ChatResult:
        ModelClientError, TransientModelError, InvalidModelOutput = _errors()
        sdk = self._sdk
        system_parts = [m["content"] for m in messages if m.get("role") == "system"]
        turns = [{"role": m["role"], "content": m["content"]} for m in messages if m.get("role") != "system"]
        if response_format == "json":
            system_parts.append("Respond with one JSON value only: no prose, no code fences.")
        kwargs: Dict[str, Any] = {"model": self.model, "max_tokens": int(max_tokens),
                                  "temperature": float(temperature), "messages": turns}
        if system_parts:
            kwargs["system"] = "\n\n".join(system_parts)

        try:
            response = self._client.messages.create(**kwargs)
        except sdk.RateLimitError as e:
            err = TransientModelError(f"429 rate limited: {e}")
            err.retry_after = _retry_after(e)
            raise err
        except (sdk.APITimeoutError, sdk.APIConnectionError) as e:
            err = TransientModelError(f"{type(e).__name__}: {e}")
            err.uncertain_charge = isinstance(e, sdk.APITimeoutError)
            raise err
        except sdk.InternalServerError as e:
            raise TransientModelError(f"{getattr(e, 'status_code', '5xx')}: {e}")
        except (sdk.AuthenticationError, sdk.PermissionDeniedError) as e:
            raise ModelClientError(f"auth/permission error, stopping: {e}")
        except sdk.BadRequestError as e:
            message = str(e)
            if "credit" in message.lower() or "billing" in message.lower():
                raise ModelClientError(f"billing error, stopping: {message}")
            raise InvalidModelOutput(f"400: {message}")
        except sdk.APIStatusError as e:
            if getattr(e, "status_code", 0) in (529,) or getattr(e, "status_code", 0) >= 500:
                raise TransientModelError(f"{e.status_code}: {e}")
            raise InvalidModelOutput(f"{getattr(e, 'status_code', '?')}: {e}")

        if response.stop_reason == "max_tokens":
            raise InvalidModelOutput(f"output hit max_tokens={max_tokens} (truncated)")
        if response.stop_reason == "refusal":
            raise InvalidModelOutput("model refused the request")
        text = "".join(block.text for block in response.content if block.type == "text")
        if response_format == "json":
            text = _strip_fences(text)

        usage = response.usage
        cache_read = getattr(usage, "cache_read_input_tokens", None) or 0
        cache_write = getattr(usage, "cache_creation_input_tokens", None) or 0
        return ChatResult(
            text=text,
            request_id=getattr(response, "_request_id", None) or response.id,
            model=response.model,
            # input_tokens is TOTAL input (uncached + cache read + cache write) so the calculator
            # can subtract cached_input_tokens before applying the uncached rate.
            input_tokens=int(usage.input_tokens) + int(cache_read) + int(cache_write),
            output_tokens=int(usage.output_tokens),
            cached_input_tokens=int(cache_read),
            cost_usd=None,  # Anthropic does not return cost per response; cost/ computes it from rates.csv
        )


def _retry_after(error) -> Optional[float]:
    response = getattr(error, "response", None)
    headers = getattr(response, "headers", None) or {}
    try:
        value = headers.get("retry-after")
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def build_anthropic_chat(config: Optional[Dict[str, Any]] = None, sdk: Any = None) -> Optional[AnthropicChat]:
    """Return a live client when ANTHROPIC_API_KEY (or config api_key) is set, else None."""
    config = config or {}
    key = config.get("api_key") or os.environ.get(config.get("api_key_env", "ANTHROPIC_API_KEY"), "")
    if not key:
        return None
    return AnthropicChat(model=config.get("model") or DEFAULT_MODEL, api_key=key,
                         timeout=float(config.get("timeout_seconds", 60)), sdk=sdk)
