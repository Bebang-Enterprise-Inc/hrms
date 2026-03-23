"""Centralized configuration for governor-erp. No hardcoded user paths."""
from __future__ import annotations

import os
import shutil

DOPPLER_BIN = os.environ.get("DOPPLER_BIN") or shutil.which("doppler") or "doppler"
BEI_TASKS_DIR = os.environ.get("BEI_TASKS_DIR", "F:/Dropbox/Projects/bei-tasks")
VERCEL_SCOPE = os.environ.get("VERCEL_SCOPE", "team_xvK1nhuvsdZp3GNfd4uDJ0DW")
GOVERNOR_REPO = "Bebang-Enterprise-Inc/hrms"
