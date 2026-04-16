"""Zero CLI entry point."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

from .config import EvolutionConfig, LLMConfig, RunConfig, SandboxConfig
from .evolution import run_evolution
from .problems import PROBLEM_NAMES, get_problem


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="zero", description="Evolutionary algorithm discovery engine.")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="Run the evolutionary search.")
    r.add_argument("--problem", required=True, choices=PROBLEM_NAMES + ["capset"])
    r.add_argument("--generations", type=int, default=50)
    r.add_argument("--island-count", type=int, default=5)
    r.add_argument("--island-size", type=int, default=10)
    r.add_argument("--migration-every", type=int, default=10)
    r.add_argument("--seed", type=int, default=0)
    r.add_argument("--output-dir", default="runs/latest")
    r.add_argument("--no-llm", action="store_true", help="Disable LLM calls.")
    r.add_argument("--cpu-seconds", type=float, default=5.0)
    r.add_argument("--wall-seconds", type=float, default=10.0)
    r.add_argument("--memory-mb", type=int, default=512)
    r.add_argument("--model", default="claude-opus-4-6")
    r.add_argument("--temperatures", default="0.4,0.8,1.0",
                   help="Comma-separated list of sampling temperatures.")
    r.add_argument("--llm-cache-dir", default=".zero_cache/llm")

    sub.add_parser("problems", help="List known problems.")

    return p


def _parse_run(args: argparse.Namespace) -> RunConfig:
    temps = tuple(float(x) for x in args.temperatures.split(",") if x.strip())
    return RunConfig(
        problem=args.problem,
        seed=args.seed,
        output_dir=args.output_dir,
        use_llm=not args.no_llm,
        evolution=EvolutionConfig(
            island_count=args.island_count,
            island_size=args.island_size,
            generations=args.generations,
            migration_every=args.migration_every,
        ),
        sandbox=SandboxConfig(
            cpu_seconds=args.cpu_seconds,
            wall_seconds=args.wall_seconds,
            memory_mb=args.memory_mb,
        ),
        llm=LLMConfig(
            model=args.model,
            temperatures=temps,
            parallel_calls=len(temps),
            cache_dir=args.llm_cache_dir,
        ),
    )


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.cmd == "problems":
        for name in PROBLEM_NAMES:
            prob = get_problem(name)
            print(f"{name}\tbaseline={prob.baseline_score}\thigher_is_better={prob.higher_is_better}")
            print(f"  {prob.describe()}")
        return 0

    if args.cmd == "run":
        cfg = _parse_run(args)
        problem = get_problem(args.problem)
        print(f"[zero] problem={problem.name} generations={cfg.evolution.generations} "
              f"islands={cfg.evolution.island_count} llm={cfg.use_llm}")
        def _prog(gen: int, best: float | None) -> None:
            print(f"[zero] gen={gen} best={best}")
        summary = run_evolution(cfg, problem, progress=_prog)
        out = Path(cfg.output_dir)
        (out / "summary.json").write_text(json.dumps(summary, indent=2))
        print(json.dumps(summary, indent=2))
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
