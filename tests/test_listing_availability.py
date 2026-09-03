from autoplius.listing_availability import classify_listing_html


def test_classify_available_listing_html():
    html = """
    <html><head><title>Ford Focus</title></head>
    <body>
      <div class="second-parameters"><div class="parameter-row">Пробег</div></div>
      <div class="announcement-price">6 600 €</div>
      <div class="announcement-id">ID 31898439</div>
    </body></html>
    """
    result = classify_listing_html(
        status_code=200,
        url="https://ru.autoplius.lt/objavlenija/ford-31898439.html",
        title="Ford Focus",
        html=html,
        listing_id=31898439,
    )
    assert result.status == "available"


def test_classify_related_ads_shell_is_not_available():
    html = """
    <html><head><title>Skelbimas nerastas</title></head>
    <body>
      <h1>Skelbimas nerastas</h1>
      <a href="/objavlenija/a-111.html">A</a>
      <a href="/objavlenija/b-222.html">B</a>
      <a href="/objavlenija/c-333.html">C</a>
      <a href="/objavlenija/d-444.html">D</a>
      <a href="/objavlenija/e-555.html">E</a>
      <a href="/objavlenija/f-666.html">F</a>
      <a href="/objavlenija/g-777.html">G</a>
      <a href="/objavlenija/h-888.html">H</a>
    </body></html>
    """
    result = classify_listing_html(
        status_code=200,
        url="https://ru.autoplius.lt/objavlenija/ford-galaxy-31898439.html",
        title="Skelbimas nerastas",
        html=html,
        listing_id=31898439,
    )
    assert result.status == "unavailable"


def test_classify_not_found_page():
    html = "<html><head><title>404</title></head><body>Страница не найдена</body></html>"
    result = classify_listing_html(
        status_code=200, url="https://ru.autoplius.lt/x", title="404", html=html
    )
    assert result.status == "unavailable"


def test_classify_http_404():
    result = classify_listing_html(status_code=404, url="https://ru.autoplius.lt/x", title="", html="")
    assert result.status == "unavailable"


def test_classify_challenge_unknown_cloudflare():
    html = "<html><title>Just a moment...</title><body>cf-turnstile</body></html>"
    result = classify_listing_html(
        status_code=403,
        url="https://ru.autoplius.lt/x",
        title="Just a moment...",
        html=html,
    )
    assert result.status == "unknown"
    assert result.reason == "cloudflare"
    assert "Cloudflare" in result.reason_label


def test_classify_requires_listing_id_match():
    html = """
    <html><body>
      <div class="second-parameters"><div class="parameter-row">x</div></div>
      <div class="announcement-price">100 €</div>
      ID 11111111
    </body></html>
    """
    result = classify_listing_html(
        status_code=200,
        url="https://ru.autoplius.lt/objavlenija/x-31898439.html",
        title="Ford",
        html=html,
        listing_id=31898439,
    )
    assert result.status == "unknown"
    assert result.reason == "no_content"
