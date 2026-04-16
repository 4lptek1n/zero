from zero.config import EvolutionConfig, LLMConfig, RunConfig, SandboxConfig
from zero.evolution import run_evolution
from zero.problems import get_problem
from zero.mutation import swap_adjacent_lines, perturb_int_literal
import random


def test_smoke_sortnet8_no_llm(tmp_path):
    cfg = RunConfig(
        problem="sortnet8",
        seed=7,
        output_dir=str(tmp_path),
        use_llm=False,
        evolution=EvolutionConfig(
            island_count=2, island_size=4, generations=3,
            migration_every=2, tournament_size=2,
        ),
        sandbox=SandboxConfig(cpu_seconds=3, wall_seconds=6, memory_mb=256),
        llm=LLMConfig(cache_dir=str(tmp_path / "llm_cache")),
    )
    problem = get_problem("sortnet8")
    summary = run_evolution(cfg, problem)
    assert summary["problem"] == "sortnet8"
    assert summary["total_programs"] > 0
    assert summary["best_score"] is not None
    # Best cannot be worse than seed.
    assert summary["best_score"] <= 19
    # DB + JSONL must exist.
    assert (tmp_path / "programs.sqlite").exists()
    assert (tmp_path / "events.jsonl").exists()
    assert (tmp_path / "events.jsonl").stat().st_size > 0


def test_mutators_preserve_python():
    src = "def solve():\n    x = 1\n    y = 2\n    return (x, y)\n"
    rng = random.Random(0)
    for _ in range(20):
        mutated = swap_adjacent_lines(src, rng)
        assert "def solve" in mutated
        mutated = perturb_int_literal(src, rng)
        assert "def solve" in mutated
