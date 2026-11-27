"""AC1：4 条判重规则各有命中与不命中用例（含金额相差 1% 与 1.01% 的边界）。

边界口径以任务原文的整数公式为准：差额 x 100 <= 较大金额。
金额 1,000,000 分时：差 10,000 分（恰好 1%）命中 70 分；
差 10,100 分（相对较大金额 1.01%）不命中。注意公式以较大金额为
分母，1.01% 的表述只在“较小金额低于较大金额”方向上精确成立。
"""

from __future__ import annotations

from datetime import date

from conftest import D1, D2, mk_contract
from crm.dedup.contract import score_pair
from crm.dedup.models import Contract


def _candidate(**kwargs) -> Contract:
    base = dict(
        company_id="comp-fict-001",
        contract_no="HT-2026-0001",
        amount_fen=1_000_000,
        start_date=D1,
        end_date=D2,
    )
    base.update(kwargs)
    return Contract(**base)


# -- 规则 1：esign_flow_id 相同 100 分 --------------------------------
def test_rule100_hit_same_esign_flow_id():
    a = _candidate(esign_flow_id="flow-fict-001")
    b = _candidate(
        contract_no="HT-2026-9999",
        company_id="comp-fict-002",
        esign_flow_id="flow-fict-001",
    )
    score, rule = score_pair(a, b)
    assert score == 100
    assert "esign_flow_id" in rule


def test_rule100_miss_different_esign_flow_id():
    a = _candidate(esign_flow_id="flow-fict-001")
    b = _candidate(
        contract_no="HT-2026-9999",
        company_id="comp-fict-002",
        esign_flow_id="flow-fict-002",
    )
    assert score_pair(a, b) == (0, None)


def test_rule100_miss_empty_esign_flow_id():
    a = _candidate(esign_flow_id=None)
    b = _candidate(esign_flow_id=None)
    assert score_pair(a, b)[0] == 95  # 合同编号相同，只命中 95 分规则


# -- 规则 2：合同编号去连字符、转大写后相同 95 分 --------------------
def test_rule95_hit_normalized_contract_no():
    a = _candidate(contract_no="HT-2026-0001")
    b = _candidate(contract_no="ht20260001", company_id="comp-fict-002")
    score, rule = score_pair(a, b)
    assert score == 95
    assert "合同编号" in rule


def test_rule95_miss_different_contract_no():
    a = _candidate(contract_no="HT-2026-0001")
    b = _candidate(contract_no="HT-2026-0002", company_id="comp-fict-002")
    assert score_pair(a, b) == (0, None)


def test_rule95_miss_empty_contract_no():
    a = _candidate(contract_no="")
    b = _candidate(contract_no="", company_id="comp-fict-002")
    assert score_pair(a, b) == (0, None)


# -- 规则 3：同一企业、期限重叠且 amount_fen 相同 90 分 --------------
def test_rule90_hit_same_company_overlap_same_amount():
    a = _candidate()
    b = _candidate(
        contract_no="HT-2026-0002",
        start_date=date(2026, 6, 1),
        end_date=date(2027, 5, 31),
    )
    score, _ = score_pair(a, b)
    assert score == 90


def test_rule90_miss_different_company():
    a = _candidate()
    b = _candidate(contract_no="HT-2026-0002", company_id="comp-fict-002")
    assert score_pair(a, b) == (0, None)


def test_rule90_miss_no_overlap():
    a = _candidate()
    b = _candidate(
        contract_no="HT-2026-0002",
        start_date=date(2027, 1, 1),
        end_date=date(2027, 12, 31),
    )
    assert score_pair(a, b) == (0, None)


def test_rule90_boundary_adjacent_periods_overlap_on_shared_day():
    # 闭区间：前一份到期日当天起租算重叠（共享同一天）。
    a = _candidate()
    b = _candidate(
        contract_no="HT-2026-0002",
        start_date=date(2026, 12, 31),
        end_date=date(2027, 12, 31),
    )
    assert score_pair(a, b)[0] == 90


# -- 规则 4：同一企业、期限重叠且金额相差不超过 1% 得 70 分 ---------
def test_rule70_hit_diff_exactly_1pct():
    a = _candidate(amount_fen=1_000_000)
    b = _candidate(contract_no="HT-2026-0002", amount_fen=990_000)
    score, rule = score_pair(a, b)
    assert score == 70
    assert "1%" in rule


def test_rule70_hit_diff_below_1pct():
    a = _candidate(amount_fen=1_000_000)
    b = _candidate(contract_no="HT-2026-0002", amount_fen=999_000)
    assert score_pair(a, b)[0] == 70


def test_rule70_miss_diff_1_01pct():
    # 差 10,100 分：10_100 x 100 = 1_010_000 > 较大金额 1_000_000，不命中。
    a = _candidate(amount_fen=1_000_000)
    b = _candidate(contract_no="HT-2026-0002", amount_fen=989_900)
    assert score_pair(a, b) == (0, None)


def test_rule70_miss_diff_over_1pct_no_overlap():
    a = _candidate(amount_fen=1_000_000)
    b = _candidate(
        contract_no="HT-2026-0002",
        amount_fen=990_000,
        start_date=date(2027, 1, 1),
        end_date=date(2027, 12, 31),
    )
    assert score_pair(a, b) == (0, None)


def test_rule_priority_esign_beats_contract_no():
    a = _candidate(esign_flow_id="flow-fict-001")
    b = _candidate(esign_flow_id="flow-fict-001")
    assert score_pair(a, b)[0] == 100


def test_duplicate_check_lists_hits_sorted(store):
    mk_contract(store, contract_no="HT-2026-0001", esign_flow_id="flow-fict-001")
    mk_contract(store, contract_no="HT-2026-0002", amount_fen=990_000)
    hits = store.duplicate_check(
        company_id="comp-fict-001",
        contract_no="HT-2026-0003",
        amount_fen=1_000_000,
        start_date=D1,
        end_date=D2,
        esign_flow_id="flow-fict-001",
    )
    assert [h["score"] for h in hits] == [100, 70]
