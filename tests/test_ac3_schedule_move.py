"""AC3：主记录无期次时，被合并草稿合同的回款期次整体迁入主记录（测试断言）。

另覆盖任务原文的另一半：主记录已有期次时，被合并合同的期次软删除；
任一期次已有实收则返回 409。
"""

from __future__ import annotations

import pytest
from conftest import mk_contract, mk_membership, mk_schedule
from crm.dedup.contract import MERGE_SCHEDULE_RECEIVED_CODE
from crm.dedup.store import MergeError


def test_master_without_schedules_receives_all(store):
    master = mk_contract(store, contract_no="HT-2026-0001")
    dup = mk_contract(store, contract_no="HT-2026-0002")
    s1 = mk_schedule(store, dup.id, period_no=1, amount_fen=500_000)
    s2 = mk_schedule(store, dup.id, period_no=2, amount_fen=500_000)
    mk_membership(store, dup.id)
    result = store.merge_contracts(
        master_id=master.id, duplicate_ids=[dup.id], confirm=True
    )
    assert result["moved_schedule_ids"] == [s1.id, s2.id]
    assert result["deleted_schedule_ids"] == []
    moved = store.schedules_of(master.id)
    assert {s.id for s in moved} == {s1.id, s2.id}
    assert [s.period_no for s in sorted(moved, key=lambda s: s.period_no)] == [1, 2]
    assert all(s.amount_fen == 500_000 for s in moved)
    assert store.schedules_of(dup.id) == []
    # 会籍改指向主记录；被合并记录写 merged_into_id 并软删除。
    assert all(
        m.contract_id == master.id for m in store.memberships.values()
    )
    assert store.contracts[dup.id].merged_into_id == master.id
    assert store.contracts[dup.id].deleted_at is not None
    # 合并后调用 record_change（action=merge）。
    assert store.change_log[-1]["action"] == "merge"
    assert store.change_log[-1]["master_id"] == master.id
    assert store.change_log[-1]["merged_ids"] == [dup.id]


def test_master_with_schedules_soft_deletes_duplicate_schedules(store):
    master = mk_contract(store, contract_no="HT-2026-0001")
    mk_schedule(store, master.id, period_no=1, amount_fen=1_000_000)
    dup = mk_contract(store, contract_no="HT-2026-0002")
    s1 = mk_schedule(store, dup.id, period_no=1, amount_fen=500_000)
    result = store.merge_contracts(
        master_id=master.id, duplicate_ids=[dup.id], confirm=True
    )
    assert result["moved_schedule_ids"] == []
    assert result["deleted_schedule_ids"] == [s1.id]
    assert len(store.schedules_of(master.id)) == 1
    assert store.schedules[s1.id].deleted_at is not None


def test_schedule_with_receipt_returns_409(store):
    master = mk_contract(store, contract_no="HT-2026-0001")
    dup = mk_contract(store, contract_no="HT-2026-0002")
    mk_schedule(store, dup.id, period_no=1, received_fen=100_000)
    with pytest.raises(MergeError) as excinfo:
        store.merge_contracts(
            master_id=master.id, duplicate_ids=[dup.id], confirm=True
        )
    assert excinfo.value.status_code == 409
    assert excinfo.value.code == MERGE_SCHEDULE_RECEIVED_CODE
    assert store.contracts[dup.id].deleted_at is None
    assert store.schedules_of(dup.id) != []


def test_merge_requires_confirm_true(store):
    master = mk_contract(store, contract_no="HT-2026-0001")
    dup = mk_contract(store, contract_no="HT-2026-0002")
    with pytest.raises(MergeError) as excinfo:
        store.merge_contracts(
            master_id=master.id, duplicate_ids=[dup.id], confirm=False
        )
    assert excinfo.value.status_code == 400
    assert store.contracts[dup.id].deleted_at is None
