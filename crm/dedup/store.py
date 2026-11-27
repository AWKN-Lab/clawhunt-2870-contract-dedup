"""内存仓储：重复识别、草稿合并、疑似重复报告（ClawHunt #2870）。

合并事务（任务原文）：
- 会籍表 contract_id 改指向主记录；
- 回款计划在主记录无期次时整体迁到主记录，主记录已有期次时被合并
  合同的期次软删除，任一期次已有实收则返回 409；
- 被合并记录写 merged_into_id 并软删除。
- 合并后调用 record_change（action=merge），未合入时用空实现桩。

本样品的 record_change 是内存桩：把变更记进 change_log 列表，
供测试断言“合并后调用过 record_change”；未合入核心系统时不发
任何外部调用。S2-IAM 未接线时权限用请求头桩核对（见 permissions.py）。
"""

from __future__ import annotations

from datetime import datetime, timezone

from .contract import (
    MERGE_ALLOWED_ESIGN_STATUSES,
    MERGE_CONFLICT_CODE,
    MERGE_SCHEDULE_RECEIVED_CODE,
    REPORT_MIN_SCORE,
    score_pair,
)
from .models import Contract, Membership, PaymentSchedule


def _now() -> datetime:
    return datetime.now(timezone.utc)


class MergeError(Exception):
    """合并被拒：带 HTTP 状态码与业务错误码。"""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


class InMemoryStore:
    """内存仓储：合同、回款期次、会籍、变更日志。"""

    def __init__(self) -> None:
        self.contracts: dict[str, Contract] = {}
        self.schedules: dict[str, PaymentSchedule] = {}
        self.memberships: dict[str, Membership] = {}
        self.change_log: list[dict] = []

    # -- 写入 ---------------------------------------------------------
    def add_contract(self, contract: Contract) -> Contract:
        self.contracts[contract.id] = contract
        return contract

    def add_schedule(self, schedule: PaymentSchedule) -> PaymentSchedule:
        self.schedules[schedule.id] = schedule
        return schedule

    def add_membership(self, membership: Membership) -> Membership:
        self.memberships[membership.id] = membership
        return membership

    # -- 读取 ---------------------------------------------------------
    def get_contract(self, contract_id: str) -> Contract | None:
        contract = self.contracts.get(contract_id)
        if contract is None or contract.is_deleted:
            return None
        return contract

    def live_contracts(self) -> list[Contract]:
        return [c for c in self.contracts.values() if not c.is_deleted]

    def schedules_of(self, contract_id: str) -> list[PaymentSchedule]:
        return [
            s
            for s in self.schedules.values()
            if s.contract_id == contract_id and not s.is_deleted
        ]

    # -- record_change 桩 ---------------------------------------------
    def record_change(self, action: str, **kwargs) -> None:
        """变更记录桩：未合入核心系统时只记内存日志，不发外部调用。"""
        self.change_log.append({"action": action, **kwargs})

    # -- 重复识别 -----------------------------------------------------
    def find_duplicates(self, contract_id: str) -> list[dict]:
        """某份合同的重复候选：得分 > 0，按得分从高到低。"""
        target = self.get_contract(contract_id)
        if target is None:
            return []
        hits = []
        for other in self.live_contracts():
            if other.id == target.id:
                continue
            score, rule = score_pair(target, other)
            if score > 0:
                hits.append(
                    {
                        "contract_id": other.id,
                        "contract_no": other.contract_no,
                        "score": score,
                        "rule": rule,
                    }
                )
        hits.sort(key=lambda h: -h["score"])
        return hits

    def duplicate_check(
        self,
        company_id: str,
        contract_no: str,
        amount_fen: int,
        start_date,
        end_date,
        esign_flow_id: str | None = None,
    ) -> list[dict]:
        """新建前提示：拿候选字段与库内合同逐一打分，得分 > 0 即列出。"""
        candidate = Contract(
            company_id=company_id,
            contract_no=contract_no,
            amount_fen=amount_fen,
            start_date=start_date,
            end_date=end_date,
            esign_flow_id=esign_flow_id,
        )
        hits = []
        for other in self.live_contracts():
            score, rule = score_pair(candidate, other)
            if score > 0:
                hits.append(
                    {
                        "contract_id": other.id,
                        "contract_no": other.contract_no,
                        "score": score,
                        "rule": rule,
                    }
                )
        hits.sort(key=lambda h: -h["score"])
        return hits

    # -- 疑似重复报告 -------------------------------------------------
    def duplicate_report(self) -> list[dict]:
        """只读报告：status=active 且两两得分 >= 90 的合同对，供人工核对。

        只列 active 合同对；draft / terminated / 已软删除均不列入；
        得分 70 的对（金额相差 1% 以内但不相同）不列入。
        """
        active = [c for c in self.live_contracts() if c.status == "active"]
        pairs = []
        for i, a in enumerate(active):
            for b in active[i + 1 :]:
                score, rule = score_pair(a, b)
                if score >= REPORT_MIN_SCORE:
                    pairs.append(
                        {
                            "contract_a_id": a.id,
                            "contract_b_id": b.id,
                            "score": score,
                            "rule": rule,
                        }
                    )
        pairs.sort(key=lambda p: -p["score"])
        return pairs

    # -- 草稿合并 -----------------------------------------------------
    def merge_contracts(
        self, master_id: str, duplicate_ids: list[str], confirm: bool
    ) -> dict:
        """合并草稿合同。成功返回合并结果；违规抛 MergeError。

        校验顺序：confirm -> 个数 1-3 -> 记录存在 -> 全部 draft 且
        esign_status 在允许集合内 -> 被合并期次无实收。
        任一校验失败都不改动任何数据（先校验、后落库）。
        """
        if confirm is not True:
            raise MergeError(400, "CRM_MERGE_CONFIRM_REQUIRED", "合并须传 confirm=true")
        if not 1 <= len(duplicate_ids) <= 3:
            raise MergeError(
                400,
                "CRM_MERGE_COUNT_INVALID",
                "duplicate_ids 须为 1-3 个",
            )
        if master_id in duplicate_ids:
            raise MergeError(
                400, "CRM_MERGE_MASTER_IN_DUPLICATES", "主记录不能同时列为被合并记录"
            )
        master = self.get_contract(master_id)
        if master is None:
            raise MergeError(404, "CRM_CONTRACT_NOT_FOUND", "主记录不存在")
        duplicates: list[Contract] = []
        for dup_id in duplicate_ids:
            dup = self.get_contract(dup_id)
            if dup is None:
                raise MergeError(404, "CRM_CONTRACT_NOT_FOUND", "被合并记录不存在")
            duplicates.append(dup)

        # 全部记录须 status=draft 且 esign_status 在允许集合内，否则 409。
        for record in [master, *duplicates]:
            if (
                record.status != "draft"
                or record.esign_status not in MERGE_ALLOWED_ESIGN_STATUSES
            ):
                raise MergeError(
                    409,
                    MERGE_CONFLICT_CODE,
                    "只允许合并全部为草稿且未签署的合同",
                )

        # 任一被合并期次已有实收则返回 409（主记录已有期次不受影响）。
        dup_schedules = [
            s for dup in duplicates for s in self.schedules_of(dup.id)
        ]
        if any(s.has_receipt for s in dup_schedules):
            raise MergeError(
                409,
                MERGE_SCHEDULE_RECEIVED_CODE,
                "被合并合同的期次已有实收，无法合并",
            )

        # 落库：会籍改指向主记录；期次整体迁移或软删除；被合并记录软删除。
        now = _now()
        master_schedules = self.schedules_of(master.id)
        for membership in self.memberships.values():
            if (
                not membership.is_deleted
                and membership.contract_id in {d.id for d in duplicates}
            ):
                membership.contract_id = master.id
                membership.updated_at = now
        if master_schedules:
            for schedule in dup_schedules:
                schedule.deleted_at = now
                schedule.updated_at = now
        else:
            for schedule in dup_schedules:
                schedule.contract_id = master.id
                schedule.updated_at = now
        merged_ids = []
        for dup in duplicates:
            dup.merged_into_id = master.id
            dup.deleted_at = now
            dup.updated_at = now
            merged_ids.append(dup.id)
        self.record_change(
            action="merge",
            master_id=master.id,
            merged_ids=merged_ids,
            moved_schedule_ids=[s.id for s in dup_schedules]
            if not master_schedules
            else [],
            deleted_schedule_ids=[s.id for s in dup_schedules]
            if master_schedules
            else [],
        )
        return {
            "master_id": master.id,
            "merged_ids": merged_ids,
            "moved_schedule_ids": [s.id for s in dup_schedules]
            if not master_schedules
            else [],
            "deleted_schedule_ids": [s.id for s in dup_schedules]
            if master_schedules
            else [],
        }
