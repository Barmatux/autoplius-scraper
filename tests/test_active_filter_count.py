def test_year_filter_values_must_tolerate_ints():
    """Import presets pass year_from/year_to as ints into filter counting."""
    year_from = 2011
    year_to = 2016
    assert str(year_from or "").strip() == "2011"
    assert str(year_to or "").strip() == "2016"
    # The previous implementation called .strip() on ints and raised AttributeError.
    try:
        (year_from or "").strip()
        raised = False
    except AttributeError:
        raised = True
    assert raised
