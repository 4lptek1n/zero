# zero

**An open-source AlphaEvolve-style evolutionary algorithm discovery engine.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

---

## Abstract

In April 2025 DeepMind published [AlphaEvolve](https://deepmind.google/discover/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/),
an LLM-driven evolutionary search system that rediscovers and improves on
human-designed algorithms (faster matrix multiplication, larger cap sets,
shorter sorting networks, …). The paper is fascinating; the artifact is
closed-source. **`zero` is an open-source clone**: a population-based
island-model evolutionary loop where the mutation operator is itself a
language model. We provide three problem evaluators
(`sortnet8`, `matmul44_z2`, `capset:6`), a sandboxed candidate executor, an
on-disk LLM response cache, and an honest comparison against two control
conditions — random-only mutation and single-shot LLM. The repository ships
with the raw artifacts (SQLite + JSONL + best-program source) of the
benchmark runs reported below so the numbers are reproducible end-to-end
from a fresh checkout and an Anthropic API key.

## Method

### Architecture

```
                      ┌──────────────────────────────┐
                      │        EvolutionLoop         │
                      │  (island model, N islands)   │
                      └──────────────┬───────────────┘
                                     │
                ┌────────────────────┼─────────────────────┐
                │                    │                     │
                ▼                    ▼                     ▼
        ┌───────────────┐   ┌────────────────┐    ┌──────────────────┐
        │ random mutate │   │  LLM mutator   │    │   crossover      │
        │ (AST + token) │   │ (Claude Opus,  │    │   (two parents)  │
        │               │   │  N temperatures│    │                  │
        └───────┬───────┘   │  in parallel,  │    └────────┬─────────┘
                │           │  on-disk cache)│             │
                │           └───────┬────────┘             │
                └────────────┬──────┴──────────────────────┘
                             ▼
                  ┌─────────────────────┐
                  │ sandboxed executor  │
                  │ (rlimit cpu/mem,    │
                  │  wall-clock guard)  │
                  └─────────┬───────────┘
                            ▼
                  ┌─────────────────────┐         ┌────────────────┐
                  │ ProgramDB (sqlite)  │ ──────▶ │ events.jsonl   │
                  │  + EventLog         │         │ summary.json   │
                  └─────────────────────┘         └────────────────┘
```

Each generation, every island independently runs tournament selection +
mutation/crossover; in parallel, the top-k programs are shown to the LLM at
several temperatures and the returned candidates are added to the pool.
Every candidate is executed in a fresh subprocess with `RLIMIT_CPU`,
`RLIMIT_AS`, and a wall-clock guard, then inserted into a SQLite database
tagged with origin (`seed | mutation | crossover | llm`). Periodic
migration copies the top-k of each island to the next, keeping islands
diverse but not isolated.

### LLM mutation operator

The orchestrator uses the Anthropic API (model: `claude-opus-4-6`).
Required env vars (see `scripts/reproduce.sh`):

```
AI_INTEGRATIONS_ANTHROPIC_BASE_URL
AI_INTEGRATIONS_ANTHROPIC_API_KEY
```

Every `(model, temperature, prompt)` triple is hashed with SHA-256 and the
response is cached at `.zero_cache/llm/<hash>.json`. A re-run with the same
seed therefore costs **zero tokens**.

### Sandbox

The sandbox spawns a fresh `python -I -B` per candidate, sets `RLIMIT_CPU`
and `RLIMIT_AS` inside the child, and wraps the call with
`subprocess.run(..., timeout=...)` as the wall-clock guard. There is no
shared interpreter state between candidates.

## Problems

| Problem      | Direction       | Baseline | Source / status                                         |
|--------------|-----------------|----------|---------------------------------------------------------|
| `sortnet8`   | lower is better | **19**   | Floyd's 19-comparator network. Provably optimal for N=8.|
| `matmul44_z2`| lower is better | **64**   | Naive 4×4 matmul over GF(2). Strassen-style ⇒ 49.       |
| `capset:6`   | higher is better| **112**  | Best-known cap set in F₃⁶ (Edel 2004).                  |

The full problem registry is in `src/zero/problems/`. See
[CONTRIBUTING.md](CONTRIBUTING.md) for how to add a new evaluator.

## Results

All numbers are produced by `scripts/aggregate_results.py` from the raw
artifacts under `results/`. Re-run any time. Seed = `0` for every run.

### Headline (LLM-driven evolution vs. controls)

| Problem        | Baseline | **zero (LLM-evo)** | Random-only | Single-shot LLM | Δ vs. baseline | Optimal? |
|----------------|---------:|--------------------:|------------:|----------------:|---------------:|----------|
| `sortnet8`     |       19 |               **19** |          19 |              19 |             +0 | matches optimum |
| `matmul44_z2`  |       64 |               **49** |          64 |              64 |            −15 | matches Strassen-style 7²=49 |
| `capset:6`     |      112 |               *budget-capped* |        64 |              77 |              — | — |

(Lower is better for `sortnet8` / `matmul44_z2`; higher is better for `capset:6`.)

The LLM-driven runs **match Floyd's optimum** on `sortnet8` from generation 0
(the seed program is already optimal — the 100-generation run confirms
nothing smaller is found, which is the correct answer) and **discover a
49-product decomposition** of `matmul44_z2`, matching the
Strassen-recursive bound `7² = 49`. The random-only baseline does not
escape the seed in either case, and the single-shot LLM baseline only
echoes the seed back. This is exactly the regime where evolutionary
LLM-search adds value over either control alone.

### Cost & wall-clock

| Run                               | Generations | Programs eval'd | LLM calls | Wall-clock | Approx. cost |
|-----------------------------------|------------:|----------------:|----------:|-----------:|-------------:|
| `sortnet8`     LLM-evo            |         100 |           3,244 |     1,200 | ~25 min    | ~$8          |
| `matmul44_z2`  LLM-evo            |         150 |           4,864 |     1,800 | ~45 min    | ~$14         |
| `capset:6`     LLM-evo (capped)   |       100\* |          —      |       —   |       —    | within budget|
| `sortnet8`     random-only        |         200 |           4,084 |         0 | ~6 min     | $0           |
| `matmul44_z2`  random-only        |         200 |           4,084 |         0 | ~9 min     | $0           |
| `capset:6`     random-only        |         200 |           4,084 |         0 | ~12 min    | $0           |

\* `capset:6` LLM-evo was budget-capped; see `results/llm/capset-6/` for the
in-flight artifacts. The full per-run dump is in
[`results/RESULTS.md`](results/RESULTS.md).

### Single-shot LLM control condition

The single-shot baseline shows the same problem description and the same
seed program to the same model (`claude-opus-4-6`, temperature `0.7`),
asks for one program, and evaluates it once. No mutation, no selection,
no second attempt. Per-problem detail and the raw response are committed
under `results/single_shot/`.

## Continuous integration

The CI workflow is shipped under
[`docs/github-workflow-template/ci.yml`](docs/github-workflow-template/ci.yml)
(see the README in that directory for the one-line install). It runs:

- `ruff check .`
- `pytest -q`
- The 5-generation no-LLM smoke run (asserts `summary.json` is well-formed
  and `best_score` is non-null).

It is shipped as a template instead of `.github/workflows/ci.yml` only
because the OAuth token used to push the initial release intentionally
lacks the `workflow` scope. Move it into place in any fork to enable
CI.

## Reproducibility

Every committed run is fully reproducible from a fresh checkout. The LLM
response cache is committed (or can be regenerated) so re-runs cost zero
tokens.

```bash
git clone https://github.com/yusuf4lp/zero.git
cd zero
pip install -e ".[dev]"

# 60-second smoke test, no LLM, no token spend.
zero run --problem sortnet8 --generations 5 --island-count 2 --no-llm \
         --output-dir runs/smoke

# Full reproduction (requires an Anthropic API key).
ANTHROPIC_API_KEY=sk-ant-... ./scripts/reproduce.sh all
```

The reproduce script writes outputs to `results/repro/` so it never
clobbers the committed published artifacts under `results/llm/` or
`results/baselines/`. It then prints a side-by-side diff of
`summary.json`.

## Installation

```bash
pip install -e .
# or, with dev extras for tests + lint
pip install -e ".[dev]"
```

Verify:

```bash
zero problems
zero run --problem sortnet8 --generations 5 --island-count 2 --no-llm \
         --output-dir /tmp/zero-smoke
```

## Project layout

```
zero/
├── src/zero/
│   ├── cli.py              # `zero run`, `zero problems`
│   ├── config.py           # typed config dataclasses
│   ├── sandbox.py          # subprocess executor with rlimit guards
│   ├── db.py               # SQLite schema + DAO
│   ├── events.py           # JSONL streaming event log
│   ├── evolution.py        # island-model evolutionary loop
│   ├── mutation.py         # deterministic source-level mutators
│   ├── llm.py              # parallel Anthropic orchestrator + cache
│   └── problems/           # sortnet8, matmul44_z2, capset
├── tests/                  # pytest unit tests
├── scripts/
│   ├── run_all_benchmarks.sh
│   ├── run_all_baselines.sh
│   ├── run_single_shot_llm.py
│   ├── aggregate_results.py
│   └── reproduce.sh        # end-to-end replay from a clean clone
├── results/                # committed run artifacts
│   ├── RESULTS.md          # auto-generated from summaries + sqlite
│   ├── llm/<problem>/      # LLM-evo runs
│   ├── baselines/<problem>-random/
│   └── single_shot/<problem>/
├── .github/workflows/ci.yml
├── CITATION.cff
├── CONTRIBUTING.md
└── LICENSE
```

## Limitations

1. **Token budget.** A research-grade run on harder problems
   (`capset:7`, `capset:8`, `matmul55_z2`) requires meaningfully more
   compute than the budget approved for this release. The `capset:6` LLM-evo
   numbers should be read with that caveat.
2. **Sandbox is best-effort.** Adversarial Python escapes are not the
   threat model — buggy candidate programs are. The sandbox blocks
   resource exhaustion (CPU, memory, wall-clock) and isolates state, but
   it is not a secure jail. Do not run untrusted prompts.
3. **One model.** Results are reported only for `claude-opus-4-6`. Other
   models are likely better at some problems and worse at others. Adding
   a second backend is a small change in `src/zero/llm.py`.
4. **No diff-mode mutation prompt.** AlphaEvolve uses a structured "diff
   against this candidate" prompt that we have not (yet) implemented. We
   send the top-k candidates verbatim and ask for a new full program.
5. **`sortnet8` already starts optimal.** This is honestly reported: the
   seed is Floyd's 19-comparator network. The point of including
   `sortnet8` is to show that the system does not regress from a known
   optimum, not that it discovers something new.

## Citation

```bibtex
@software{keser_zero_2026,
  author  = {Keser, Yusuf},
  title   = {{zero}: an open-source AlphaEvolve-style evolutionary algorithm discovery engine},
  year    = {2026},
  url     = {https://github.com/yusuf4lp/zero},
  version = {0.1.0}
}
```

See also [`CITATION.cff`](CITATION.cff).

## References

- Novikov, A. et al. (2025). *AlphaEvolve: A coding agent for scientific
  and algorithmic discovery.* DeepMind blog and accompanying preprint.
- Romera-Paredes, B. et al. (2024). *FunSearch: Mathematical discoveries
  from program search with large language models.* Nature 625, 468–475.
- Strassen, V. (1969). *Gaussian elimination is not optimal.* Numer.
  Math. 13, 354–356.
- Edel, Y. (2004). *Extensions of generalized product caps.* Designs,
  Codes and Cryptography 31, 5–14.
- Floyd, R. W. (1964). *Algorithm 245: TREESORT 3.* CACM 7(12), 701.
- Knuth, D. E. (1973). *The Art of Computer Programming, Vol. 3:
  Sorting and Searching*, §5.3.4 (sorting networks).

## License

MIT — see [LICENSE](LICENSE).

## Contact

Yusuf Keser — kesermkkdkd@gmail.com
