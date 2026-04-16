#!/usr/bin/env python3
"""Single-shot LLM control condition.

For each problem we issue ONE non-evolutionary call to the same model used by
the evolutionary loop (`claude-opus-4-6`), with the same problem description
and the same seed program shown as the only context. The returned program is
evaluated once. No mutation, no selection, no second attempt.

This is the honest "what does the LLM produce on its own?" baseline that the
LLM-driven evolutionary results are compared against.

Outputs:
    results/single_shot/<problem>/{program.py, response.txt, summary.json}
    results/single_shot/single_shot.json   (combined headline)

Reads `AI_INTEGRATIONS_ANTHROPIC_BASE_URL` and
`AI_INTEGRATIONS_ANTHROPIC_API_KEY` like the engine.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from zero.config import LLMConfig  # noqa: E402
from zero.llm import LLMOrchestrator, build_prompt, extract_code  # noqa: E402
from zero.problems import get_problem  # noqa: E402

PROBLEMS = ["sortnet8", "matmul44_z2", "capset:6"]


def run_one(problem_name: str, out_root: Path) -> dict:
    prob = get_problem(problem_name)
    safe = problem_name.replace(":", "-")
    out = out_root / safe
    out.mkdir(parents=True, exist_ok=True)

    seed_src = prob.seed_program()
    seed_eval = prob.evaluate(seed_src, cpu=10.0, wall=20.0, mem=512)
    prompt = build_prompt(prob.describe(), [(seed_src, seed_eval.score)])

    cfg = LLMConfig(
        model="claude-opus-4-6",
        temperatures=(0.7,),
        parallel_calls=1,
        cache_dir=str(ROOT / ".zero_cache" / "llm"),
    )
    orch = LLMOrchestrator(cfg)
    if not orch.enabled:
        print(f"[single-shot] LLM disabled (env not configured) — skipping {problem_name}",
              file=sys.stderr)
        return {"problem": problem_name, "skipped": True}

    t0 = time.monotonic()
    muts = orch.fan_out(prompt, generation=0, island=None)
    elapsed = time.monotonic() - t0
    if not muts:
        return {"problem": problem_name, "error": "no mutation returned"}
    m = muts[0]
    (out / "response.txt").write_text(m.response or "")
    (out / "prompt.txt").write_text(prompt)

    code = extract_code(m.response or "") or ""
    (out / "program.py").write_text(code)

    if not code:
        result = {
            "problem": problem_name,
            "ok": False,
            "valid": False,
            "score": None,
            "baseline_score": prob.baseline_score,
            "higher_is_better": prob.higher_is_better,
            "error": m.error or "no code block in response",
            "elapsed_seconds": elapsed,
            "cached": m.cached,
        }
    else:
        ev = prob.evaluate(code, cpu=10.0, wall=30.0, mem=512)
        result = {
            "problem": problem_name,
            "ok": ev.ok,
            "valid": ev.valid,
            "score": ev.score,
            "baseline_score": prob.baseline_score,
            "higher_is_better": prob.higher_is_better,
            "error": ev.error,
            "elapsed_seconds": elapsed,
            "cached": m.cached,
        }
    (out / "summary.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    return result


def main() -> int:
    out_root = ROOT / "results" / "single_shot"
    out_root.mkdir(parents=True, exist_ok=True)
    combined = []
    for name in PROBLEMS:
        try:
            combined.append(run_one(name, out_root))
        except Exception as e:
            combined.append({"problem": name, "error": repr(e)})
    (out_root / "single_shot.json").write_text(json.dumps(combined, indent=2))
    print(f"\n[single-shot] wrote {out_root / 'single_shot.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
