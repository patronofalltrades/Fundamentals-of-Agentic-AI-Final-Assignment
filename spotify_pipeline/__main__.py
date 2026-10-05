"""Enable ``python3 -m spotify_pipeline`` from the repository root."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
