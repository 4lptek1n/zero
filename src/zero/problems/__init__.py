"""Problem registry."""
from __future__ import annotations
from .base import EvalResult, Problem
from .matmul44_z2 import Matmul44Z2Problem
from .sortnet8 import Sortnet8Problem
from .capset import CapsetProblem


def get_problem(name: str) -> Problem:
    if name == "sortnet8":
        return Sortnet8Problem()
    if name == "matmul44_z2":
        return Matmul44Z2Problem()
    if name.startswith("capset"):
        parts = name.split(":")
        n = int(parts[1]) if len(parts) > 1 else 6
        return CapsetProblem(n=n)
    raise KeyError(f"unknown problem: {name}")


PROBLEM_NAMES = ["sortnet8", "matmul44_z2", "capset:6", "capset:7", "capset:8"]


__all__ = [
    "EvalResult",
    "Problem",
    "get_problem",
    "PROBLEM_NAMES",
    "Sortnet8Problem",
    "Matmul44Z2Problem",
    "CapsetProblem",
]
