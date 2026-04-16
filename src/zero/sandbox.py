"""Subprocess-based sandbox executor with resource limits.

No eval(), no shared interpreter state. Every candidate runs in a fresh
Python subprocess with CPU/memory/wall-clock limits enforced via the
`resource` module.
"""
from __future__ import annotations
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Union


@dataclass
class SandboxSuccess:
    kind: Literal["ok"] = "ok"
    result: Any = None
    runtime_seconds: float = 0.0
    stdout: str = ""
    stderr: str = ""


@dataclass
class SandboxFailure:
    kind: Literal[
        "timeout",
        "crash",
        "invalid_output",
        "invalid_program",
        "memory",
    ]
    message: str = ""
    runtime_seconds: float = 0.0
    stdout: str = ""
    stderr: str = ""


SandboxResult = Union[SandboxSuccess, SandboxFailure]


_LIMITER_PREAMBLE = '''
import resource, sys, json
def _apply_limits(cpu_seconds, memory_mb):
    try:
        resource.setrlimit(resource.RLIMIT_CPU, (int(cpu_seconds)+1, int(cpu_seconds)+2))
    except Exception:
        pass
    try:
        mem = int(memory_mb) * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (mem, mem))
    except Exception:
        pass
'''


def run_harness(
    program_source: str,
    harness_source: str,
    *,
    cpu_seconds: float = 5.0,
    wall_seconds: float = 10.0,
    memory_mb: int = 512,
    input_payload: dict | None = None,
) -> SandboxResult:
    """Run a candidate `program_source` through a per-problem `harness_source`.

    The harness script should:
      - import json, sys
      - read program source from environment variable ZERO_PROGRAM_PATH
      - read input payload from env ZERO_INPUT_PATH (JSON)
      - exec() the program in a fresh namespace
      - produce a JSON object on stdout with at minimum {"ok": bool}
    """
    with tempfile.TemporaryDirectory(prefix="zero_sbx_") as tmp:
        tmp_path = Path(tmp)
        prog_path = tmp_path / "candidate.py"
        prog_path.write_text(program_source)
        input_path = tmp_path / "input.json"
        input_path.write_text(json.dumps(input_payload or {}))
        harness_path = tmp_path / "_harness.py"
        harness_path.write_text(
            _LIMITER_PREAMBLE
            + f"_apply_limits({cpu_seconds}, {memory_mb})\n"
            + harness_source
        )

        env = {
            "ZERO_PROGRAM_PATH": str(prog_path),
            "ZERO_INPUT_PATH": str(input_path),
            "PYTHONUNBUFFERED": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PATH": os.environ.get("PATH", ""),
        }

        import time
        t0 = time.monotonic()
        try:
            proc = subprocess.run(
                [sys.executable, "-I", "-B", str(harness_path)],
                env=env,
                cwd=tmp,
                capture_output=True,
                timeout=wall_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as e:
            return SandboxFailure(
                kind="timeout",
                message=f"wall timeout after {wall_seconds}s",
                runtime_seconds=wall_seconds,
                stdout=(e.stdout or b"").decode("utf-8", "replace")[-2000:],
                stderr=(e.stderr or b"").decode("utf-8", "replace")[-2000:],
            )
        elapsed = time.monotonic() - t0
        stdout = proc.stdout.decode("utf-8", "replace")
        stderr = proc.stderr.decode("utf-8", "replace")

        if proc.returncode != 0:
            kind: Literal["crash", "memory"] = "crash"
            if "MemoryError" in stderr:
                kind = "memory"
            return SandboxFailure(
                kind=kind,
                message=f"exit {proc.returncode}",
                runtime_seconds=elapsed,
                stdout=stdout[-2000:],
                stderr=stderr[-2000:],
            )

        # Last non-empty line of stdout is the JSON result.
        payload_line = ""
        for line in reversed(stdout.strip().splitlines()):
            s = line.strip()
            if s.startswith("{") and s.endswith("}"):
                payload_line = s
                break
        if not payload_line:
            return SandboxFailure(
                kind="invalid_output",
                message="no JSON payload on stdout",
                runtime_seconds=elapsed,
                stdout=stdout[-2000:],
                stderr=stderr[-2000:],
            )
        try:
            data = json.loads(payload_line)
        except json.JSONDecodeError as e:
            return SandboxFailure(
                kind="invalid_output",
                message=f"json decode: {e}",
                runtime_seconds=elapsed,
                stdout=stdout[-2000:],
                stderr=stderr[-2000:],
            )
        return SandboxSuccess(
            result=data,
            runtime_seconds=elapsed,
            stdout=stdout[-2000:],
            stderr=stderr[-2000:],
        )
