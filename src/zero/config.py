"""Typed configuration for zero runs."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


@dataclass
class SandboxConfig:
    cpu_seconds: float = 5.0
    wall_seconds: float = 10.0
    memory_mb: int = 512


@dataclass
class LLMConfig:
    model: str = "claude-opus-4-6"
    temperatures: tuple[float, ...] = (0.4, 0.8, 1.0)
    max_tokens: int = 8192
    parallel_calls: int = 3
    top_k_context: int = 3
    cache_dir: str = ".zero_cache/llm"


@dataclass
class EvolutionConfig:
    island_count: int = 5
    island_size: int = 10
    generations: int = 50
    migration_every: int = 10
    migration_fraction: float = 0.1
    tournament_size: int = 3
    crossover_rate: float = 0.2
    mutation_rate: float = 1.0
    elitism: int = 1


@dataclass
class RunConfig:
    problem: str = "sortnet8"
    seed: int = 0
    output_dir: str = "runs/latest"
    use_llm: bool = True
    evolution: EvolutionConfig = field(default_factory=EvolutionConfig)
    sandbox: SandboxConfig = field(default_factory=SandboxConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def ensure_dirs(self) -> Path:
        p = Path(self.output_dir)
        p.mkdir(parents=True, exist_ok=True)
        Path(self.llm.cache_dir).mkdir(parents=True, exist_ok=True)
        return p
