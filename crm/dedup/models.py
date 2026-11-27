"""合同、回款期次、会籍的数据模型（ClawHunt #2870，S2-CRM-039）。

业务表统一含 id（UUID）、org_id、site_id、created_at、created_by、
updated_at、deleted_at（软删除）；金额一律以「分」存整数。
本样品用内存仓储（见 store.py），不连真实库；只用虚构测试数据。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return str(uuid.uuid4())


@dataclass
class Contract:
    company_id: str
    contract_no: str
    amount_fen: int
    start_date: date
    end_date: date
    status: str = "draft"  # draft / active / terminated 等
    esign_status: str = "not_started"  # not_started / rejected / expired / revoked / signed
    esign_flow_id: str | None = None
    id: str = field(default_factory=_new_id)
    org_id: str = "org-fict-001"
    site_id: str = "site-fict-001"
    created_at: datetime = field(default_factory=_now)
    created_by: str = "user-fict-001"
    updated_at: datetime = field(default_factory=_now)
    deleted_at: datetime | None = None
    merged_into_id: str | None = None

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


@dataclass
class PaymentSchedule:
    contract_id: str
    period_no: int
    amount_fen: int
    received_fen: int = 0  # 已实收金额（分）；>0 表示该期次已有实收
    due_date: date | None = None
    id: str = field(default_factory=_new_id)
    org_id: str = "org-fict-001"
    site_id: str = "site-fict-001"
    created_at: datetime = field(default_factory=_now)
    created_by: str = "user-fict-001"
    updated_at: datetime = field(default_factory=_now)
    deleted_at: datetime | None = None

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    @property
    def has_receipt(self) -> bool:
        return self.received_fen > 0


@dataclass
class Membership:
    contract_id: str
    company_id: str
    member_name: str = "虚构会员"
    id: str = field(default_factory=_new_id)
    org_id: str = "org-fict-001"
    site_id: str = "site-fict-001"
    created_at: datetime = field(default_factory=_now)
    created_by: str = "user-fict-001"
    updated_at: datetime = field(default_factory=_now)
    deleted_at: datetime | None = None

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None
