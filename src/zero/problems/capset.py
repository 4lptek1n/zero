"""Cap-set lower bounds in F_3^n for small n. Score = size (higher is better).

A candidate program defines `solve() -> {"n": int, "vectors": [[...], ...]}`.
`vectors` is a list of length-n integer tuples with entries in {0,1,2}. A cap
set has no three (distinct) vectors that sum to 0 mod 3 (equivalently, no
three in arithmetic progression).
"""
from __future__ import annotations
from .base import EvalResult, run_with_harness


# Published lower bounds / best-known cap set sizes for small n:
# n=1: 2, n=2: 4, n=3: 9, n=4: 20, n=5: 45, n=6: 112, n=7: 236, n=8: 496.
BASELINES = {1: 2, 2: 4, 3: 9, 4: 20, 5: 45, 6: 112, 7: 236, 8: 496}


HARNESS = r'''
import json, os, sys
prog = open(os.environ["ZERO_PROGRAM_PATH"]).read()
payload = json.loads(open(os.environ["ZERO_INPUT_PATH"]).read())
ns = {"__name__": "__candidate__"}
try:
    exec(compile(prog, "<candidate>", "exec"), ns)
    fn = ns.get("solve")
    if fn is None:
        print(json.dumps({"valid": False, "error": "no solve()"})); sys.exit(0)
    out = fn()
except Exception as e:
    print(json.dumps({"valid": False, "error": f"exec: {e!r}"})); sys.exit(0)

try:
    n = int(out["n"])
    vecs = [tuple(int(x) % 3 for x in v) for v in out["vectors"]]
except Exception as e:
    print(json.dumps({"valid": False, "error": f"bad shape: {e!r}"})); sys.exit(0)

if n != payload.get("n", n):
    print(json.dumps({"valid": False, "error": f"n mismatch {n} vs {payload.get('n')}"})); sys.exit(0)

for v in vecs:
    if len(v) != n:
        print(json.dumps({"valid": False, "error": "wrong vector length"})); sys.exit(0)
    for x in v:
        if x not in (0,1,2):
            print(json.dumps({"valid": False, "error": "entries must be 0/1/2"})); sys.exit(0)

if len(set(vecs)) != len(vecs):
    print(json.dumps({"valid": False, "error": "duplicate vectors"})); sys.exit(0)

# Cap-set check: for every ordered triple (a, b), the unique c completing the
# line (a + b + c == 0 mod 3) must NOT be in the set (unless c equals a or b).
vset = set(vecs)
for i, a in enumerate(vecs):
    for j in range(i+1, len(vecs)):
        b = vecs[j]
        c = tuple((-(a[k] + b[k])) % 3 for k in range(n))
        if c == a or c == b:
            continue
        if c in vset:
            print(json.dumps({"valid": False, "error": f"3-AP: {a} {b} {c}"})); sys.exit(0)

print(json.dumps({"valid": True, "score": len(vecs), "n": n, "size": len(vecs)}))
'''


def _affine_cap_seed(n: int) -> str:
    """Construct a simple cap set via the classical 'all vectors with no 2' trick.

    {0,1}^n is a cap set because any 3-AP over F_3 with all entries in {0,1} must
    be constant. Size 2^n. Known to be beaten by better constructions for n>=3.
    """
    src = f"""\
def solve():
    n = {n}
    vectors = []
    for mask in range(1 << n):
        vectors.append([((mask >> k) & 1) for k in range(n)])
    return {{"n": n, "vectors": vectors}}
"""
    return src


class CapsetProblem:
    name = "capset"
    higher_is_better = True

    def __init__(self, n: int = 6):
        if n not in BASELINES:
            raise ValueError(f"capset baseline unknown for n={n}")
        self.n = n
        self.baseline_score = float(BASELINES[n])

    def seed_program(self) -> str:
        return _affine_cap_seed(self.n)

    def evaluate(self, program_source: str, *, cpu: float, wall: float, mem: int) -> EvalResult:
        _, res = run_with_harness(
            program_source, HARNESS, cpu=cpu, wall=wall, mem=mem,
            payload={"n": self.n},
        )
        return res

    def describe(self) -> str:
        return (
            f"Cap set in F_3^{self.n}. Return {{'n': {self.n}, 'vectors': [[...]]}}"
            f" from solve(). No three distinct vectors may sum to 0 mod 3. Maximize"
            f" the set size. Best known lower bound: {int(self.baseline_score)}."
        )
