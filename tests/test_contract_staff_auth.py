from autoplius.contract_staff import (
    check_contract_credentials,
    contract_credentials,
    parse_contract_users,
)


def test_parse_contract_users():
    parsed = parse_contract_users("dir_max:77997799, manager_alex:77997799;roman1067:10671067")
    assert parsed == {
        "dir_max": "77997799",
        "manager_alex": "77997799",
        "roman1067": "10671067",
    }


def test_default_contract_credentials(monkeypatch):
    monkeypatch.delenv("CONTRACT_USERS", raising=False)
    users = contract_credentials()
    assert users["dir_max"] == "77997799"
    assert users["manager_alex"] == "77997799"
    assert users["roman1067"] == "10671067"


def test_contract_credentials_env_override(monkeypatch):
    monkeypatch.setenv("CONTRACT_USERS", "only_one:secret")
    assert contract_credentials() == {"only_one": "secret"}


def test_check_contract_credentials(monkeypatch):
    monkeypatch.delenv("CONTRACT_USERS", raising=False)
    assert check_contract_credentials("dir_max", "77997799") == "dir_max"
    assert check_contract_credentials("DIR_MAX", "77997799") == "dir_max"
    assert check_contract_credentials("dir_max", "wrong") is None
    assert check_contract_credentials("nobody", "77997799") is None
