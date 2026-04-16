from zero.problems import get_problem
from zero.problems.sortnet8 import Sortnet8Problem
from zero.problems.matmul44_z2 import Matmul44Z2Problem
from zero.problems.capset import CapsetProblem


def test_sortnet8_seed_is_correct():
    prob = Sortnet8Problem()
    res = prob.evaluate(prob.seed_program(), cpu=5, wall=10, mem=256)
    assert res.valid
    assert res.score == 19


def test_sortnet8_detects_invalid_network():
    prob = Sortnet8Problem()
    bad = "def solve(): return [(0,1)]\n"
    res = prob.evaluate(bad, cpu=5, wall=10, mem=256)
    assert not res.valid


def test_matmul44_seed_is_correct_naive():
    prob = Matmul44Z2Problem()
    res = prob.evaluate(prob.seed_program(), cpu=10, wall=20, mem=512)
    assert res.valid
    assert res.score == 64


def test_matmul44_rejects_wrong_recipe():
    prob = Matmul44Z2Problem()
    bad = "def solve(): return {'products': [], 'C': [0]*16}\n"
    res = prob.evaluate(bad, cpu=5, wall=10, mem=256)
    assert not res.valid


def test_capset_seed_is_valid():
    prob = CapsetProblem(n=4)
    res = prob.evaluate(prob.seed_program(), cpu=5, wall=10, mem=256)
    assert res.valid
    # {0,1}^4 cap set has size 16.
    assert res.score == 16


def test_capset_detects_three_term_ap():
    bad = (
        "def solve():\n"
        "    return {'n': 3, 'vectors': [[0,0,0],[1,1,1],[2,2,2]]}\n"
    )
    res = CapsetProblem(n=3).evaluate(bad, cpu=5, wall=10, mem=256)
    assert not res.valid


def test_get_problem_registry():
    assert get_problem("sortnet8").name == "sortnet8"
    assert get_problem("matmul44_z2").name == "matmul44_z2"
    assert get_problem("capset:6").baseline_score == 112.0
