#!/usr/bin/env python3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ui.app import app

client = app.test_client()
start = time.perf_counter()
response = client.get("/")
elapsed = time.perf_counter() - start
print("status", response.status_code)
print("render_sec", round(elapsed, 3))
print("bytes", len(response.data))
