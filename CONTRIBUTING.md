# Contributing to zero

Thanks for your interest. Bug reports, methodological critiques, new
problem evaluators, and reproducibility runs are all welcome.

## Code of conduct

Be civil. Argue with the work, not the person. Reproducible counter-examples
beat opinions.

## Setting up a dev environment

```bash
git clone https://github.com/4lptek1n/zero.git
cd zero
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

Run the test suite:

```bash
pytest
ruff check .
ruff format --check .
```

Run the no-LLM smoke test (exercises the full evolutionary loop without
spending tokens):

```bash
zero run --problem sortnet8 --generations 5 --island-count 2 --no-llm \
         --output-dir runs/smoke
```

## Adding a new problem evaluator

A problem evaluator is a single Python module under
`src/zero/problems/<name>.py` that exports a class implementing the
`Problem` protocol from `zero.problems.base`:

```python
class Problem(Protocol):
    name: str
    higher_is_better: bool
    baseline_score: float

    def seed_program(self) -> str: ...
    def evaluate(self, program_source: str, *, cpu: float, wall: float, mem: int) -> EvalResult: ...
    def describe(self) -> str: ...
```

Concretely:

1. Pick a problem with a clear, machine-checkable correctness criterion and
   a published baseline (so we can report Δ honestly).
2. Write a sandbox **harness** — a self-contained Python snippet that
   `exec`'s the candidate, calls `solve()`, validates the output, and prints
   a single JSON line of the form `{"valid": bool, "score": float, ...}`.
3. Implement the class. Use `run_with_harness(...)` from
   `zero.problems.base` to drive the sandbox.
4. Provide a **seed program** that is correct and matches a known baseline
   (so generation 0 of evolution is never empty).
5. Register the problem in `src/zero/problems/__init__.py` (`get_problem`
   and `PROBLEM_NAMES`).
6. Add a `tests/test_problems.py` case that evaluates the seed and asserts
   it matches `baseline_score`.

Run `zero problems` to confirm your evaluator shows up.

## Pull request checklist

- `pytest` passes locally.
- `ruff check .` and `ruff format --check .` are clean.
- The CI workflow (`.github/workflows/ci.yml`) is green on your PR.
- If you add a problem, you also add a baseline run command to
  `scripts/run_all_baselines.sh`.
- If you change scoring, update the relevant rows in
  `results/RESULTS.md` and the README results table — and explain why in
  the PR description.

## Reporting a reproducibility failure

Open an issue with:

- The exact `zero run ...` command line.
- The seed.
- Your `git rev-parse HEAD`.
- The contents of `summary.json` from your run.
- The first 200 lines of `events.jsonl`.

Reproducibility regressions are treated as P0 bugs.
