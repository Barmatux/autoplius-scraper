#!/usr/bin/env python3
from pathlib import Path

for path in (
    Path("/etc/nginx/sites-enabled/autoplius-ui"),
    Path("/opt/autoplius-scraper/deploy/nginx-autoplius-ui.conf"),
):
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        "gzip_types text/html text/css application/javascript",
        "gzip_types text/css application/javascript",
    )
    path.write_text(text, encoding="utf-8")
    print("OK", path)
