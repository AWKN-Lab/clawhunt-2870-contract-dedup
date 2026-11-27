"""权限码核对桩（ClawHunt #2870，S2-CRM-039）。

任务要求合并接口的权限码为 crm.contract.merge。
S2-IAM（身份、角色与数据范围）尚未接线，本样品用请求头桩核对：
调用方在 X-Permissions 头里传逗号分隔的权限码列表，含
crm.contract.merge 才放行，否则 403。

合入核心系统时把本桩换成 S2-IAM 的真实权限校验，接口签名不变。
"""

from __future__ import annotations

from fastapi import Header, HTTPException

from .contract import MERGE_PERMISSION_CODE


def require_merge_permission(
    x_permissions: str | None = Header(default=None),
) -> None:
    granted = {
        code.strip() for code in (x_permissions or "").split(",") if code.strip()
    }
    if MERGE_PERMISSION_CODE not in granted:
        raise HTTPException(
            status_code=403,
            detail=f"缺少权限码 {MERGE_PERMISSION_CODE}",
        )
