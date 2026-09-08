from autoplius.translate import is_usable_russian_text, looks_russian


def test_looks_russian_detects_cyrillic():
    assert looks_russian("Продается автомобиль в хорошем состоянии")
    assert not looks_russian(
        "Parduodamas labai geros būklės automobilis su pilna istorija"
    )


def test_is_usable_russian_text_rejects_errors_and_lithuanian():
    assert is_usable_russian_text("Машина в отличном состоянии, полный сервис")
    assert not is_usable_russian_text("Error 500: server error please try again later")
    assert not is_usable_russian_text(
        "Parduodamas labai geros būklės automobilis su pilna istorija"
    )
