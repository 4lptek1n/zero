"""Problem evaluator base class."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol

from ..sandbox import SandboxResult, run_harness


@dataclass
class EvalResult:
    ok: bool
    score: float | None
    valid: bool
    runtime: float
    error: str | None
    raw: dict | None


class Problem(Protocol):
    name: str
    higher_is_better: bool
    baseline_score: float

    def seed_program(self) -> str: ...
    def evaluate(self, program_source: str, *, cpu: float, wall: float, mem: int) -> EvalResult: ...
    def describe(self) -> str: ...


def run_with_harness(
    program_source: str,
    harness: str,
    *,
    cpu: float,
    wall: float,
    mem: int,
    payload: dict | None = None,
) -> tuple[SandboxResult, EvalResult]:
    """Convenience wrapper converting sandbox output to EvalResult."""
    sb = run_harness(
        program_source,
        harness,
        cpu_seconds=cpu,
        wall_seconds=wall,
        memory_mb=mem,
        input_payload=payload,
    )
    if sb.kind != "ok":
        return sb, EvalResult(
            ok=False,
            score=None,
            valid=False,
            runtime=sb.runtime_seconds,
            error=f"{sb.kind}: {sb.message}",
            raw=None,
        )
    data = sb.result or {}
    valid = bool(data.get("valid", False))
    score = data.get("score") if valid else None
    err = data.get("error")
    return sb, EvalResult(
        ok=True,
        score=float(score) if score is not None else None,
        valid=valid,
        runtime=sb.runtime_seconds,
        error=err,
        raw=data,
    )
