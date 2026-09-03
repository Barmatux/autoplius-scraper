from autoplius.listing_availability import classify_listing_html


def test_classify_available_listing_html():
    html = """
    <html><head><title>Ford Focus</title></head>
    <body>
      <div class="second-parameters"><div class="parameter-row">Пробег</div></div>
      <div class="announcement-price">6 600 €</div>
    </body></html>
    """
    assert classify_listing_html(status_code=200, url="https://ru.autoplius.lt/x.html", title="Ford Focus", html=html) == "available"


def test_classify_not_found_page():
    html = "<html><head><title>404</title></head><body>Страница не найдена</body></html>"
    assert classify_listing_html(status_code=200, url="https://ru.autoplius.lt/x", title="404", html=html) == "unavailable"


def test_classify_http_404():
    assert classify_listing_html(status_code=404, url="https://ru.autoplius.lt/x", title="", html="") == "unavailable"


def test_classify_challenge_unknown():
    html = "<html><title>Just a moment...</title><body>cf-turnstile</body></html>"
    assert (
        classify_listing_html(
            status_code=403,
            url="https://ru.autoplius.lt/x",
            title="Just a moment...",
            html=html,
        )
        == "unknown"
    )
