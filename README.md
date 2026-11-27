# clawhunt-2870-contract-dedup

ClawHunt #2870（S2-CRM-039）最小可验证样品：会员空间平台 · 重复合同识别、
草稿合同合并与已签疑似重复报告。

交付物对应任务原文：`crm/dedup/contract.py`、判重与合并接口、疑似重复
报告接口、pytest 用例、README 规则表。

## 判重规则表

| 得分 | 规则 | 实现位置 |
|---|---|---|
| 100 | esign_flow_id 相同 | `crm/dedup/contract.py` `score_pair` |
| 95 | 合同编号去连字符、转大写后相同 | 同上（空编号不参与） |
| 90 | 同一企业、期限重叠且 amount_fen 相同 | 同上 |
| 70 | 同一企业、期限重叠且金额相差不超过 1% | 同上（整数运算：差额 × 100 ≤ 较大金额） |

规则按分值从高到低依次判定，命中即返回；都不命中得 0 分。
期限重叠是闭区间：`a_start <= b_end 且 b_start <= a_end`。
金额字段一律以「分」存整数；1% 判定不做浮点除法。

边界说明：1% 的口径以整数公式为准，公式以较大金额为分母。
金额 1,000,000 分时，差 10,000 分（恰好 1%）得 70 分；
差 10,100 分（相对较大金额 1.01%）不得分。测试见
`tests/test_ac1_rules.py`。

## 接口

| 接口 | 说明 |
|---|---|
| `POST /api/crm/contracts/duplicate-check` | 新建前提示。入参 `company_id, contract_no, amount_fen, start_date, end_date`，可选 `esign_flow_id`；返回得分 > 0 的候选，按得分从高到低 |
| `GET /api/crm/contracts/{id}/duplicates` | 某份合同的重复候选（得分 > 0，从高到低） |
| `POST /api/crm/contracts/merge` | 草稿合同合并。入参 `master_id`、`duplicate_ids`（1–3 个）、`confirm=true`；权限码 `crm.contract.merge` |
| `GET /api/crm/contracts/duplicates/report` | 已签疑似重复报告（只读）：只列 `status=active` 且两两得分 ≥ 90 的合同对，供人工核对 |

## 合并事务

1. 只允许全部记录 `status=draft` 且 `esign_status` 为
   `not_started / rejected / expired / revoked`，否则返回
   `409 CRM_MERGE_CONTRACT_SIGNED`，数据无改动。
2. 会籍表 `contract_id` 改指向主记录。
3. 回款计划：主记录无期次时整体迁到主记录；主记录已有期次时，
   被合并合同的期次软删除；任一被合并期次已有实收则返回
   `409 CRM_MERGE_SCHEDULE_RECEIVED`。
4. 被合并记录写 `merged_into_id` 并软删除。
5. 合并后调用 `record_change（action=merge）`，未合入时用空实现桩
   （本样品记进内存 `change_log`，不发外部调用）。

校验先于落库：任一校验失败都不改动任何数据（测试用深拷贝快照断言）。

## 运行与测试

```bash
bash setup.sh   # 建 venv（如已有则复用）→ pytest → 变异自证 → MANIFEST 核对
```

或手动：

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q tests/
.venv/bin/python scripts/mutation_check.py
```

一键复跑：`bash setup.sh`，实测 `SELFTEST: PASS`（见
`ACCEPTANCE-EVIDENCE.md`）。

## 测试结果

- pytest：36 passed（AC1 16 项、AC2 7 项、AC3 4 项、AC4 3 项、接口 6 项）
- 变异自证：`MUTATION CHECK: PASS`（变异 1：1% 边界 `<=` 改 `<` 后
  边界测试变红；变异 2：合并允许集合加 `signed` 后 AC2 测试变红；
  恢复后全量通过，`contract.py` SHA256 不变）

## 对接点（S2-IAM 未接线，用桩先行）

- 权限：合并接口的权限码核对目前是请求头桩——调用方在
  `X-Permissions` 头里传逗号分隔的权限码列表，含 `crm.contract.merge`
  才放行，否则 403（见 `crm/dedup/permissions.py`）。合入核心系统时
  换成 S2-IAM 的真实权限校验，接口签名不变。
- `record_change`：目前是内存桩，只记 `change_log`。合入时换成
  核心系统的真实实现。
- 仓储：目前是内存仓储（`crm/dedup/store.py` 的 `InMemoryStore`），
  不连真实库。合入核心系统时把仓储换成 SQLAlchemy + PostgreSQL 16
  实现，判重函数 `score_pair` 与合并事务逻辑原样复用。
- 依赖其他工单的接口时，用接口桩或 mock 先行（任务统一技术约定）。

## 已知边界

- 报告接口只列 active 合同对；draft / terminated / 已软删除不列入；
  得分 70 的对不列入（只列 ≥ 90）。
- 空合同编号不参与 95 分规则（两份空编号不算重复）；空
  `esign_flow_id` 不参与 100 分规则。
- 合并的“任一期次已有实收则返回 409”只查被合并合同的期次；
  主记录自身的期次不受影响（主记录已有期次时被合并期次直接软删除，
  主记录期次原样保留）。
- 期限重叠是闭区间：前一份到期日当天起租算重叠（共享同一天）。

## 数据与保密

只用虚构测试数据（虚构企业、虚构合同编号、虚构 esign 流水号），
不出现客户名称，不使用任何真实个人信息或企业信息。
