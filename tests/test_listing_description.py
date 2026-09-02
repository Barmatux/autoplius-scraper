from autoplius.listing_description import is_seller_description, seller_description


def test_rejects_parameter_dump_as_description():
    text = "Пробег: 120000 km\nТип топлива: Дизель\nКПП: автомат"
    assert not is_seller_description(text)


def test_rejects_short_meta_blurb():
    assert not is_seller_description("Parduodamas Peugeot 3008, 2016, diesel, automatas")


def test_accepts_real_seller_text():
    text = (
        "Продаю автомобиль в хорошем состоянии, обслуживался только у дилера, "
        "есть полная история сервиса и второй комплект резины."
    )
    assert is_seller_description(text)


def test_seller_description_filters_invalid_stored_text():
    item = {
        "description": "Parduodamas Ford Mondeo, 2015, diesel, 180000 km",
        "description_ru": None,
    }
    assert seller_description(item) == (None, None)


def test_rejects_autoplius_spec_summary_dump():
    text = (
        "Renault Captur, Внедорожник / Кроссовер. Первая регистрация 2018-06, "
        "Пробег 130 000 км, Тип топлива Бензин, Тип кузова Внедорожник / Кроссовер, "
        "Количество дверей 4/5, Коробка передач Автоматическая, Цвет Синий / голубой"
    )
    assert not is_seller_description(text)
    item = {"description": text, "description_ru": text}
    assert seller_description(item) == (None, None)
