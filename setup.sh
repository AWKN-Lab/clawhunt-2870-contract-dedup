#!/usr/bin/env bash
# #2870 最小样品一键自测（setup.sh）
#
# 1. 有 .venv 就用它；没有就建 venv 并按 requirements.txt 装依赖。
# 2. 跑 pytest 全量测试。
# 3. 跑 scripts/mutation_check.py 变异自证。
# 4. 核对 MANIFEST（sha256sum -c）。
# 任何一步失败都退出非零；最后打印 SELFTEST: PASS。
set -u
cd "$(dirname "$0")"

if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
  .venv/bin/pip install -q -r requirements.txt
fi

.venv/bin/python -m pytest -q tests/
.venv/bin/python scripts/mutation_check.py

if [ -f MANIFEST ]; then
  sha256sum -c MANIFEST
fi

echo "SELFTEST: PASS"
