"""LLM mutation orchestrator.

Fans out parallel mutation calls to Anthropic's `claude-opus-4-6` using the
Replit AI Integrations proxy. All prompts and responses are cached on disk by
hash so runs are replayable without re-spending tokens.

Required env vars (provisioned by Replit):
    AI_INTEGRATIONS_ANTHROPIC_BASE_URL
    AI_INTEGRATIONS_ANTHROPIC_API_KEY

Never hard-code keys.
"""
from __future__ import annotations
import concurrent.futures as cf
import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .config import LLMConfig


@dataclass
class Mutation:
    source: str
    prompt: str
    response: str
    temperature: float
    cached: bool
    elapsed: float
    error: str | None = None


SYSTEM_PROMPT = (
    "You are an expert algorithm designer collaborating on an evolutionary search "
    "for better algorithms. You receive a problem description and one or more "
    "current candidate Python programs with their scores. Your job is to propose "
    "a NEW program that is likely to score better.\n\n"
    "Hard rules:\n"
    "- Reply with EXACTLY one fenced Python code block: ```python ...```\n"
    "- The program must define `solve()` and follow the problem's I/O contract.\n"
    "- No external imports beyond the Python standard library.\n"
    "- No explanation outside the code block.\n"
    "- Prefer small, targeted edits over full rewrites when the current best is close.\n"
)


def _hash_prompt(model: str, temperature: float, prompt: str) -> str:
    h = hashlib.sha256()
    h.update(model.encode())
    h.update(f"|{temperature:.4f}|".encode())
    h.update(prompt.encode())
    return h.hexdigest()


def _load_cached(cache_dir: Path, key: str) -> str | None:
    p = cache_dir / f"{key}.json"
    if p.exists():
        try:
            return json.loads(p.read_text())["response"]
        except Exception:
            return None
    return None


def _save_cached(cache_dir: Path, key: str, prompt: str, response: str) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / f"{key}.json").write_text(
        json.dumps({"prompt": prompt, "response": response})
    )


_CODE_BLOCK_RE = re.compile(r"```(?:python)?\s*(.*?)```", re.DOTALL)


def extract_code(response: str) -> str | None:
    m = _CODE_BLOCK_RE.search(response)
    if not m:
        return None
    code = m.group(1).strip()
    return code if code else None


def build_prompt(problem_description: str, top_programs: list[tuple[str, float | None]]) -> str:
    parts = [
        "# Problem",
        problem_description,
        "",
        "# Current best candidates (lower score or higher score depending on the problem):",
    ]
    for i, (src, score) in enumerate(top_programs):
        parts.append(f"\n## Candidate {i} — score={score}")
        parts.append("```python")
        parts.append(src.strip())
        parts.append("```")
    parts.append(
        "\n# Task\nPropose a NEW program that likely scores better. Output exactly one "
        "```python``` block containing the full program, no commentary."
    )
    return "\n".join(parts)


class LLMOrchestrator:
    """Fans out parallel mutation calls, caches on disk, handles errors."""

    def __init__(
        self,
        cfg: LLMConfig,
        *,
        db_logger: Callable[..., None] | None = None,
        enabled: bool = True,
    ):
        self.cfg = cfg
        self.cache_dir = Path(cfg.cache_dir)
        self._db_logger = db_logger
        self._client: Any | None = None
        self.enabled = enabled and self._env_ready()

    @staticmethod
    def _env_ready() -> bool:
        return bool(
            os.environ.get("AI_INTEGRATIONS_ANTHROPIC_BASE_URL")
            and os.environ.get("AI_INTEGRATIONS_ANTHROPIC_API_KEY")
        )

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            import anthropic  # type: ignore
        except ImportError as e:  # pragma: no cover
            raise RuntimeError("anthropic package not installed") from e
        self._client = anthropic.Anthropic(
            base_url=os.environ["AI_INTEGRATIONS_ANTHROPIC_BASE_URL"],
            api_key=os.environ["AI_INTEGRATIONS_ANTHROPIC_API_KEY"],
        )
        return self._client

    def _single_call(
        self,
        prompt: str,
        temperature: float,
        *,
        generation: int,
        island: int | None,
    ) -> Mutation:
        key = _hash_prompt(self.cfg.model, temperature, prompt)
        cached = _load_cached(self.cache_dir, key)
        if cached is not None:
            mut = Mutation(
                source=extract_code(cached) or "",
                prompt=prompt,
                response=cached,
                temperature=temperature,
                cached=True,
                elapsed=0.0,
            )
            if self._db_logger:
                self._db_logger(
                    generation=generation, island=island, model=self.cfg.model,
                    temperature=temperature, prompt_hash=key, prompt=prompt,
                    response=cached, cached=True, elapsed=0.0,
                )
            return mut

        if not self.enabled:
            return Mutation(
                source="", prompt=prompt, response="", temperature=temperature,
                cached=False, elapsed=0.0, error="llm disabled",
            )

        client = self._get_client()
        t0 = time.monotonic()
        try:
            msg = client.messages.create(
                model=self.cfg.model,
                max_tokens=self.cfg.max_tokens,
                system=SYSTEM_PROMPT,
                temperature=temperature,
                messages=[{"role": "user", "content": prompt}],
            )
            # Concatenate text blocks.
            text_parts = []
            for block in getattr(msg, "content", []) or []:
                t = getattr(block, "text", None)
                if t:
                    text_parts.append(t)
            response = "".join(text_parts)
        except Exception as e:  # network, rate-limit, parse — all non-fatal.
            return Mutation(
                source="", prompt=prompt, response="", temperature=temperature,
                cached=False, elapsed=time.monotonic() - t0, error=repr(e),
            )
        elapsed = time.monotonic() - t0
        _save_cached(self.cache_dir, key, prompt, response)
        source = extract_code(response) or ""
        if self._db_logger:
            self._db_logger(
                generation=generation, island=island, model=self.cfg.model,
                temperature=temperature, prompt_hash=key, prompt=prompt,
                response=response, cached=False, elapsed=elapsed,
            )
        return Mutation(
            source=source, prompt=prompt, response=response,
            temperature=temperature, cached=False, elapsed=elapsed,
        )

    def fan_out(
        self,
        prompt: str,
        *,
        generation: int,
        island: int | None,
    ) -> list[Mutation]:
        """Issue parallel calls at the configured temperatures."""
        if not self.cfg.temperatures:
            return []
        results: list[Mutation] = []
        with cf.ThreadPoolExecutor(max_workers=self.cfg.parallel_calls) as pool:
            futures = [
                pool.submit(self._single_call, prompt, t, generation=generation, island=island)
                for t in self.cfg.temperatures[: self.cfg.parallel_calls]
            ]
            for fut in cf.as_completed(futures):
                results.append(fut.result())
        return results
