#!/usr/bin/env bash
# Sequentially run the three LLM-driven benchmarks and write results under
# artifacts/zero/results/llm/. Designed to be run as a Replit workflow so it
# survives shell detachment.
set -euo pipefail

cd "$(dirname "$0")/.."

mkdir -p results/llm/logs

run_one() {
    local prob="$1"
    local gens="$2"
    local islands="$3"
    local name
    name="$(echo "$prob" | tr ':' '-')"
    local out="results/llm/${name}"
    local log="results/llm/logs/${name}.log"

    if [ -f "${out}/summary.json" ]; then
        echo "[bench] ${prob} already complete (summary.json present), skipping"
        return 0
    fi

    rm -rf "${out}"
    echo "[bench] starting ${prob} gens=${gens} islands=${islands}"
    echo "[bench] log -> ${log}"
    zero run --problem "${prob}" --generations "${gens}" --island-count "${islands}" \
        --output-dir "${out}" 2>&1 | tee "${log}"
    echo "[bench] finished ${prob}"
}

echo "===================================================================="
echo " zero benchmark suite — start: $(date -Iseconds)"
echo "===================================================================="

run_one sortnet8      100 4
run_one matmul44_z2   150 4
run_one "capset:6"    100 4

echo "===================================================================="
echo " zero benchmark suite — done: $(date -Iseconds)"
echo "===================================================================="

# Keep the workflow process alive so logs remain visible.
sleep infinity
