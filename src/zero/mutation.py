"""Non-LLM mutation operators that edit candidate source code.

These are deterministic, syntax-aware-lite transforms that let the evolution
loop make progress even when `--no-llm` is set (smoke tests, CI). They are
intentionally simple; the real engine relies on the LLM orchestrator for
intelligent mutations.
"""
from __future__ import annotations
import random
import re
from typing import Callable


Mutator = Callable[[str, random.Random], str]


def _split_body(src: str) -> tuple[list[str], list[str]]:
    """Return (header_lines, body_lines). Header keeps all lines up to and
    including the first `def` definition line; body is indented content inside
    that function (best-effort, no AST parsing)."""
    lines = src.splitlines()
    header: list[str] = []
    body: list[str] = []
    in_body = False
    for line in lines:
        if not in_body:
            header.append(line)
            if line.lstrip().startswith("def "):
                in_body = True
            continue
        body.append(line)
    return header, body


def _reassemble(header: list[str], body: list[str]) -> str:
    return "\n".join(header + body) + ("\n" if not body or body[-1] else "")


def swap_adjacent_lines(src: str, rng: random.Random) -> str:
    header, body = _split_body(src)
    if len(body) < 2:
        return src
    i = rng.randrange(len(body) - 1)
    body[i], body[i + 1] = body[i + 1], body[i]
    return _reassemble(header, body)


def perturb_int_literal(src: str, rng: random.Random) -> str:
    ints = list(re.finditer(r"\b(\d+)\b", src))
    if not ints:
        return src
    m = rng.choice(ints)
    val = int(m.group(1))
    delta = rng.choice([-2, -1, 1, 2])
    new_val = max(0, val + delta)
    return src[: m.start()] + str(new_val) + src[m.end():]


def duplicate_last_tuple_in_list(src: str, rng: random.Random) -> str:
    # Duplicate a (i,j) tuple inside a bracketed list, useful for sortnet8.
    matches = list(re.finditer(r"\((\d+)\s*,\s*(\d+)\)", src))
    if not matches:
        return src
    m = rng.choice(matches)
    insertion = m.group(0) + ","
    return src[: m.end()] + insertion + src[m.end():]


def remove_random_tuple(src: str, rng: random.Random) -> str:
    # Remove a (i,j) tuple along with trailing comma or preceding comma.
    matches = list(re.finditer(r",?\s*\(\d+\s*,\s*\d+\)\s*,?", src))
    if not matches:
        return src
    m = rng.choice(matches)
    return src[: m.start()] + src[m.end():]


ALL_MUTATORS: list[Mutator] = [
    swap_adjacent_lines,
    perturb_int_literal,
    duplicate_last_tuple_in_list,
    remove_random_tuple,
]


def random_mutate(src: str, rng: random.Random) -> str:
    mutator = rng.choice(ALL_MUTATORS)
    return mutator(src, rng)


def crossover(src_a: str, src_b: str, rng: random.Random) -> str:
    """Very simple line-block crossover: pick a cut point in each source and
    splice. Keeps the header of A and swaps a body range with B."""
    ha, ba = _split_body(src_a)
    hb, bb = _split_body(src_b)
    if not ba or not bb:
        return src_a
    ca = rng.randrange(len(ba) + 1)
    cb = rng.randrange(len(bb) + 1)
    return _reassemble(ha, ba[:ca] + bb[cb:])
