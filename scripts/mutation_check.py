#!/usr/bin/env python3
"""变异自证（ClawHunt #2870，S2-CRM-039）。

三相：A 相全量测试通过；B 相两次变异各跑目标测试、须变红；
C 相恢复后全量测试通过，且 crm/dedup/contract.py 的 SHA256 与
变异前一致（变异是临时改动，不留痕）。

变异 1：1% 边界的 `<=` 改成 `<`（差额恰好 1% 不再命中 70 分）。
变异 2：合并允许的 esign_status 集合里加上 signed（已签也能合并）。
任一变异没变红即退出非 0。
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "crm" / "dedup" / "contract.py"
PY = ROOT / ".venv" / "bin" / "python"
PY = PY if PY.exists() else Path(sys.executable)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_pytest(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(PY), "-m", "pytest", "-q", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )


def main() -> int:
    original = TARGET.read_bytes()
    original_sha = sha256(TARGET)

    phase_a = run_pytest(["tests/"])
    print(f"A 相：pytest exit={phase_a.returncode}")
    if phase_a.returncode != 0:
        print(phase_a.stdout[-2000:])
        print("MUTATION CHECK: FAIL（A 相未通过）")
        return 1

    mutations = [
        (
            "变异 1：1% 边界 <= 改 <",
            "diff * 100 <= larger",
            "diff * 100 < larger",
            ["tests/test_ac1_rules.py::test_rule70_hit_diff_exactly_1pct"],
        ),
        (
            "变异 2：合并允许 signed",
            '{"not_started", "rejected", "expired", "revoked"}',
            '{"not_started", "rejected", "expired", "revoked", "signed"}',
            ["tests/test_ac2_merge_signed.py"],
        ),
    ]
    for name, old, new, targets in mutations:
        text = TARGET.read_text()
        if old not in text:
            print(f"{name}：未找到待变异文本")
            return 1
        TARGET.write_text(text.replace(old, new, 1))
        result = run_pytest(targets)
        print(f"B 相 {name}：pytest exit={result.returncode}（期望非 0）")
        TARGET.write_bytes(original)
        if sha256(TARGET) != original_sha:
            print(f"{name}：恢复后 SHA 不一致")
            return 1
        if result.returncode == 0:
            print(f"MUTATION CHECK: FAIL（{name} 未变红）")
            return 1

    phase_c = run_pytest(["tests/"])
    print(f"C 相：pytest exit={phase_c.returncode}")
    if phase_c.returncode != 0:
        print(phase_c.stdout[-2000:])
        print("MUTATION CHECK: FAIL（C 相未通过）")
        return 1
    if sha256(TARGET) != original_sha:
        print("MUTATION CHECK: FAIL（恢复后 SHA 不一致）")
        return 1
    print(f"contract.py SHA256（变异前后一致）：{original_sha}")
    print("MUTATION CHECK: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
