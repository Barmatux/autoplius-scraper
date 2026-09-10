import os

from autoplius.company_info import company_info


def test_company_info_scandi_defaults(monkeypatch):
    for key in list(os.environ):
        if key.startswith("COMPANY_"):
            monkeypatch.delenv(key, raising=False)
    info = company_info()
    assert info["is_configured"] is True
    assert info["full_name"] == "Общество с ограниченной ответственностью «Сканди Моторс»"
    assert info["short_name"] == "ООО «Сканди Моторс»"
    assert info["unp"] == "193866357"
    assert info["legal_address"] == "г. Минск, ул. Скрыганова, дом 6, помещение 7"
    assert info["director"] == "Герасимец Максим Сергеевич"
    assert info["director_genitive"] == "Герасимца Максима Сергеевича"
    assert info["email"] == "scandimotorsby@gmail.com"
    assert info["phone"] == "+375 (33) 698-77-99"
    assert info["bank_account"] == "BY58 ALFA 3012 2G91 3900 1027 0000"
    assert info["bank_swift"] == "ALFABY2X"
    assert info["okpo"] == "37526626"


def test_company_info_env_override(monkeypatch):
    monkeypatch.setenv("COMPANY_FULL_NAME", 'ООО «Тест»')
    monkeypatch.setenv("COMPANY_UNP", "123456789")
    monkeypatch.setenv("COMPANY_LEGAL_ADDRESS", "г. Минск")
    info = company_info()
    assert info["is_configured"] is True
    assert info["short_name"] == 'ООО «Тест»'
    assert info["postal_address"] == "г. Минск"
    assert info["unp"] == "123456789"
