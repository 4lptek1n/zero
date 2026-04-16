# Launch post draft — `zero`

## TL;DR (one-line)

> Open-source clone of DeepMind's AlphaEvolve: a Claude-driven evolutionary
> loop that discovers algorithms. Matches the optimal 19-comparator
> sorting network for N=8 and the Strassen-recursive 49-product
> decomposition of 4×4 matrix multiplication over GF(2). MIT-licensed,
> end-to-end reproducible from a fresh clone + an Anthropic API key.

Repo: https://github.com/yusuf4lp/zero

---

## Hacker News

**Title:** `zero – open-source clone of DeepMind's AlphaEvolve`

**Body:**

I built `zero`, an open-source AlphaEvolve clone. Same idea: a
population-based island-model evolutionary loop where the mutation
operator is a language model. Each generation, the top-k candidates of
each island are shown to Claude Opus at several temperatures in parallel,
the returned programs are sandboxed, scored, and inserted back into the
SQLite-backed program database. Migration moves elites between islands
every N generations.

What's in the repo:

- Three problem evaluators with published baselines: 8-input sorting
  networks (Floyd, 19 comparators), 4×4 matmul over GF(2)
  (Strassen-recursive ⇒ 49 products), and cap-sets in F₃⁶ (Edel, 112).
- A subprocess sandbox with `RLIMIT_CPU` / `RLIMIT_AS` / wall-clock guard
  per candidate.
- An on-disk SHA-256 cache of every `(model, temperature, prompt)`
  triple, so re-running a published seed costs zero tokens.
- Three control conditions reported alongside the LLM-evo numbers:
  random-mutation-only and single-shot-LLM-only.
- Raw run artifacts (SQLite + JSONL + best-program source) committed
  under `results/` so every number in the README is reproducible without
  spending a dollar.
- A 5-generation no-LLM smoke test in CI on every PR.

Headline numbers: matches Floyd's optimum on `sortnet8`; finds the
Strassen-bound 49-product decomposition on `matmul44_z2`; `capset:6` is
budget-capped (the LLM-evo run is in flight in the committed artifacts —
a longer run is the obvious next step).

Limitations are spelled out honestly in the README — chiefly: token
budget caps the harder problems, the sandbox is not a security jail, and
results are reported only for `claude-opus-4-6`.

Would love methodological critiques from anyone who has worked on
AlphaEvolve / FunSearch-style systems.

---

## X / Twitter (5 posts)

1. open-sourced an AlphaEvolve clone today.
   it's an evolutionary loop where the mutation operator is Claude Opus.
   matches the optimal sorting network for N=8 and the Strassen-bound
   49-product 4x4 matmul over GF(2).
   👉 https://github.com/yusuf4lp/zero

2. each generation, every island runs tournament selection + mutation,
   and in parallel the top-k get shown to the LLM at multiple
   temperatures. winners get sandboxed, scored, and written into a
   SQLite program db. migration every N gens. that's it.

3. every (model, temp, prompt) is hashed and cached on disk.
   re-running a published seed costs $0.
   the raw sqlite + jsonl from the actual benchmark runs is committed
   in the repo so the numbers in the README are end-to-end reproducible.

4. honest controls reported alongside:
   • random-mutation-only (no LLM at all)
   • single-shot LLM (one call, no evolution)
   neither escapes the seed on `matmul44_z2`. the LLM-evo loop finds
   the 49-product decomposition. that gap is the whole point.

5. limitations are in the README. token budget caps the harder problems,
   the sandbox is best-effort, and only one model was tested. PRs and
   methodological critiques very welcome — esp. if you've worked on
   AlphaEvolve / FunSearch.

---

## r/MachineLearning

**Title:** `[P] zero — an open-source AlphaEvolve clone (LLM-driven
evolutionary search for algorithms)`

**Body:** *(use the HN body above)*

---

## Media to attach

- `docs/media/dashboard.gif` — 30-second screen capture of the
  dashboard during evolution. Recommended capture: pick the
  `matmul44_z2` LLM-evo run, scrub from gen 0 to gen ~60, show the
  leaderboard climbing, end on the 49-product best program highlighted.
  Encode at 12 fps, ≤ 4 MB so GitHub renders inline.
- `docs/media/architecture.svg` — replace the ASCII diagram in the
  README with a real SVG once available.

The dashboard artifact lives in the sibling
`artifacts/zero-dashboard/` directory in the source monorepo and is
not part of this released repository.
