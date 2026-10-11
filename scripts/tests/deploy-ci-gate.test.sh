#!/usr/bin/env bash
# **البوّابةُ الثانية — تُقاس في الاتجاهين** (قرارُ المالك 2026-10-11): تقف حين يجب وتمرّ حين يجب.
# الحالاتُ في `deploy_ci_gate_cases.py` على GitHub مزيَّف — **لا شبكة ولا خادم ولا دفع**.
#
#     bash scripts/tests/deploy-ci-gate.test.sh
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
PY="$(command -v python3 || command -v python)"
[ -n "$PY" ] || { echo "  ✗ لا python — والغيابُ لا يُقرأ سلامة"; exit 1; }
exec "$PY" "$HERE/deploy_ci_gate_cases.py"
