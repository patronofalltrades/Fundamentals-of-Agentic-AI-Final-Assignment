"""The seam between the harness (run_pipeline.py) and the downstream stage modules.

Every stage module exposes ``run(ctx: StageContext) -> dict`` (a small summary for
invocations.jsonl) and writes its artifacts under ``ctx.run_dir/<stage>/``. Model calls made
by a stage are logged with ``ctx.log_call(make_call_event(...))`` — one event per attempt.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


@dataclass(frozen=True)
class ChatResult:
    text: str
    request_id: str
    model: str
    input_tokens: int
    output_tokens: int
    cached_input_tokens: Optional[int] = None
    cost_usd: Optional[float] = None


@dataclass
class StageContext:
    run_dir: Path
    config: Dict[str, Any]              # resolved run config (see run_config.json)
    label_config: str                   # enrichment label_config in force for this run
    phase: str                          # "initial" | "resume" for this invocation
    invocation_id: str
    dry_run: bool
    texts: Dict[str, str]               # review_id -> exact review_text, CSV order preserved
    records: Dict[str, dict]            # review_id -> latest record line (completed or quarantined)
    chat: Any                           # object with .complete(messages, *, max_tokens, temperature=0.0, response_format=None) -> ChatResult
    log_call: Callable[[dict], None]    # appends one call event to calls.jsonl (fsync'd)
    ledger: Any = None                  # pipeline.spend.SpendLedger or None
    extras: Dict[str, Any] = field(default_factory=dict)

    def stage_dir(self, name: str) -> Path:
        path = Path(self.run_dir) / name
        path.mkdir(parents=True, exist_ok=True)
        return path


def make_call_event(*, role: str, review_ids: List[str], model: str, phase: str, outcome: str,
                    label_config: str, input_tokens: int = 0, output_tokens: int = 0,
                    request_id: Optional[str] = None, invocation_id: str = "", attempt: int = 1,
                    started_at: str = "", ended_at: str = "", duration_ms: int = 0,
                    provider: Optional[str] = None, error: Optional[str] = None,
                    cached_input_tokens: Optional[int] = None, reasoning_tokens: Optional[int] = None,
                    cost_usd: Optional[float] = None, **extra) -> dict:
    """Build a calls.jsonl line: grading fields first, then extras (see docs/INTERFACES.md §4)."""
    if role not in ("enrich", "verify", "group", "memo"):
        raise ValueError("bad role " + repr(role))
    if outcome not in ("succeeded", "failed"):
        raise ValueError("bad outcome " + repr(outcome))
    event = {
        "request_id": request_id or "local-" + uuid.uuid4().hex,
        "role": role, "review_ids": list(review_ids), "model": model, "phase": phase,
        "outcome": outcome, "label_config": label_config,
        "input_tokens": int(input_tokens), "output_tokens": int(output_tokens),
        "invocation_id": invocation_id, "attempt": attempt, "started_at": started_at,
        "ended_at": ended_at, "duration_ms": int(duration_ms), "provider": provider, "error": error,
        "cached_input_tokens": cached_input_tokens, "reasoning_tokens": reasoning_tokens, "cost_usd": cost_usd,
    }
    event.update(extra)
    return event
