from autoplius.myfin_rates import _parse_best_buy_rate, _parse_rate_text


def test_parse_rate_text_with_currency_suffix():
    assert _parse_rate_text("3.074 β") == 3.074
    assert _parse_rate_text("1,1585") == 1.1585


def test_parse_best_buy_rate_from_myfin_html():
    html = """
    <div class="course-brief-info course-brief-info--best-courses">
      <div class="course-brief-info__body">
        <div class="course-brief-info__r">
          <div class="course-brief-info__b"><span class="accent">3.072 β</span></div>
          <div class="course-brief-info__b"><span class="accent">3.074 β</span></div>
        </div>
      </div>
    </div>
    """
    assert _parse_best_buy_rate(html) == 3.074
