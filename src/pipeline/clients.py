"""Build the enrichment and chat clients from a run config, with the mock guard.

Mock guard (docs/INTERFACES.md §2): ``labelling.model_client.create_client`` silently returns a
``MockClient`` when no API key is set. Here a mock is only allowed with ``--dry-run``; a dry run
*always* uses the offline mock (never a real provider), and its ``label_config`` is prefixed
``mock:`` with model ``mock`` so mock output can never be mistaken for real labels.
"""
from __future__ import annotations

import hashlib
import json
import os
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple

from .context import ChatResult

MOCK_PREFIX = "mock:"
MOCK_MODEL = "mock"


class ClientConfigError(RuntimeError):
    """Configuration problem detected before any work (exit nonzero, clear message)."""


class MockGuardError(ClientConfigError):
    """A mock client would be used outside --dry-run."""


def base_label_config(config: Dict[str, Any]) -> str:
    lc = config.get("label_config")
    if not isinstance(lc, str) or not lc.strip():
        raise ClientConfigError("config.label_config must be a nonempty string")
    return lc


def resolve_label_config(config: Dict[str, Any], dry_run: bool) -> str:
    lc = base_label_config(config)
    if dry_run:
        return lc if lc.startswith(MOCK_PREFIX) else MOCK_PREFIX + lc
    if lc.startswith(MOCK_PREFIX):
        raise MockGuardError("label_config %r is a mock config; real runs need a real label_config" % lc)
    return lc


def _client_kwargs(block: Dict[str, Any]) -> Dict[str, Any]:
    """Translate our config block into the keys OpenCode's factories read."""
    cfg = {k: v for k, v in block.items() if k not in ("api_key_env", "timeout_seconds")}
    if "timeout_seconds" in block and "timeout" not in cfg:
        cfg["timeout"] = block["timeout_seconds"]
    env = block.get("api_key_env")
    if env and not cfg.get("api_key"):
        key = os.environ.get(env, "")
        if key:
            cfg["api_key"] = key
    return cfg


def build_enrich_client(config: Dict[str, Any], dry_run: bool) -> Tuple[Any, str]:
    """Return ``(client, label_config)``. Refuses a mock client outside dry-run."""
    from labelling import model_client as mc

    label_config = resolve_label_config(config, dry_run)
    block = dict(config.get("client") or {})
    if dry_run:
        return mc.MockClient(model=MOCK_MODEL), label_config
    if str(block.get("provider", "")).lower() == "mock":
        raise MockGuardError("client.provider is 'mock'; use --dry-run for offline runs")
    client = mc.create_client(_client_kwargs(block))
    if isinstance(client, mc.MockClient):
        env = block.get("api_key_env") or "the provider API key"
        raise MockGuardError("no API key found (%s is unset), so the client factory returned the offline "
                             "MockClient; refusing a non-dry-run with mock labels. Set the key or pass --dry-run."
                             % env)
    return client, label_config


# --------------------------------------------------------------------------- chat

def _last_user_text(messages: List[dict]) -> str:
    for m in reversed(messages or []):
        content = m.get("content") if isinstance(m, dict) else getattr(m, "content", "")
        role = m.get("role") if isinstance(m, dict) else getattr(m, "role", "")
        if role == "user":
            return content or ""
    return ""


def default_mock_responder(messages: List[dict], *, max_tokens: int, response_format: Optional[str]) -> str:
    """Fixed-shape offline answer. Downstream modules/tests plug their own ``responder`` as needed."""
    user_text = _last_user_text(messages)
    digest = hashlib.sha256(user_text.encode("utf-8")).hexdigest()[:12]
    if response_format == "json" and "\nREVIEWS:\n" in user_text:
        # Verifier-shaped request (pipeline.verify.build_messages): one deterministic label per ID.
        try:
            batch = json.loads(user_text.split("\nREVIEWS:\n", 1)[1])
        except ValueError:
            batch = []
        topics = ("access", "usability", "playback", "downloads", "catalog", "billing", "support", "other")
        intents = ("complaint", "request", "praise", "cancellation", "unclear")
        labels = []
        for item in batch if isinstance(batch, list) else []:
            rid = item.get("review_id") if isinstance(item, dict) else None
            if not isinstance(rid, str):
                continue
            h = int(hashlib.sha256(rid.encode("utf-8")).hexdigest(), 16)
            labels.append({"review_id": rid, "topic": topics[h % 8], "intent": intents[h % 5],
                           "severity": h % 5 + 1, "needs_review": h % 7 == 0})
        return json.dumps(labels, sort_keys=True)
    if response_format == "json":
        return json.dumps({"mock": True, "digest": digest, "items": []}, sort_keys=True)
    return "Mock response %s (offline dry run; no model was called)." % digest


class MockChat:
    """Deterministic offline chat client returning ``context.ChatResult`` with zero usage."""

    def __init__(self, responder: Optional[Callable[..., str]] = None, model: str = MOCK_MODEL):
        self.responder = responder or default_mock_responder
        self.model = model
        self.calls: List[dict] = []

    def complete(self, messages, *, max_tokens: int, temperature: float = 0.0,
                 response_format: Optional[str] = None) -> ChatResult:
        text = self.responder(messages, max_tokens=max_tokens, response_format=response_format)
        self.calls.append({"messages": messages, "max_tokens": max_tokens, "response_format": response_format})
        return ChatResult(text=text, request_id="mock-chat-" + uuid.uuid4().hex, model=self.model,
                          input_tokens=0, output_tokens=0)


class ChatAdapter:
    """Adapts OpenCode's ``labelling.chat_client`` (``chat(ChatMessage[], max_tokens, json_mode)``
    returning ``.content``) to the ``complete(...) -> context.ChatResult`` shape of INTERFACES §3."""

    def __init__(self, inner, message_cls=None):
        self.inner = inner
        self.message_cls = message_cls
        self.model = getattr(inner, "model", None)

    def complete(self, messages, *, max_tokens: int, temperature: float = 0.0,
                 response_format: Optional[str] = None) -> ChatResult:
        msgs = []
        for m in messages:
            role = m["role"] if isinstance(m, dict) else m.role
            content = m["content"] if isinstance(m, dict) else m.content
            msgs.append(self.message_cls(role=role, content=content) if self.message_cls else m)
        r = self.inner.chat(msgs, max_tokens=max_tokens, json_mode=(response_format == "json"))
        text = getattr(r, "text", None)
        if text is None:
            text = getattr(r, "content", "")
        cached = getattr(r, "cached_input_tokens", None)
        return ChatResult(text=text, request_id=str(r.request_id), model=str(r.model),
                          input_tokens=int(r.input_tokens or 0), output_tokens=int(r.output_tokens or 0),
                          cached_input_tokens=None if cached is None else int(cached),
                          cost_usd=getattr(r, "cost_usd", None))


def build_chat(config: Dict[str, Any], dry_run: bool, responder: Optional[Callable[..., str]] = None):
    """Chat client for verify/group/memo.

    Dry run -> MockChat (never a live provider). Otherwise by ``chat.provider``:
    ``anthropic`` (default; Claude Haiku 4.5 via ``pipeline.anthropic_chat``) or ``openrouter`` /
    ``deepseek`` (OpenCode's ``labelling.chat_client``). A missing key aborts; no mock fallback.
    """
    if dry_run:
        return MockChat(responder=responder)
    block = dict(config.get("chat") or {})
    provider = str(block.get("provider") or "anthropic").lower()
    if provider == "anthropic":
        from .anthropic_chat import build_anthropic_chat
        try:
            chat = build_anthropic_chat(block)
        except ImportError as exc:
            raise ClientConfigError("the 'anthropic' SDK is not installed (%s). Live chat roles need Python >= 3.10 "
                                    "and `pip install anthropic`; see configs/README.md." % exc)
        if chat is None:
            raise MockGuardError("no Anthropic API key found (%s is unset); refusing to run verify/group/memo "
                                 "without a live chat client. Set the key (e.g. in .env) or pass --dry-run."
                                 % (block.get("api_key_env") or "ANTHROPIC_API_KEY"))
        return chat
    if provider not in ("openrouter", "deepseek"):
        raise ClientConfigError("unsupported chat.provider %r (use anthropic or openrouter)" % provider)
    try:
        from labelling import chat_client as cc
    except ImportError as exc:
        raise ClientConfigError("labelling.chat_client is not available on this branch (%s); "
                                "chat.provider=%r needs it. Use provider 'anthropic' or --dry-run." % (exc, provider))
    for key in ("alternatives", "roles", "pricing_ref_usd_per_mtok", "max_output_tokens", "thinking"):
        block.pop(key, None)
    factory = getattr(cc, "create_chat_client", None)
    if factory is None:
        raise ClientConfigError("labelling.chat_client has no create_chat_client()")
    inner = factory(_client_kwargs(block))
    mock_cls = getattr(cc, "MockChatClient", None)
    if mock_cls is not None and isinstance(inner, mock_cls):
        env = block.get("api_key_env") or "the chat API key"
        raise MockGuardError("no chat API key found (%s is unset); refusing mock chat outside --dry-run" % env)
    if hasattr(inner, "complete"):
        return inner
    return ChatAdapter(inner, getattr(cc, "ChatMessage", None))


# --------------------------------------------------------------------------- .env

def load_dotenv(path, environ=None) -> List[str]:
    """Load ``KEY=value`` lines into ``environ`` (default ``os.environ``) without overriding.

    Blank lines and ``#`` comments are ignored; an optional ``export`` prefix and matching
    single/double quotes are stripped. Returns the key names that were found with a non-empty
    value (values are never printed or logged).
    """
    environ = os.environ if environ is None else environ
    found: List[str] = []
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return found
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key.startswith("export "):
            key = key[len("export "):].strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        elif " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        if not key or not key.replace("_", "").isalnum():
            continue
        if value:
            found.append(key)
        if key not in environ:
            environ[key] = value
    return found
