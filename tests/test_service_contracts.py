from pathlib import Path

from scraper.db import (
    create_service_contract,
    delete_service_contract,
    get_service_contract,
    init_db,
    list_service_contracts,
    update_service_contract,
)


def test_service_contracts_crud(tmp_path: Path):
    db = tmp_path / "contracts.db"
    init_db(db)

    created = create_service_contract(
        db,
        contract_number="П100926",
        client_name="Иванов Иван Иванович",
        amount="1000",
        payload={"contractNumber": "П100926", "amount": "1000", "clientName": "Иванов Иван Иванович"},
        created_by="admin",
    )
    assert created["id"] >= 1
    assert created["payload"]["contractNumber"] == "П100926"

    listed = list_service_contracts(db)
    assert len(listed) == 1
    assert listed[0]["contract_number"] == "П100926"
    assert "payload" not in listed[0]

    got = get_service_contract(db, created["id"])
    assert got is not None
    assert got["client_name"] == "Иванов Иван Иванович"
    assert got["payload"]["amount"] == "1000"

    updated = update_service_contract(
        db,
        created["id"],
        contract_number="П100927",
        client_name="Петров",
        amount="1500",
        payload={"contractNumber": "П100927", "amount": "1500"},
    )
    assert updated is not None
    assert updated["contract_number"] == "П100927"
    assert updated["payload"]["amount"] == "1500"

    assert delete_service_contract(db, created["id"]) is True
    assert get_service_contract(db, created["id"]) is None
    assert list_service_contracts(db) == []
