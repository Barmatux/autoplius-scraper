from autoplius.popular_makes import (
    FALLBACK_POPULAR_MAKES,
    POPULAR_MAKE_LIMIT,
    make_nav_links,
)


def test_make_nav_links_start_with_all_and_eleven_makes():
    links = make_nav_links(makes=list(FALLBACK_POPULAR_MAKES[:POPULAR_MAKE_LIMIT]))
    assert len(links) == 12
    assert links[0]["label"] == "Все"
    assert "tab=all" in links[0]["href"]
    assert "make=" not in links[0]["href"]
    assert links[1]["label"] == "Volkswagen"
    assert "make=Volkswagen" in links[1]["href"]


def test_make_nav_links_default_fallback():
    links = make_nav_links()
    assert links[0]["label"] == "Все"
    assert len(links) == 1 + POPULAR_MAKE_LIMIT
