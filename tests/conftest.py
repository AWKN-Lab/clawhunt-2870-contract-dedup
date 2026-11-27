"""测试共用夹具：只用虚构数据（虚构企业、虚构合同编号）。"""

from __future__ import annotations

from datetime import date

import pytest

from crm.dedup.models import Contract, Membership, PaymentSchedule
from crm.dedup.store import InMemoryStore

D1 = date(2026, 1, 1)
D2 = date(2026, 12, 31)


@pytest.fixture
def store() -> InMemoryStore:
    return InMemoryStore()


def mk_contract(
    store: InMemoryStore,
    company_id: str = "comp-fict-001",
    contract_no: str = "HT-2026-0001",
    amount_fen: int = 1_000_000,
    start_date: date = D1,
    end_date: date = D2,
    status: str = "draft",
    esign_status: str = "not_started",
    esign_flow_id: str | None = None,
) -> Contract:
    contract = Contract(
        company_id=company_id,
        contract_no=contract_no,
        amount_fen=amount_fen,
        start_date=start_date,
        end_date=end_date,
        status=status,
        esign_status=esign_status,
        esign_flow_id=esign_flow_id,
    )
    return store.add_contract(contract)


def mk_schedule(
    store: InMemoryStore,
    contract_id: str,
    period_no: int = 1,
    amount_fen: int = 500_000,
    received_fen: int = 0,
) -> PaymentSchedule:
    return store.add_schedule(
        PaymentSchedule(
            contract_id=contract_id,
            period_no=period_no,
            amount_fen=amount_fen,
            received_fen=received_fen,
        )
    )


def mk_membership(
    store: InMemoryStore, contract_id: str, company_id: str = "comp-fict-001"
) -> Membership:
    return store.add_membership(
        Membership(contract_id=contract_id, company_id=company_id)
    )
