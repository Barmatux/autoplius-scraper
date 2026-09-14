from autoplius.translate import (
    _backends,
    is_usable_russian_text,
    looks_russian,
    split_translation_chunks,
)


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


def test_translation_backends_include_gtx_and_fallbacks():
    names = [name for name, _fn in _backends()]
    assert names[0] == "gtx-lt"
    assert "gtx-auto" in names
    assert "mymemory-http" in names
    assert "libre-lt" in names
    assert "google-lt" in names


def test_split_translation_chunks_keeps_short_text():
    assert split_translation_chunks("trumpas tekstas") == ["trumpas tekstas"]


def test_split_translation_chunks_breaks_long_text():
    text = ("Labai ilgas aprašymas. " * 80).strip()
    chunks = split_translation_chunks(text, max_len=100)
    assert len(chunks) > 1
    assert all(len(chunk) <= 120 for chunk in chunks)
    assert "Labai ilgas" in chunks[0]
    assert sum(len(c) for c in chunks) >= len(text) - len(chunks)
