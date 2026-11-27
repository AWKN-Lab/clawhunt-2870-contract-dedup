# 验收证据（ClawHunt #2870，S2-CRM-039）

实测环境：Python 3.12.3，FastAPI 0.115.6，pytest 9.2.0，httpx 0.28.1，
内存仓储（不连真实库）。原始日志在 `evidence/`。

## AC1：4 条判重规则各有命中与不命中用例（含 1% 与 1.01% 边界）

`tests/test_ac1_rules.py` 16 项，全部通过。边界用整数公式核对：
金额 1,000,000 分时，差 10,000 分（恰好 1%）得 70 分；
差 10,100 分（相对较大金额 1.01%）不得分。

## AC2：esign_status=signed 的合同发起合并返回 409，数据无改动

`tests/test_ac2_merge_signed.py` 7 项，全部通过。signed（主记录或
被合并记录）与 status=active 均返回 409 `CRM_MERGE_CONTRACT_SIGNED`，
合并前后合同、期次、会籍、变更日志的深拷贝快照逐字一致。

## AC3：主记录无期次时，被合并草稿合同的回款期次整体迁入主记录

`tests/test_ac3_schedule_move.py` 4 项，全部通过。两期期次整体迁入
主记录（期次号与金额保留），会籍改指向主记录，被合并记录写
`merged_into_id` 并软删除，`change_log` 末条 `action=merge`。
另覆盖：主记录已有期次时被合并期次软删除；被合并期次已有实收返回
409 `CRM_MERGE_SCHEDULE_RECEIVED`。

## AC4：report 接口只列出得分 ≥ 90 的 active 合同对

`tests/test_ac4_report.py` 3 项，全部通过。100 分对列入，95 分与
90 分对列入，70 分对、含 draft 的对不列入。

## 接口

`tests/test_api.py` 6 项，全部通过：duplicate-check、单合同 duplicates、
report、merge 成功、signed 合并 409、缺权限码 403。

## pytest 全量

```text
36 passed, 1 warning in 1.41s
```

（1 warning 是 starlette TestClient 的 anyio 别名 DeprecationWarning，
与交付代码无关。完整输出见 `evidence/pytest-20261127.log`。）

## 变异自证

```text
A 相：pytest exit=0
B 相 变异 1：1% 边界 <= 改 <：pytest exit=1（期望非 0）
B 相 变异 2：合并允许 signed：pytest exit=1（期望非 0）
C 相：pytest exit=0
contract.py SHA256（变异前后一致）：77d852ec76598c45fa4ab5305fe89dcf49c820a55e829584a9852494a0a8c4b2
MUTATION CHECK: PASS
```

完整输出见 `evidence/mutation-20261127.log`。

## 一键复跑

```text
bash setup.sh → SELFTEST: PASS
```

完整输出见 `evidence/setup-20261127.log`。

## MANIFEST

21 个文件（不含 MANIFEST 本身、`.venv`、`__pycache__`），
`sha256sum -c MANIFEST` 全 OK。
