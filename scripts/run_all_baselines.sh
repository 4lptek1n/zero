#!/usr/bin/env bash
# Run no-LLM (random-only) control conditions for every problem. These are
# the honest baselines that the LLM-driven runs are compared against in the
# release. No tokens are spent here.
set -euo pipefail

cd "$(dirname "$0")/.."

mkdir -p results/baselines/logs

run_one() {
    local prob="$1"
    local gens="$2"
    local islands="$3"
    local name
    name="$(echo "$prob" | tr ':' '-')"
    local out="results/baselines/${name}-random"
    local log="results/baselines/logs/${name}-random.log"

    if [ -f "${out}/summary.json" ]; then
        echo "[base] ${prob} already complete, skipping"
        return 0
    fi

    rm -rf "${out}"
    echo "[base] starting ${prob} gens=${gens} islands=${islands}"
    zero run --problem "${prob}" --generations "${gens}" --island-count "${islands}" --no-llm \
        --output-dir "${out}" 2>&1 | tee "${log}"
    echo "[base] finished ${prob}"
}

echo "===================================================================="
echo " zero random-only baselines — start: $(date -Iseconds)"
echo "===================================================================="

run_one sortnet8      200 4
run_one matmul44_z2   200 4
run_one "capset:6"    200 4

echo "===================================================================="
echo " zero random-only baselines — done: $(date -Iseconds)"
echo "===================================================================="

sleep infinity
