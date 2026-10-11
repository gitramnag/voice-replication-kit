#!/usr/bin/env python3
"""Compatibility wrapper for the shared ``voice-kit audit`` engine."""
from __future__ import annotations

from voice_replication_kit.privacy import main


if __name__ == "__main__":
    raise SystemExit(main())
