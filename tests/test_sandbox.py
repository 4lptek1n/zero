from zero.sandbox import run_harness, SandboxSuccess, SandboxFailure


GOOD_HARNESS = r'''
import json, os
src = open(os.environ["ZERO_PROGRAM_PATH"]).read()
ns = {}
exec(src, ns)
print(json.dumps({"valid": True, "score": ns["value"]}))
'''


def test_happy_path():
    res = run_harness("value = 42\n", GOOD_HARNESS, cpu_seconds=5, wall_seconds=5, memory_mb=256)
    assert isinstance(res, SandboxSuccess)
    assert res.result == {"valid": True, "score": 42}


def test_timeout():
    res = run_harness("while True: pass\n", GOOD_HARNESS,
                      cpu_seconds=1, wall_seconds=2, memory_mb=128)
    assert isinstance(res, SandboxFailure)
    assert res.kind in ("timeout", "crash")  # SIGXCPU may surface as crash


def test_syntax_error():
    res = run_harness("def broken(\n", GOOD_HARNESS,
                      cpu_seconds=3, wall_seconds=5, memory_mb=256)
    assert isinstance(res, SandboxFailure)
    assert res.kind in ("crash", "invalid_output")


def test_invalid_output():
    bad_harness = "print('no json here')\n"
    res = run_harness("x = 1\n", bad_harness, cpu_seconds=3, wall_seconds=5, memory_mb=256)
    assert isinstance(res, SandboxFailure)
    assert res.kind == "invalid_output"
