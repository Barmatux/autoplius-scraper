import os

from autoplius.company_info import company_info


def test_company_info_empty_by_default(monkeypatch):
    for key in list(os.environ):
        if key.startswith("COMPANY_"):
            monkeypatch.delenv(key, raising=False)
    info = company_info()
    assert info["is_configured"] is False
    assert info["full_name"] == ""


def test_company_info_configured(monkeypatch):
    monkeypatch.setenv("COMPANY_FULL_NAME", 'ООО «Тест»')
    monkeypatch.setenv("COMPANY_UNP", "123456789")
    monkeypatch.setenv("COMPANY_LEGAL_ADDRESS", "г. Минск")
    info = company_info()
    assert info["is_configured"] is True
    assert info["short_name"] == 'ООО «Тест»'
    assert info["postal_address"] == "г. Минск"
