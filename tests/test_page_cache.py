from pathlib import Path

from ui.page_cache import (
    get_cached_html,
    invalidate_page_cache,
    is_bot_user_agent,
    make_cache_key,
    set_cached_html,
)


def test_is_bot_user_agent():
    assert is_bot_user_agent("Mozilla/5.0 (compatible; YandexBot/3.0; +http://yandex.com/bots)")
    assert is_bot_user_agent("Googlebot/2.1 (+http://www.google.com/bot.html)")
    assert is_bot_user_agent("Mozilla/5.0 (compatible; GPTBot/1.0)")
    assert not is_bot_user_agent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0")


def test_is_ai_bot_user_agent():
    from ui.page_cache import is_ai_bot_user_agent

    assert is_ai_bot_user_agent("Mozilla/5.0 (compatible; GPTBot/1.0; +https://openai.com/gptbot)")
    assert is_ai_bot_user_agent("ClaudeBot/1.0")
    assert not is_ai_bot_user_agent("Mozilla/5.0 (compatible; YandexBot/3.0; +http://yandex.com/bots)")
    assert not is_ai_bot_user_agent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0")


def test_page_cache_roundtrip(tmp_path: Path):
    invalidate_page_cache()
    db = tmp_path / "db.sqlite"
    db.write_text("x", encoding="utf-8")
    key = make_cache_key("home", db, "sort=added_desc")
    assert get_cached_html(key) is None
    set_cached_html(key, "<html>ok</html>", ttl_sec=30)
    assert get_cached_html(key) == "<html>ok</html>"
    invalidate_page_cache()
    assert get_cached_html(key) is None


def test_page_cache_key_changes_with_db_mtime(tmp_path: Path):
    invalidate_page_cache()
    db = tmp_path / "db.sqlite"
    db.write_text("a", encoding="utf-8")
    key1 = make_cache_key("home", db, "")
    set_cached_html(key1, "v1", ttl_sec=30)
    db.write_text("ab", encoding="utf-8")
    key2 = make_cache_key("home", db, "")
    assert key1 != key2
    assert get_cached_html(key2) is None
