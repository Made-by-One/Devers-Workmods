#!/usr/bin/env python3
"""Backwards-compatible launcher.

Older shortcuts, scripts and release archives point at ``devers_workmods.py``.
The application itself now lives in the :mod:`workmods` package; this file is
kept only so existing entries keep working.
"""

from workmods.app import main

if __name__ == "__main__":
    raise SystemExit(main())
