"""4x4 matrix multiplication over GF(2). Score = number of bilinear products.

A candidate program defines:
    solve() -> dict with keys:
        "products": list of [A_mask, B_mask] (ints, 16 bits each for the 4x4 entries
                    of A and B; bit k is row (k//4), col (k%4))
        "C": list of 16 ints (each a bitmask over which products XOR to produce
             the corresponding entry of C in row-major order)

Scoring: number of products that also reconstructs C = A @ B mod 2 correctly
on all sampled input pairs. Baseline is 64 (naive). Strassen-style recursion
of Strassen(2,2,2;7) yields 7^2 = 49.
"""
from __future__ import annotations
from .base import EvalResult, run_with_harness


HARNESS = r'''
import json, os, sys, random

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
    products = [tuple(p) for p in out["products"]]
    C_recipe = list(out["C"])
except Exception as e:
    print(json.dumps({"valid": False, "error": f"bad shape: {e!r}"})); sys.exit(0)

if len(C_recipe) != 16:
    print(json.dumps({"valid": False, "error": "C must have 16 entries"})); sys.exit(0)
P = len(products)
for (am, bm) in products:
    if not (0 <= am < (1<<16) and 0 <= bm < (1<<16)):
        print(json.dumps({"valid": False, "error": "mask out of range"})); sys.exit(0)
for r in C_recipe:
    if not (0 <= r < (1<<P) if P else r == 0):
        print(json.dumps({"valid": False, "error": "recipe mask out of range"})); sys.exit(0)

def bit(x, k): return (x >> k) & 1
def popcount(x):
    c = 0
    while x:
        x &= x-1; c += 1
    return c

def eval_candidate(A, B):
    # A,B are 16-bit ints (row-major 4x4 over GF(2))
    prods = []
    for (am, bm) in products:
        a = 0
        b = 0
        # parity of AND of selected entries
        for k in range(16):
            if bit(am, k):
                a ^= bit(A, k)
            if bit(bm, k):
                b ^= bit(B, k)
        prods.append(a & b)
    C = 0
    for idx, recipe in enumerate(C_recipe):
        x = 0
        for p in range(P):
            if bit(recipe, p):
                x ^= prods[p]
        C |= (x & 1) << idx
    return C

def true_mm(A, B):
    C = 0
    for i in range(4):
        for j in range(4):
            s = 0
            for k in range(4):
                s ^= bit(A, i*4 + k) & bit(B, k*4 + j)
            C |= (s & 1) << (i*4 + j)
    return C

# Deterministic verification.
rng = random.Random(payload.get("seed", 0))
trials = int(payload.get("trials", 256))
# First exhaustively try small structured inputs then random.
structured = []
for k in range(16):
    structured.append((1 << k, (1 << k)))  # simple unit tests
    structured.append(((1 << k), 0xFFFF))
for A, B in structured:
    if eval_candidate(A, B) != true_mm(A, B):
        print(json.dumps({"valid": False, "error": f"mismatch structured A={A} B={B}"})); sys.exit(0)

for _ in range(trials):
    A = rng.getrandbits(16); B = rng.getrandbits(16)
    if eval_candidate(A, B) != true_mm(A, B):
        print(json.dumps({"valid": False, "error": f"mismatch random A={A} B={B}"})); sys.exit(0)

print(json.dumps({"valid": True, "score": P, "products": P}))
'''


def _naive_seed() -> str:
    """The naive 64-product baseline for 4x4 multiplication.

    Product k (for 0 <= k < 64) corresponds to A[i,m] * B[m,j] where
    k = 16*i + 4*j + m; lives in C[i,j] at position 4*i + j.
    """
    products = []
    recipes = [0] * 16
    for i in range(4):
        for j in range(4):
            for m in range(4):
                a_mask = 1 << (i * 4 + m)
                b_mask = 1 << (m * 4 + j)
                p_idx = len(products)
                products.append((a_mask, b_mask))
                recipes[i * 4 + j] |= 1 << p_idx
    src_lines = [
        "def solve():",
        f"    products = {products!r}",
        f"    C = {recipes!r}",
        "    return {'products': products, 'C': C}",
    ]
    return "\n".join(src_lines) + "\n"


SEED = _naive_seed()


class Matmul44Z2Problem:
    name = "matmul44_z2"
    higher_is_better = False
    baseline_score = 64.0  # naive; Strassen-recursive achieves 49.

    def seed_program(self) -> str:
        return SEED

    def evaluate(self, program_source: str, *, cpu: float, wall: float, mem: int) -> EvalResult:
        _, res = run_with_harness(
            program_source, HARNESS, cpu=cpu, wall=wall, mem=mem,
            payload={"seed": 1, "trials": 256},
        )
        return res

    def describe(self) -> str:
        return (
            "4x4 matrix multiplication over GF(2). Return {'products': [[a_mask,"
            " b_mask], ...], 'C': [16 XOR-recipe masks]} from solve(). a_mask and"
            " b_mask are 16-bit masks selecting entries of A (resp. B) row-major;"
            " each product is the parity of A-sum times parity of B-sum; C recipes"
            " say which products to XOR. Minimize number of products."
        )
