"""重复合同识别：判重规则（ClawHunt #2870，S2-CRM-039）。

规则（任务原文，见 README 规则表）：
- esign_flow_id 相同：100 分
- 合同编号去连字符、转大写后相同：95 分
- 同一企业、期限重叠且 amount_fen 相同：90 分
- 同一企业、期限重叠且金额相差不超过 1%：70 分
  （整数运算：差额 x 100 <= 较大金额）

只用虚构测试数据；本模块不含任何真实个人信息或企业信息。
"""

from __future__ import annotations

from datetime import date

RULE_ESIGN_FLOW_ID = 100
RULE_CONTRACT_NO = 95
RULE_SAME_COMPANY_OVERLAP_SAME_AMOUNT = 90
RULE_SAME_COMPANY_OVERLAP_AMOUNT_WITHIN_1PCT = 70

# 已签疑似重复报告只列出得分 >= 90 的 active 合同对。
REPORT_MIN_SCORE = 90

# 合并只允许全部记录 status=draft 且 esign_status 为以下四种之一。
MERGE_ALLOWED_ESIGN_STATUSES = frozenset(
    {"not_started", "rejected", "expired", "revoked"}
)
MERGE_CONFLICT_CODE = "CRM_MERGE_CONTRACT_SIGNED"
MERGE_SCHEDULE_RECEIVED_CODE = "CRM_MERGE_SCHEDULE_RECEIVED"
MERGE_PERMISSION_CODE = "crm.contract.merge"

RULE_NAMES = {
    RULE_ESIGN_FLOW_ID: "esign_flow_id 相同",
    RULE_CONTRACT_NO: "合同编号去连字符、转大写后相同",
    RULE_SAME_COMPANY_OVERLAP_SAME_AMOUNT: "同一企业、期限重叠且 amount_fen 相同",
    RULE_SAME_COMPANY_OVERLAP_AMOUNT_WITHIN_1PCT: "同一企业、期限重叠且金额相差不超过 1%",
}


def normalize_contract_no(contract_no: str | None) -> str:
    """合同编号归一化：去连字符、转大写、去首尾空白。"""
    if not contract_no:
        return ""
    return contract_no.replace("-", "").strip().upper()


def periods_overlap(
    a_start: date, a_end: date, b_start: date, b_end: date
) -> bool:
    """期限重叠判定：闭区间，a_start <= b_end 且 b_start <= a_end。"""
    return a_start <= b_end and b_start <= a_end


def score_pair(a, b) -> tuple[int, str | None]:
    """给两份合同打分，返回 (得分, 命中规则名)。

    a、b 须含 company_id、contract_no、esign_flow_id、amount_fen、
    start_date、end_date 六个属性（见 crm/dedup/models.py 的 Contract）。
    规则按分值从高到低依次判定，命中即返回；都不命中返回 (0, None)。
    空合同编号不参与 95 分规则（两份空编号不算重复）；
    空 esign_flow_id 不参与 100 分规则。
    """
    if a.esign_flow_id and a.esign_flow_id == b.esign_flow_id:
        return RULE_ESIGN_FLOW_ID, RULE_NAMES[RULE_ESIGN_FLOW_ID]
    norm_a = normalize_contract_no(a.contract_no)
    norm_b = normalize_contract_no(b.contract_no)
    if norm_a and norm_a == norm_b:
        return RULE_CONTRACT_NO, RULE_NAMES[RULE_CONTRACT_NO]
    if a.company_id == b.company_id and periods_overlap(
        a.start_date, a.end_date, b.start_date, b.end_date
    ):
        if a.amount_fen == b.amount_fen:
            return (
                RULE_SAME_COMPANY_OVERLAP_SAME_AMOUNT,
                RULE_NAMES[RULE_SAME_COMPANY_OVERLAP_SAME_AMOUNT],
            )
        diff = abs(a.amount_fen - b.amount_fen)
        larger = max(a.amount_fen, b.amount_fen)
        # 整数运算：差额 x 100 <= 较大金额（不做浮点除法）。
        if larger > 0 and diff * 100 <= larger:
            return (
                RULE_SAME_COMPANY_OVERLAP_AMOUNT_WITHIN_1PCT,
                RULE_NAMES[RULE_SAME_COMPANY_OVERLAP_AMOUNT_WITHIN_1PCT],
            )
    return 0, None
