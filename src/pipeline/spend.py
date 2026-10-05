"""Shared rate limiting, the spend ledger, and bounded retries with backoff + full jitter.

All three take injectable clocks / sleeps / random sources so tests never wait in real time.
"""
from __future__ import annotations

import json
import math
import random
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from .context import utc_now
from .io import atomic_write_json


# --------------------------------------------------------------------------- rate limiting

class _Bucket:
    def __init__(self, per_minute: float, now: float):
        self.capacity = float(per_minute)
        self.rate = float(per_minute) / 60.0
        self.level = self.capacity
        self.stamp = now

    def refill(self, now: float) -> None:
        if now > self.stamp:
            self.level = min(self.capacity, self.level + (now - self.stamp) * self.rate)
            self.stamp = now

    def wait_for(self, amount: float) -> float:
        amount = min(amount, self.capacity)  # an oversized request waits for a full bucket
        if self.level >= amount:
            return 0.0
        return (amount - self.level) / self.rate


class RateLimiter:
    """Token buckets for requests/min and tokens/min, shared by all worker threads.

    ``acquire(tokens)`` blocks until both buckets can pay, then debits them. ``None`` disables a
    limit. ``clock``/``sleep`` are injectable for tests.
    """

    def __init__(self, requests_per_minute: Optional[float] = None, tokens_per_minute: Optional[float] = None,
                 clock: Callable[[], float] = time.monotonic, sleep: Callable[[float], None] = time.sleep):
        self.clock = clock
        self.sleep = sleep
        now = clock()
        self._req = _Bucket(requests_per_minute, now) if requests_per_minute else None
        self._tok = _Bucket(tokens_per_minute, now) if tokens_per_minute else None
        self._lock = threading.Lock()
        self.waited_seconds = 0.0

    def acquire(self, tokens: int = 0) -> float:
        """Block until admitted; returns seconds waited."""
        waited = 0.0
        while True:
            with self._lock:
                now = self.clock()
                delay = 0.0
                for bucket, amount in ((self._req, 1), (self._tok, tokens)):
                    if bucket is not None:
                        bucket.refill(now)
                        delay = max(delay, bucket.wait_for(amount))
                if delay <= 0:
                    if self._req is not None:
                        self._req.level -= 1
                    if self._tok is not None:
                        self._tok.level -= min(tokens, self._tok.capacity)
                    self.waited_seconds += waited
                    return waited
            self.sleep(delay)
            waited += delay


# --------------------------------------------------------------------------- spend ledger

class BudgetExceeded(Exception):
    """Admitting the next call would exceed the spend cap."""


def cost_from_usage(rates: Optional[Dict[str, Any]], input_tokens: int, output_tokens: int,
                    cached_input_tokens: Optional[int] = None, requests: int = 1) -> Optional[float]:
    """USD for one call from per-million-token (and optional per-request) rates; None if unpriced.

    ``input_tokens`` includes cached input; cached tokens are billed at ``cached_input_per_mtok``
    (falling back to the uncached rate) and subtracted from the uncached count.
    """
    if not rates:
        return None
    keys = ("input_per_mtok", "output_per_mtok", "cached_input_per_mtok", "per_request")
    if all(rates.get(k) is None for k in keys):
        return None
    cached = int(cached_input_tokens or 0)
    uncached = max(0, int(input_tokens) - cached)
    in_rate = float(rates.get("input_per_mtok") or 0.0)
    cached_rate = rates.get("cached_input_per_mtok")
    cached_rate = in_rate if cached_rate is None else float(cached_rate)
    out_rate = float(rates.get("output_per_mtok") or 0.0)
    total = (uncached * in_rate + cached * cached_rate + int(output_tokens) * out_rate) / 1_000_000
    total += requests * float(rates.get("per_request") or 0.0)
    return total


class SpendLedger:
    """Reserve worst-case cost before dispatch, commit actual cost after, persist to ledger.json.

    Admission rule: ``spent + unpriced + uncertain + reserved + next <= cap``. ``unpriced`` charges
    the reservation for calls whose cost is unknown (no provider cost, no rates) and ``uncertain``
    does the same for timeouts, so an unknown bill never silently counts as zero.
    """

    def __init__(self, cap_usd: Optional[float], path=None, rates: Optional[Dict[str, Any]] = None):
        self.cap_usd = None if cap_usd is None else float(cap_usd)
        self.path = Path(path) if path else None
        self.rates = rates or {}
        self._lock = threading.Lock()
        self._next_id = 0
        self._reservations: Dict[int, tuple] = {}
        self.spent_usd = 0.0
        self.unpriced_usd = 0.0
        self.uncertain_usd = 0.0
        self.by_role: Dict[str, Dict[str, float]] = {}
        if self.path and self.path.exists():
            prior = json.loads(self.path.read_text(encoding="utf-8"))
            self.spent_usd = float(prior.get("spent_usd", 0.0))
            self.unpriced_usd = float(prior.get("unpriced_estimate_usd", 0.0))
            self.uncertain_usd = float(prior.get("uncertain_usd", 0.0))
            self.by_role = {k: dict(v) for k, v in (prior.get("by_role") or {}).items()}

    # -- accounting helpers
    def rates_for(self, role: str) -> Optional[Dict[str, Any]]:
        return self.rates.get(role) or self.rates.get("default")

    @property
    def reserved_usd(self) -> float:
        return sum(r[1] for r in self._reservations.values())

    def committed_usd(self) -> float:
        return self.spent_usd + self.unpriced_usd + self.uncertain_usd

    def can_admit(self, next_estimate: float) -> bool:
        if self.cap_usd is None:
            return True
        with self._lock:
            return self.committed_usd() + self.reserved_usd + float(next_estimate) <= self.cap_usd + 1e-12

    def reserve(self, amount: float, role: str = "enrich") -> int:
        """Atomically check the cap and reserve; raises BudgetExceeded instead of admitting."""
        amount = max(0.0, float(amount))
        with self._lock:
            if self.cap_usd is not None and self.committed_usd() + self.reserved_usd + amount > self.cap_usd + 1e-12:
                raise BudgetExceeded("spend cap %.4f USD reached (committed %.4f, reserved %.4f, next %.4f)"
                                     % (self.cap_usd, self.committed_usd(), self.reserved_usd, amount))
            self._next_id += 1
            self._reservations[self._next_id] = (role, amount)
            return self._next_id

    def _role(self, role: str) -> Dict[str, float]:
        return self.by_role.setdefault(role, {"spent_usd": 0.0, "unpriced_estimate_usd": 0.0,
                                              "uncertain_usd": 0.0, "calls": 0, "unpriced_calls": 0})

    def commit(self, reservation: Optional[int], cost_usd: Optional[float], role: str = "enrich",
               uncertain: bool = False) -> None:
        """Settle a reservation. ``cost_usd=None`` charges the reservation as an estimate."""
        with self._lock:
            _, amount = self._reservations.pop(reservation, (role, 0.0)) if reservation is not None else (role, 0.0)
            entry = self._role(role)
            entry["calls"] += 1
            if uncertain:
                charge = amount if cost_usd is None else float(cost_usd)
                self.uncertain_usd += charge
                entry["uncertain_usd"] += charge
            elif cost_usd is None:
                self.unpriced_usd += amount
                entry["unpriced_estimate_usd"] += amount
                entry["unpriced_calls"] += 1
            else:
                self.spent_usd += float(cost_usd)
                entry["spent_usd"] += float(cost_usd)

    def release(self, reservation: Optional[int]) -> None:
        with self._lock:
            self._reservations.pop(reservation, None)

    def charge(self, cost_usd: Optional[float], role: str, estimate: float = 0.0, uncertain: bool = False) -> None:
        """Record a call made without a prior reservation (e.g. downstream chat roles)."""
        with self._lock:
            self._next_id += 1
            res = self._next_id
            self._reservations[res] = (role, max(0.0, float(estimate)))
        self.commit(res, cost_usd, role, uncertain)

    def summary(self) -> dict:
        with self._lock:
            return {"cap_usd": self.cap_usd, "spent_usd": round(self.spent_usd, 8),
                    "unpriced_estimate_usd": round(self.unpriced_usd, 8),
                    "uncertain_usd": round(self.uncertain_usd, 8),
                    "reserved_usd": round(self.reserved_usd, 8),
                    "committed_usd": round(self.committed_usd(), 8),
                    "by_role": self.by_role, "updated_at": utc_now(),
                    "note": "spent = provider-reported or rate-computed cost; unpriced/uncertain = reservation "
                            "estimates charged for calls with unknown cost or timeouts (never silently zero)."}

    def save(self) -> None:
        if self.path:
            atomic_write_json(self.path, self.summary())


# --------------------------------------------------------------------------- retries

def backoff_delay(attempt: int, *, base: float = 1.0, cap: float = 60.0, rng: Callable[[], float] = random.random,
                  retry_after: Optional[float] = None) -> float:
    """Exponential backoff with full jitter; a provider ``retry_after`` is a floor."""
    delay = rng() * min(cap, base * (2 ** max(0, attempt - 1)))
    if retry_after is not None:
        try:
            ra = float(retry_after)
            if math.isfinite(ra) and ra > 0:
                delay = max(delay, ra)
        except (TypeError, ValueError):
            pass
    return delay


def retry_call(fn: Callable[[int], Any], *, max_attempts: int = 5, base_delay: float = 1.0, max_delay: float = 60.0,
               sleep: Callable[[float], None] = time.sleep, rng: Callable[[], float] = random.random,
               should_retry: Optional[Callable[[BaseException, int], bool]] = None,
               on_error: Optional[Callable[[BaseException, int, Optional[float]], None]] = None):
    """Call ``fn(attempt)`` until it returns, retrying while ``should_retry(exc, attempt)``.

    Default retries only ``TransientModelError``-like errors (``exc.retryable`` true). Honors
    ``exc.retry_after``. ``on_error(exc, attempt, delay_or_None)`` sees every failure (for logging).
    Re-raises the last error when attempts are exhausted or the error is not retryable.
    """
    attempt = 0
    while True:
        attempt += 1
        try:
            return fn(attempt)
        except Exception as exc:  # noqa: BLE001 - classified below
            retryable = should_retry(exc, attempt) if should_retry else bool(getattr(exc, "retryable", False))
            retryable = retryable and attempt < max_attempts
            delay = backoff_delay(attempt, base=base_delay, cap=max_delay, rng=rng,
                                  retry_after=getattr(exc, "retry_after", None)) if retryable else None
            if on_error:
                on_error(exc, attempt, delay)
            if not retryable:
                raise
            sleep(delay)
