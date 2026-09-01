#!/usr/bin/env python3
"""Add inline admin controls to the VM index template without replacing the whole file."""
from __future__ import annotations

from pathlib import Path

INDEX = Path("/opt/autoplius-scraper/ui/templates/index.html")
GIT = Path("/tmp/git_index.html")


def ensure(text: str, needle: str, insert: str, *, before: str | None = None) -> str:
    if needle in text:
        return text
    anchor = before or needle
    pos = text.index(anchor)
    return text[:pos] + insert + text[pos:]


def main() -> int:
    if not INDEX.is_file():
        raise SystemExit(f"missing {INDEX}")
    text = INDEX.read_text(encoding="utf-8")

    text = ensure(
        text,
        '_admin_bar.html',
        '      {% include "_admin_bar.html" %}\n',
        before='      <div class="pill accent">{{ total_in_db }}',
    )
    text = ensure(
        text,
        '_admin_flash.html',
        '    {% include "_admin_flash.html" %}\n\n',
        before='    <form class="filters" method="get">',
    )
    text = ensure(
        text,
        '_index_admin_column_head.html',
        '          {% include "_index_admin_column_head.html" %}\n',
        before='        </colgroup>',
    )
    text = ensure(
        text,
        '_index_admin_column_th.html',
        '            {% include "_index_admin_column_th.html" %}\n',
        before='          </tr>\n        </thead>',
    )
    text = ensure(
        text,
        '_listing_admin_actions.html',
        '            {% include "_listing_admin_actions.html" %}\n',
        before='          </tr>\n          {% endfor %}',
    )
    text = ensure(
        text,
        "admin.js",
        '  <script src="{{ url_for(\'static\', filename=\'admin.js\') }}" defer></script>\n',
        before='  <script src="{{ url_for(\'static\', filename=\'make_model_filter.js\') }}" defer></script>',
    )

    if 'url_for(\'admin_listings\')' in text:
        text = text.replace(
            """  <a
    href="{{ url_for('admin_listings') }}"
    class="tab{% if active_tab == 'admin' %} active{% endif %}"
  >Админка</a>
""",
            "",
        )

    tabs = INDEX.parent / "_tabs.html"
    if tabs.is_file():
        tabs_text = tabs.read_text(encoding="utf-8")
        if "admin_listings" in tabs_text:
            tabs_text = tabs_text.replace(
                """  <a
    href="{{ url_for('admin_listings') }}"
    class="tab{% if active_tab == 'admin' %} active{% endif %}"
  >Админка</a>
""",
                "",
            )
            tabs.write_text(tabs_text, encoding="utf-8")

    INDEX.write_text(text, encoding="utf-8")
    print("OK patched", INDEX)
    print("_admin_bar", "_admin_bar.html" in text)
    print("_listing_admin_actions", "_listing_admin_actions.html" in text)
    print("admin.js", "admin.js" in text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
