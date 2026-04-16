"""Sorting network for N=8. Score = comparator count; lower is better.

A candidate program defines `solve() -> list[tuple[int,int]]` returning the
comparator sequence (each (i,j) with 0 <= i < j < 8). Correctness is checked
over all 256 binary inputs (by the 0-1 principle this implies correctness over
all inputs).
"""
from __future__ import annotations
from .base import EvalResult, run_with_harness


HARNESS = r'''
import json, os, sys, traceback

prog = open(os.environ["ZERO_PROGRAM_PATH"]).read()
ns = {"__name__": "__candidate__"}
try:
    exec(compile(prog, "<candidate>", "exec"), ns)
    fn = ns.get("solve")
    if fn is None:
        print(json.dumps({"valid": False, "error": "no solve()"})); sys.exit(0)
    comps = fn()
    comps = [tuple(c) for c in comps]
except Exception as e:
    print(json.dumps({"valid": False, "error": f"exec: {e!r}"})); sys.exit(0)

N = 8
# validate shape
for c in comps:
    if len(c) != 2: 
        print(json.dumps({"valid": False, "error": f"bad comparator {c}"})); sys.exit(0)
    i, j = c
    if not (isinstance(i, int) and isinstance(j, int)):
        print(json.dumps({"valid": False, "error": "non-int comparator"})); sys.exit(0)
    if not (0 <= i < N and 0 <= j < N and i != j):
        print(json.dumps({"valid": False, "error": f"out of range {c}"})); sys.exit(0)

# check all 256 binary inputs (0-1 principle)
for mask in range(1 << N):
    a = [(mask >> k) & 1 for k in range(N)]
    for (i, j) in comps:
        if a[i] > a[j]:
            a[i], a[j] = a[j], a[i]
    if any(a[k] > a[k+1] for k in range(N-1)):
        print(json.dumps({"valid": False, "error": f"fails on mask {mask}"})); sys.exit(0)

print(json.dumps({"valid": True, "score": len(comps), "comparators": len(comps)}))
'''


# Floyd's 19-comparator network for N=8 (a known-correct baseline).
SEED = '''\
def solve():
    # Floyd's sorting network for 8 inputs, 19 comparators.
    return [
        (0,1),(2,3),(4,5),(6,7),
        (0,2),(1,3),(4,6),(5,7),
        (1,2),(5,6),(0,4),(3,7),
        (1,5),(2,6),
        (1,4),(3,6),
        (2,4),(3,5),
        (3,4),
    ]
'''


class Sortnet8Problem:
    name = "sortnet8"
    higher_is_better = False
    baseline_score = 19.0

    def seed_program(self) -> str:
        return SEED

    def evaluate(self, program_source: str, *, cpu: float, wall: float, mem: int) -> EvalResult:
        _, res = run_with_harness(program_source, HARNESS, cpu=cpu, wall=wall, mem=mem)
        return res

    def describe(self) -> str:
        return (
            "Sorting network for 8 inputs. Return a list of (i,j) comparator pairs "
            "from `solve()`. The network must sort all 256 binary inputs. Fewer "
            "comparators is better. Best known optimal count is 19."
        )
