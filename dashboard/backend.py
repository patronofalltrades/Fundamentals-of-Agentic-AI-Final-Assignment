"""Read/write backends for the dashboard: local SQLite and Postgres over Neon's HTTPS SQL endpoint.

Both backends expose the small cursor surface the API and importer use:
``execute(sql, params).fetchone() / .fetchall() / iteration``, rows that support ``row[0]``,
``row["name"]`` and ``dict(row)``. SQL is written once in the SQLite dialect with ``?``
placeholders; ``NeonHTTPBackend`` translates the two differences we use (``?`` -> ``$n`` and
``instr(`` -> ``strpos(``).

Standard library only. The Neon backend sends HTTPS requests with ``urllib``; it never logs the
connection string. Import has no side effect: nothing connects until ``execute`` is called.
"""

import json
import os
import re
import sqlite3
import urllib.request
from decimal import Decimal
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence
from urllib.parse import urlparse

from .store import connect

INT_TYPES = {20, 21, 23, 26}          # int8, int2, int4, oid
FLOAT_TYPES = {700, 701}              # float4, float8
NUMERIC_TYPE = 1700
BOOL_TYPE = 16


class Row:
    """A result row with positional, name and ``dict()`` access, like ``sqlite3.Row``."""

    __slots__ = ("_names", "_values")

    def __init__(self, names: Sequence[str], values: Sequence[Any]):
        self._names = list(names)
        self._values = list(values)

    def keys(self):
        return list(self._names)

    def __getitem__(self, key):
        if isinstance(key, (int, slice)):
            return self._values[key]
        try:
            return self._values[self._names.index(key)]
        except ValueError:
            raise KeyError(key) from None

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)

    def __repr__(self):
        return "Row(%r)" % dict(zip(self._names, self._values))


class _Result:
    def __init__(self, rows: List[Row]):
        self._rows = rows

    def fetchone(self) -> Optional[Row]:
        return self._rows[0] if self._rows else None

    def fetchall(self) -> List[Row]:
        return list(self._rows)

    def __iter__(self):
        return iter(self._rows)


class SQLiteBackend:
    """Local SQLite file. ``readonly`` opens with ``mode=ro`` and ``query_only``."""

    dialect = "sqlite"

    def __init__(self, path: str, readonly: bool = True):
        self.path = path
        self.readonly = readonly
        self._conn = connect(path, readonly=readonly)

    @property
    def stores_full_text(self) -> bool:
        return self.table_exists("texts")

    def execute(self, sql: str, params: Sequence[Any] = ()):
        return self._conn.execute(sql, tuple(params))

    def executemany(self, sql: str, rows: Iterable[Sequence[Any]]):
        self._conn.executemany(sql, rows)

    def run_batch(self, statements: List[tuple]) -> None:
        """Run ``[(sql, params), ...]`` in one transaction."""
        with self._conn:
            for sql, params in statements:
                self._conn.execute(sql, tuple(params))

    def table_exists(self, name: str) -> bool:
        return self._conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone()[0] == 1

    def close(self) -> None:
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def translate_sqlite_to_postgres(sql: str) -> str:
    """``?`` -> ``$1..$n`` outside string literals; ``instr(`` -> ``strpos(``."""
    out, n, quote = [], 0, None
    for ch in sql:
        if quote:
            out.append(ch)
            if ch == quote:
                quote = None
        elif ch in ("'", '"'):
            quote = ch
            out.append(ch)
        elif ch == "?":
            n += 1
            out.append("$%d" % n)
        else:
            out.append(ch)
    return re.sub(r"\binstr\(", "strpos(", "".join(out), flags=re.IGNORECASE)


def _parse(value: Any, type_id: Optional[int]):
    if value is None or not isinstance(value, str):
        return value
    if type_id in INT_TYPES:
        return int(value)
    if type_id in FLOAT_TYPES:
        return float(value)
    if type_id == NUMERIC_TYPE:
        number = Decimal(value)
        return int(number) if number == number.to_integral_value() else float(number)
    if type_id == BOOL_TYPE:
        return value in ("t", "true", "1")
    return value


def _https_post(url: str, headers: Dict[str, str], body: bytes, timeout: float) -> Dict[str, Any]:
    request = urllib.request.Request(url, data=body, method="POST", headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


class NeonHTTPBackend:
    """Postgres through Neon's HTTPS ``/sql`` endpoint (the transport used by Neon's serverless driver).

    ``transport(url, headers, body_bytes, timeout) -> dict`` is injectable for tests.
    The connection string is sent only in the ``Neon-Connection-String`` header.
    """

    dialect = "postgres"
    stores_full_text = False

    def __init__(self, connection_string: str, transport: Optional[Callable[..., Dict[str, Any]]] = None,
                 timeout: float = 15.0):
        parsed = urlparse(connection_string)
        if parsed.scheme not in ("postgres", "postgresql") or not parsed.hostname:
            raise ValueError("DATABASE_URL must be a postgres:// connection string")
        self._dsn = connection_string
        self._url = "https://%s/sql" % parsed.hostname
        self._transport = transport or _https_post
        self._timeout = timeout

    def _headers(self) -> Dict[str, str]:
        return {"Content-Type": "application/json", "Neon-Connection-String": self._dsn,
                "Neon-Raw-Text-Output": "true", "Neon-Array-Mode": "true"}

    @staticmethod
    def _rows(payload: Dict[str, Any]) -> List[Row]:
        fields = payload.get("fields") or []
        names = [f.get("name") for f in fields]
        types = [f.get("dataTypeID") for f in fields]
        return [Row(names, [_parse(v, t) for v, t in zip(values, types)]) for values in payload.get("rows") or []]

    def execute(self, sql: str, params: Sequence[Any] = ()):
        body = json.dumps({"query": translate_sqlite_to_postgres(sql), "params": list(params)}).encode("utf-8")
        return _Result(self._rows(self._transport(self._url, self._headers(), body, self._timeout)))

    def executemany(self, sql: str, rows: Iterable[Sequence[Any]]):
        self.run_batch([(sql, row) for row in rows])

    def run_batch(self, statements: List[tuple]) -> None:
        """Run ``[(sql, params), ...]`` as one Postgres transaction (one HTTPS request)."""
        if not statements:
            return
        body = json.dumps({"queries": [{"query": translate_sqlite_to_postgres(sql), "params": list(params)}
                                       for sql, params in statements]}).encode("utf-8")
        self._transport(self._url, dict(self._headers(), **{"Neon-Batch-Isolation-Level": "Serializable"}),
                        body, self._timeout)

    def table_exists(self, name: str) -> bool:
        row = self.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_name=?", (name,)).fetchone()
        return bool(row and row[0])

    def close(self) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def from_env(environ: Optional[Dict[str, str]] = None):
    """``DATABASE_URL`` (postgres) wins; else ``DASHBOARD_DB`` (SQLite path, read-only)."""
    environ = os.environ if environ is None else environ
    url = environ.get("DATABASE_URL") or environ.get("POSTGRES_URL")
    if url:
        return NeonHTTPBackend(url)
    path = environ.get("DASHBOARD_DB")
    if path:
        return SQLiteBackend(path, readonly=True)
    raise ValueError("set DATABASE_URL (postgres) or DASHBOARD_DB (SQLite path)")
