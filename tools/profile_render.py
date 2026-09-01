#!/usr/bin/env python3
import cProfile
import pstats
import sys
from io import StringIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ui.app import app

profiler = cProfile.Profile()
profiler.enable()
with app.test_client() as client:
    client.get("/")
profiler.disable()
stream = StringIO()
stats = pstats.Stats(profiler, stream=stream).sort_stats("cumtime")
stats.print_stats(25)
print(stream.getvalue())
