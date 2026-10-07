"""Vercel Python Function entry. Every path is rewritten here by vercel.json."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dashboard.wsgi import app  # noqa: E402,F401  (Vercel serves the WSGI callable named ``app``)
