"""AC2：对 esign_status=signed 的合同发起合并返回 409，数据无改动（测试断言）。
"""

from __future__ import annotations

import copy

import pytest
from conftest import mk_contract, mk_membership, mk_schedule
from crm.dedup.contract import MERGE_CONFLICT_CODE
from crm.dedup.store import MergeError


def _snapshot(store):
    return {
        "contracts": copy.deepcopy(store.contracts),
        "schedules": copy.deepcopy(store.schedules),
        "memberships": copy.deepcopy(store.memberships),
        "change_log": copy.deepcopy(store.change_log),
    }


def test_merge_signed_duplicate_returns_409_and_no_change(store):
    master = mk_contract(store, contract_no="HT-2026-0001")
    signed = mk_contract(
        store, contract_no="HT-2026-0002", esign_status="signed"
    )
    mk_schedule(store, signed.id, period_no=1)
    mk_membership(store, signed.id)
    before = _snapshot(store)
    with pytest.raises(MergeError) as excinfo:
        store.merge_contracts(
            master_id=master.id,
            duplicate_ids=[signed.id],
            confirm=True,
        )
    assert excinfo.value.status_code == 409
    assert excinfo.value.code == MERGE_CONFLICT_CODE
    after = _snapshot(store)
    assert after == before


def test_merge_signed_master_returns_409_and_no_change(store):
    master = mk_contract(
        store, contract_no="HT-2026-0001", esign_status="signed"
    )
    dup = mk_contract(store, contract_no="HT-2026-0002")
    before = _snapshot(store)
    with pytest.raises(MergeError) as excinfo:
        store.merge_contracts(
            master_id=master.id, duplicate_ids=[dup.id], confirm=True
        )
    assert excinfo.value.status_code == 409
    assert excinfo.value.code == MERGE_CONFLICT_CODE
    assert _snapshot(store) == before


def test_merge_active_status_returns_409(store):
    master = mk_contract(store, contract_no="HT-2026-0001")
    active = mk_contract(
        store, contract_no="HT-2026-0002", status="active"
    )
    with pytest.raises(MergeError) as excinfo:
        store.merge_contracts(
            master_id=master.id, duplicate_ids=[active.id], confirm=True
        )
    assert excinfo.value.status_code == 409
    assert excinfo.value.code == MERGE_CONFLICT_CODE


@pytest.mark.parametrize(
    "esign_status", ["not_started", "rejected", "expired", "revoked"]
)
def test_merge_allowed_esign_statuses(store, esign_status):
    master = mk_contract(store, contract_no="HT-2026-0001")
    dup = mk_contract(
        store, contract_no="HT-2026-0002", esign_status=esign_status
    )
    result = store.merge_contracts(
        master_id=master.id, duplicate_ids=[dup.id], confirm=True
    )
    assert result["merged_ids"] == [dup.id]
    assert store.contracts[dup.id].merged_into_id == master.id
    assert store.contracts[dup.id].deleted_at is not None
