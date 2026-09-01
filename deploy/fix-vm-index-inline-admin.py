#!/usr/bin/env python3
"""Repair VM index.html and place admin controls under the car name."""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys

INDEX = Path("/opt/autoplius-scraper/ui/templates/index.html")
REPO = Path("/opt/autoplius-scraper")


def restore_from_stash() -> str:
    for ref in ("stash@{0}", "stash@{1}", "stash@{3}"):
        try:
            text = subprocess.check_output(
                ["git", "-C", str(REPO), "show", f"{ref}:ui/templates/index.html"],
                text=True,
            )
        except subprocess.CalledProcessError:
            continue
        if "body_type_lines" in text and len(text.splitlines()) > 300:
            return text
    raise SystemExit("no suitable stashed index.html found")


def patch(text: str) -> str:
    text = text.replace('          {% include "_index_admin_column_head.html" %}\n', "")
    text = text.replace('            {% include "_index_admin_column_th.html" %}\n', "")
    text = text.replace(
        '            </td>\n            {% include "_listing_admin_actions.html" %}\n          </tr>',
        "            </td>\n          </tr>",
    )
    broken = (
        '              {% endfor %}\n'
        '              {% include "_listing_admin_actions.html" %}'
    )
    fixed = (
        '              {% endfor %}\n'
        '              {% endif %}\n'
        '              {% include "_listing_admin_actions.html" %}'
    )
    if broken in text:
        text = text.replace(broken, fixed, 1)
    elif '_listing_admin_actions' not in text:
        anchor = (
            '              {% endfor %}\n'
            '              {% endif %}\n'
            '            </td>\n'
            '            <td class="col-engine">'
        )
        insert = (
            '              {% endfor %}\n'
            '              {% endif %}\n'
            '              {% include "_listing_admin_actions.html" %}\n'
            '            </td>\n'
            '            <td class="col-engine">'
        )
        if anchor not in text:
            raise SystemExit("col-auto anchor not found")
        text = text.replace(anchor, insert, 1)
    if '_admin_bar.html' not in text:
        text = text.replace(
            '      <div class="pill accent">{{ total_in_db }}',
            '      {% include "_admin_bar.html" %}\n'
            '      <div class="pill accent">{{ total_in_db }}',
            1,
        )
    if '_admin_flash.html' not in text:
        text = text.replace(
            '    <form class="filters" method="get">',
            '    {% include "_admin_flash.html" %}\n\n'
            '    <form class="filters" method="get">',
            1,
        )
    if "admin.js" not in text:
        text = text.replace(
            '  <script src="{{ url_for(\'static\', filename=\'make_model_filter.js\') }}" defer></script>',
            '  <script src="{{ url_for(\'static\', filename=\'admin.js\') }}" defer></script>\n'
            '  <script src="{{ url_for(\'static\', filename=\'make_model_filter.js\') }}" defer></script>',
            1,
        )
    return text


def main() -> int:
    text = INDEX.read_text(encoding="utf-8") if INDEX.is_file() else ""
    if "body_type_lines" not in text or len(text.splitlines()) < 300:
        text = restore_from_stash()
    text = patch(text)
    INDEX.write_text(text, encoding="utf-8")
    print("OK", INDEX, "lines", len(text.splitlines()))
    print("inline_actions", "_listing_admin_actions" in text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
