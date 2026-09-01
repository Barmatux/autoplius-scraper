#!/usr/bin/env python3
"""Add inline admin controls to the VM index template without replacing the whole file."""
from __future__ import annotations

from pathlib import Path

INDEX = Path("/opt/autoplius-scraper/ui/templates/index.html")
TABS = Path("/opt/autoplius-scraper/ui/templates/_tabs.html")
ACTIONS_MARKER = '{% include "_listing_admin_actions.html" %}'
ADMIN_COL_HEAD = '          {% include "_index_admin_column_head.html" %}\n'
ADMIN_COL_TH = '            {% include "_index_admin_column_th.html" %}\n'


def ensure(text: str, needle: str, insert: str, *, before: str | None = None) -> str:
    if needle in text:
        return text
    anchor = before or needle
    pos = text.index(anchor)
    return text[:pos] + insert + text[pos:]


def remove_admin_column(text: str) -> str:
    text = text.replace(ADMIN_COL_HEAD, "")
    text = text.replace(ADMIN_COL_TH, "")
    text = text.replace(
        "            </td>\n            {% include \"_listing_admin_actions.html\" %}\n          </tr>",
        "            </td>\n          </tr>",
    )
    return text


def move_actions_inline(text: str) -> str:
    text = remove_admin_column(text)
    if ACTIONS_MARKER in text and "listing-admin-actions" in text:
        return text
    anchor = (
        "              {% endfor %}\n"
        "              {% endif %}\n"
        "            </td>\n"
        "            <td class=\"col-engine\">"
    )
    replacement = (
        "              {% endfor %}\n"
        "              {% endif %}\n"
        "              {% include \"_listing_admin_actions.html\" %}\n"
        "            </td>\n"
        "            <td class=\"col-engine\">"
    )
    if anchor not in text:
        raise SystemExit("could not find col-auto anchor for admin actions")
    return text.replace(anchor, replacement, 1)


def main() -> int:
    if not INDEX.is_file():
        raise SystemExit(f"missing {INDEX}")
    text = INDEX.read_text(encoding="utf-8")

    text = ensure(
        text,
        "_admin_bar.html",
        '      {% include "_admin_bar.html" %}\n',
        before='      <div class="pill accent">{{ total_in_db }}',
    )
    text = ensure(
        text,
        "_admin_flash.html",
        '    {% include "_admin_flash.html" %}\n\n',
        before='    <form class="filters" method="get">',
    )
    text = move_actions_inline(text)
    text = ensure(
        text,
        "admin.js",
        '  <script src="{{ url_for(\'static\', filename=\'admin.js\') }}" defer></script>\n',
        before='  <script src="{{ url_for(\'static\', filename=\'make_model_filter.js\') }}" defer></script>',
    )

    if TABS.is_file():
        tabs_text = TABS.read_text(encoding="utf-8")
        if "admin_listings" in tabs_text:
            tabs_text = tabs_text.replace(
                """  <a
    href="{{ url_for('admin_listings') }}"
    class="tab{% if active_tab == 'admin' %} active{% endif %}"
  >Админка</a>
""",
                "",
            )
            TABS.write_text(tabs_text, encoding="utf-8")

    INDEX.write_text(text, encoding="utf-8")
    print("OK patched", INDEX)
    print("_admin_bar", "_admin_bar.html" in text)
    print("inline_actions", ACTIONS_MARKER in text and ADMIN_COL_HEAD not in text)
    print("admin.js", "admin.js" in text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
