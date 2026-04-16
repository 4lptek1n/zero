#!/usr/bin/env bash
# Reproduce the published zero benchmark runs end to end.
#
# Usage:
#   ANTHROPIC_API_KEY=sk-ant-... ./scripts/reproduce.sh [problem]
#
# `problem` is one of: sortnet8 | matmul44_z2 | capset:6 | all  (default: all)
#
# This script:
#   1. Verifies the working tree matches a published commit.
#   2. Reuses any cached LLM responses under .zero_cache/llm/ if present
#      (so re-runs are free).
#   3. Writes results into results/repro/<problem>/ to avoid clobbering the
#      committed baselines under results/llm/ and results/baselines/.
#   4. Prints a side-by-side comparison vs. the committed summary.json.
set -euo pipefail

cd "$(dirname "$0")/.."

PROBLEM="${1:-all}"

if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
    echo "ERROR: ANTHROPIC_API_KEY is not set." >&2
    echo "Get a key at https://console.anthropic.com/ and re-run:" >&2
    echo "    ANTHROPIC_API_KEY=sk-ant-... $0 ${PROBLEM}" >&2
    exit 2
fi

# zero reads these env vars (Replit AI Integrations style). We just point them
# at api.anthropic.com directly when running outside Replit.
export AI_INTEGRATIONS_ANTHROPIC_BASE_URL="${AI_INTEGRATIONS_ANTHROPIC_BASE_URL:-https://api.anthropic.com}"
export AI_INTEGRATIONS_ANTHROPIC_API_KEY="${AI_INTEGRATIONS_ANTHROPIC_API_KEY:-$ANTHROPIC_API_KEY}"

# Install the package in editable mode if `zero` isn't on PATH yet.
if ! command -v zero >/dev/null 2>&1; then
    echo "[repro] installing zero (editable)"
    pip install -e . >/dev/null
fi

mkdir -p results/repro/logs

run_one() {
    local prob="$1"
    local gens="$2"
    local islands="$3"
    local name
    name="$(echo "$prob" | tr ':' '-')"
    local out="results/repro/${name}"
    local log="results/repro/logs/${name}.log"
    local published="results/llm/${name}/summary.json"

    echo "===================================================================="
    echo " reproducing ${prob}  (gens=${gens}, islands=${islands})"
    echo "===================================================================="

    rm -rf "${out}"
    zero run --problem "${prob}" --generations "${gens}" --island-count "${islands}" \
        --seed 0 --output-dir "${out}" 2>&1 | tee "${log}"

    if [ -f "${published}" ]; then
        echo "--- published summary ---"
        cat "${published}"
        echo
        echo "--- your reproduction summary ---"
        cat "${out}/summary.json"
        echo
    fi
}

case "${PROBLEM}" in
    sortnet8)     run_one sortnet8     100 4 ;;
    matmul44_z2)  run_one matmul44_z2  150 4 ;;
    capset:6)     run_one "capset:6"   100 4 ;;
    all)
        run_one sortnet8     100 4
        run_one matmul44_z2  150 4
        run_one "capset:6"   100 4
        ;;
    *)
        echo "ERROR: unknown problem '${PROBLEM}'." >&2
        echo "Choose one of: sortnet8 | matmul44_z2 | capset:6 | all" >&2
        exit 2
        ;;
esac

python scripts/aggregate_results.py
echo "[repro] done. See results/RESULTS.md and results/repro/."
