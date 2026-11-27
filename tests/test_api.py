"""接口端到端测试：四个接口 + 权限码 + 409 透传。"""

from __future__ import annotations

from fastapi.testclient import TestClient

from conftest import mk_contract, mk_schedule
from crm.dedup.api import create_app
from crm.dedup.store import InMemoryStore

PERM = {"X-Permissions": "crm.contract.merge"}
BODY = {
    "company_id": "comp-fict-001",
    "contract_no": "HT-2026-0003",
    "amount_fen": 1_000_000,
    "start_date": "2026-01-01",
    "end_date": "2026-12-31",
    "esign_flow_id": "flow-fict-001",
}


def _client(store=None):
    store = store or InMemoryStore()
    return TestClient(create_app(store)), store


def test_duplicate_check_endpoint():
    client, store = _client()
    mk_contract(store, contract_no="HT-2026-0001", esign_flow_id="flow-fict-001")
    resp = client.post("/api/crm/contracts/duplicate-check", json=BODY)
    assert resp.status_code == 200
    assert resp.json()["duplicates"][0]["score"] == 100


def test_contract_duplicates_endpoint():
    client, store = _client()
    a = mk_contract(store, contract_no="HT-2026-0001")
    mk_contract(store, contract_no="HT-2026-0002", amount_fen=990_000)
    resp = client.get(f"/api/crm/contracts/{a.id}/duplicates")
    assert resp.status_code == 200
    assert resp.json()["duplicates"][0]["score"] == 70
    assert client.get("/api/crm/contracts/no-such-id/duplicates").status_code == 404


def test_report_endpoint_only_ge_90():
    client, store = _client()
    a = mk_contract(
        store, contract_no="HT-2026-0001", status="active",
        esign_flow_id="flow-fict-001",
    )
    b = mk_contract(
        store, contract_no="HT-2026-0002", status="active",
        esign_flow_id="flow-fict-001",
    )
    mk_contract(store, contract_no="HT-2026-0003", status="active",
                amount_fen=990_000)
    resp = client.get("/api/crm/contracts/duplicates/report")
    assert resp.status_code == 200
    data = resp.json()
    assert data["min_score"] == 90
    assert len(data["pairs"]) == 1
    assert {data["pairs"][0]["contract_a_id"], data["pairs"][0]["contract_b_id"]} == {a.id, b.id}


def test_merge_endpoint_success_and_record_change():
    client, store = _client()
    master = mk_contract(store, contract_no="HT-2026-0001")
    dup = mk_contract(store, contract_no="HT-2026-0002")
    mk_schedule(store, dup.id, period_no=1)
    resp = client.post(
        "/api/crm/contracts/merge",
        json={"master_id": master.id, "duplicate_ids": [dup.id], "confirm": True},
        headers=PERM,
    )
    assert resp.status_code == 200
    assert resp.json()["merged_ids"] == [dup.id]
    assert store.change_log[-1]["action"] == "merge"


def test_merge_endpoint_signed_returns_409():
    client, store = _client()
    master = mk_contract(store, contract_no="HT-2026-0001")
    signed = mk_contract(
        store, contract_no="HT-2026-0002", esign_status="signed"
    )
    resp = client.post(
        "/api/crm/contracts/merge",
        json={"master_id": master.id, "duplicate_ids": [signed.id], "confirm": True},
        headers=PERM,
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "CRM_MERGE_CONTRACT_SIGNED"


def test_merge_endpoint_requires_permission_code():
    client, store = _client()
    master = mk_contract(store, contract_no="HT-2026-0001")
    dup = mk_contract(store, contract_no="HT-2026-0002")
    resp = client.post(
        "/api/crm/contracts/merge",
        json={"master_id": master.id, "duplicate_ids": [dup.id], "confirm": True},
    )
    assert resp.status_code == 403
