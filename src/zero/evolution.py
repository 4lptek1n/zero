"""Island-model evolutionary loop."""
from __future__ import annotations
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .config import RunConfig
from .db import ProgramDB, ProgramRow
from .events import EventLog
from .llm import LLMOrchestrator, build_prompt
from .mutation import crossover, random_mutate
from .problems.base import Problem


@dataclass
class Candidate:
    source: str
    parent_ids: list[int]
    origin: str  # "seed" | "mutation" | "crossover" | "llm"
    island: int


def _tournament(
    rng: random.Random,
    population: list[ProgramRow],
    size: int,
    higher_is_better: bool,
) -> ProgramRow:
    contenders = rng.sample(population, min(size, len(population)))
    key = (lambda r: -(r.score or -1e18)) if higher_is_better else (lambda r: (r.score if r.score is not None else 1e18))
    return sorted(contenders, key=key)[0]


def _island_seed_population(
    db: ProgramDB,
    events: EventLog,
    problem: Problem,
    cfg: RunConfig,
) -> None:
    """Evaluate the seed program in each island so tournaments have something."""
    seed = problem.seed_program()
    for island in range(cfg.evolution.island_count):
        res = problem.evaluate(
            seed, cpu=cfg.sandbox.cpu_seconds,
            wall=cfg.sandbox.wall_seconds, mem=cfg.sandbox.memory_mb,
        )
        pid = db.insert_program(
            generation=0, island=island, parent_ids=[],
            source=seed, score=res.score, runtime=res.runtime,
            status="ok" if res.valid else "invalid",
            error=res.error,
        )
        events.emit(
            "program_inserted", program_id=pid, generation=0, island=island,
            score=res.score, valid=res.valid, origin="seed",
        )


def _migrate(
    db: ProgramDB,
    events: EventLog,
    rng: random.Random,
    cfg: RunConfig,
    problem: Problem,
    generation: int,
) -> None:
    n_islands = cfg.evolution.island_count
    if n_islands < 2:
        return
    frac = cfg.evolution.migration_fraction
    k = max(1, int(cfg.evolution.island_size * frac))
    for src in range(n_islands):
        dst = (src + 1) % n_islands
        top = db.top_k(island=src, k=k, higher_is_better=problem.higher_is_better)
        for row in top:
            new_id = db.insert_program(
                generation=generation, island=dst, parent_ids=[row.id],
                source=row.source, score=row.score, runtime=row.runtime,
                status="ok", error=None,
            )
            events.emit(
                "migration", program_id=new_id, from_island=src, to_island=dst,
                generation=generation, score=row.score,
            )


def run_evolution(
    cfg: RunConfig,
    problem: Problem,
    *,
    progress: Callable[[int, float | None], None] | None = None,
) -> dict:
    """Run the evolution loop end-to-end.

    Returns a summary dict with best score and program id.
    """
    out = Path(cfg.ensure_dirs())
    db = ProgramDB(out / "programs.sqlite")
    events = EventLog(out / "events.jsonl")
    rng = random.Random(cfg.seed)

    run_id = db.start_run(problem.name, cfg.seed, cfg.to_dict())
    events.emit("run_started", run_id=run_id, problem=problem.name, config=cfg.to_dict())

    llm = LLMOrchestrator(
        cfg.llm,
        db_logger=db.log_llm_call,
        enabled=cfg.use_llm,
    )
    events.emit("llm_status", enabled=llm.enabled, model=cfg.llm.model)

    db.start_generation(0)
    _island_seed_population(db, events, problem, cfg)
    db.finish_generation(0, _best_score(db, problem), cfg.evolution.island_count)

    for gen in range(1, cfg.evolution.generations + 1):
        db.start_generation(gen)
        events.emit("generation_started", generation=gen)
        candidates_this_gen = 0

        # Migration phase.
        if gen % max(1, cfg.evolution.migration_every) == 0:
            _migrate(db, events, rng, cfg, problem, gen)

        for island in range(cfg.evolution.island_count):
            pop = db.island_population(island, limit=cfg.evolution.island_size * 4)
            pop = [p for p in pop if p.status == "ok"]
            if not pop:
                # Fallback: take globally best.
                fb = db.top_k(island=None, k=1, higher_is_better=problem.higher_is_better)
                if not fb:
                    continue
                pop = fb

            # Build a batch of candidates for this island.
            new_candidates: list[Candidate] = []
            n_target = max(1, cfg.evolution.island_size // 2)

            # Local variation.
            for _ in range(n_target):
                parent = _tournament(rng, pop, cfg.evolution.tournament_size, problem.higher_is_better)
                if rng.random() < cfg.evolution.crossover_rate and len(pop) >= 2:
                    other = _tournament(rng, pop, cfg.evolution.tournament_size, problem.higher_is_better)
                    src = crossover(parent.source, other.source, rng)
                    parents = [parent.id, other.id]
                    origin = "crossover"
                else:
                    src = random_mutate(parent.source, rng)
                    parents = [parent.id]
                    origin = "mutation"
                new_candidates.append(Candidate(src, parents, origin, island))

            # LLM variation (optional).
            if llm.enabled:
                top = db.top_k(island=island, k=cfg.llm.top_k_context,
                               higher_is_better=problem.higher_is_better)
                if top:
                    prompt = build_prompt(
                        problem.describe(),
                        [(p.source, p.score) for p in top],
                    )
                    mutations = llm.fan_out(prompt, generation=gen, island=island)
                    for mut in mutations:
                        events.emit(
                            "llm_call", generation=gen, island=island,
                            temperature=mut.temperature, cached=mut.cached,
                            elapsed=mut.elapsed, error=mut.error,
                        )
                        if mut.source:
                            new_candidates.append(
                                Candidate(mut.source, [top[0].id], "llm", island)
                            )

            # Evaluate candidates.
            for cand in new_candidates:
                res = problem.evaluate(
                    cand.source, cpu=cfg.sandbox.cpu_seconds,
                    wall=cfg.sandbox.wall_seconds, mem=cfg.sandbox.memory_mb,
                )
                status = "ok" if res.valid else ("failed" if res.ok else "sandbox_error")
                pid = db.insert_program(
                    generation=gen, island=island, parent_ids=cand.parent_ids,
                    source=cand.source, score=res.score, runtime=res.runtime,
                    status=status, error=res.error,
                )
                candidates_this_gen += 1
                events.emit(
                    "program_inserted", program_id=pid, generation=gen, island=island,
                    score=res.score, valid=res.valid, origin=cand.origin, status=status,
                )

        best = _best_score(db, problem)
        db.finish_generation(gen, best, candidates_this_gen)
        events.emit("generation_finished", generation=gen, best_score=best, candidates=candidates_this_gen)
        if progress:
            progress(gen, best)

    # Summary.
    best_row = db.best(higher_is_better=problem.higher_is_better)
    summary = {
        "problem": problem.name,
        "generations": cfg.evolution.generations,
        "total_programs": db.count(),
        "best_score": best_row.score if best_row else None,
        "best_program_id": best_row.id if best_row else None,
        "baseline_score": problem.baseline_score,
    }
    events.emit("run_finished", **summary)
    db.finish_run(run_id)
    db.close()
    events.close()
    return summary


def _best_score(db: ProgramDB, problem: Problem) -> float | None:
    r = db.best(higher_is_better=problem.higher_is_better)
    return r.score if r else None
