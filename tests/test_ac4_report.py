"""AC4：report 接口只列出得分 >= 90 的 active 合同对（测试断言）。

得分 70 的对（金额相差 1% 以内但不相同）、含 draft 的对、已软删除
的合同，均不列入。
"""

from __future__ import annotations

from conftest import mk_contract


def test_report_only_active_pairs_scored_ge_90(store):
    a = mk_contract(
        store, contract_no="HT-2026-0001", status="active",
        esign_status="signed", esign_flow_id="flow-fict-001",
    )
    b = mk_contract(
        store, contract_no="HT-2026-0002", status="active",
        esign_status="signed", esign_flow_id="flow-fict-001",
    )
    c = mk_contract(
        store, contract_no="HT-2026-0003", status="active",
        esign_status="signed", amount_fen=990_000,
    )
    d = mk_contract(
        store, contract_no="HT-2026-0004", status="draft",
        esign_flow_id="flow-fict-001",
    )
    pairs = store.duplicate_report()
    pair_ids = {(p["contract_a_id"], p["contract_b_id"]) for p in pairs}
    # a-b：esign 相同 100 分，列入；a-c：同企业重叠、金额差 1% 得 70 分，不列入；
    # b-c 同样 70 分，不列入；d 是 draft，不参与报告。
    assert pair_ids == {(a.id, b.id)}
    assert pairs[0]["score"] == 100


def test_report_includes_90_and_95_pairs(store):
    a = mk_contract(store, contract_no="HT-2026-0001", status="active")
    b = mk_contract(
        store, contract_no="ht20260001", company_id="comp-fict-002",
        status="active",
    )
    c = mk_contract(store, contract_no="HT-2026-0003", status="active")
    pairs = store.duplicate_report()
    pair_ids = {(p["contract_a_id"], p["contract_b_id"]) for p in pairs}
    # a-b：合同编号归一化相同 95 分；a-c：同企业重叠且金额相同 90 分。
    assert pair_ids == {(a.id, b.id), (a.id, c.id)}
    assert {p["score"] for p in pairs} == {95, 90}


def test_report_empty_when_no_active_pairs(store):
    mk_contract(store, contract_no="HT-2026-0001", status="draft")
    mk_contract(store, contract_no="HT-2026-0002", status="draft")
    assert store.duplicate_report() == []
