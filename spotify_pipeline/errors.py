"""Typed errors for the offline Spotify pipeline."""


class PipelineError(Exception):
    """Base class for all pipeline errors."""


class ValidationError(PipelineError):
    """Raised when a source row, record or JSON document is invalid."""


class ManifestError(PipelineError):
    """Raised when the input identity does not match the manifest."""


class PathCollisionError(PipelineError):
    """Raised when two required paths resolve to the same file."""


class StateError(PipelineError):
    """Raised when saved database state is inconsistent or conflicting."""


class CostError(PipelineError):
    """Raised when cost configuration or arithmetic is invalid."""
