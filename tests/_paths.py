"""Make src/ and the repo root importable from tests; locate the local dataset if present."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT / "src", ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

DATASET_DIR = Path(os.environ.get(
    "A5_DATASET_DIR",
    Path.home() / "Desktop/Fundamentals of Agentic AI - Final Assignment - Spotify/Final Assignment - Spotify Reviews Dataset",
))
