"""Offline, standard-library-only foundation for the Spotify review pipeline.

Scope: ingestion, bounded-memory dedup and state, schema validation for
completed/quarantined records, checkpoints and an offline cost scaffold.
No model or provider calls are implemented.
"""

__all__ = ["__version__"]

__version__ = "0.1.0"
