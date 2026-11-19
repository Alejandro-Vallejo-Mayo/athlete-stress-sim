"""Shared pytest configuration."""

from __future__ import annotations

import os

# Never trigger the network-bound startup sync while running the test suite.
os.environ.setdefault("POLAR_SYNC_ON_STARTUP", "false")
