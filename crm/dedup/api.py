"""判重与合并接口（ClawHunt #2870，S2-CRM-039）。

- POST /api/crm/contracts/duplicate-check：新建前提示
- GET /api/crm/contracts/duplicates/report：已签疑似重复报告（只读）
- GET /api/crm/contracts/{id}/duplicates：某份合同的重复候选
- POST /api/crm/contracts/merge：草稿合同合并（权限码 crm.contract.merge）

注意：report 路由须在 {id}/duplicates 之前注册，否则 "duplicates"
会被当成合同 id。create_app 接受外部传入的仓储，便于测试注入。
"""

from __future__ import annotations

from datetime import date

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from .contract import REPORT_MIN_SCORE
from .permissions import require_merge_permission
from .store import InMemoryStore, MergeError


class DuplicateCheckRequest(BaseModel):
    company_id: str
    contract_no: str
    amount_fen: int = Field(ge=0)
    start_date: date
    end_date: date
    esign_flow_id: str | None = None


class MergeRequest(BaseModel):
    master_id: str
    duplicate_ids: list[str] = Field(min_length=1, max_length=3)
    confirm: bool = False


def create_app(store: InMemoryStore | None = None) -> FastAPI:
    app = FastAPI(title="crm-dedup-sample")
    _store = store or InMemoryStore()
    app.state.store = _store

    @app.post("/api/crm/contracts/duplicate-check")
    def duplicate_check(body: DuplicateCheckRequest):
        return {
            "duplicates": _store.duplicate_check(
                company_id=body.company_id,
                contract_no=body.contract_no,
                amount_fen=body.amount_fen,
                start_date=body.start_date,
                end_date=body.end_date,
                esign_flow_id=body.esign_flow_id,
            )
        }

    @app.get("/api/crm/contracts/duplicates/report")
    def duplicate_report():
        return {
            "min_score": REPORT_MIN_SCORE,
            "pairs": _store.duplicate_report(),
        }

    @app.get("/api/crm/contracts/{contract_id}/duplicates")
    def contract_duplicates(contract_id: str):
        if _store.get_contract(contract_id) is None:
            raise HTTPException(status_code=404, detail="合同不存在")
        return {"duplicates": _store.find_duplicates(contract_id)}

    @app.post("/api/crm/contracts/merge")
    def merge_contracts(
        body: MergeRequest, _: None = Depends(require_merge_permission)
    ):
        try:
            return _store.merge_contracts(
                master_id=body.master_id,
                duplicate_ids=body.duplicate_ids,
                confirm=body.confirm,
            )
        except MergeError as exc:
            raise HTTPException(
                status_code=exc.status_code,
                detail={"code": exc.code, "message": exc.message},
            ) from exc

    return app


app = create_app()
