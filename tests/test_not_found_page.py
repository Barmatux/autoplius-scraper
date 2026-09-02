from __future__ import annotations

from autoplius.browser import is_not_found_page


def test_listing_id_with_404_digits_is_not_treated_as_not_found():
    assert is_not_found_page("A31404018", "") is False
    assert is_not_found_page("Renault Kadjar · A31404018", "<html>second-parameters</html>") is False
    assert is_not_found_page("31404018 - Autoplius", "") is False


def test_real_404_title_is_detected():
    assert is_not_found_page("404", "") is True
    assert is_not_found_page("Page 404 Not Found", "") is True
    assert is_not_found_page("Страница не найдена", "") is True


def test_not_found_phrase_in_html_is_detected():
    assert is_not_found_page("Autoplius", "<h1>Страница не найдена</h1>") is True
