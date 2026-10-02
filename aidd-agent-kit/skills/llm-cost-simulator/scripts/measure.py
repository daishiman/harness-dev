"""Empirical token measurement for llm-cost-simulator (the grounding ladder).

Tiers
-----
T1  free exact INPUT count:
      - Anthropic: POST /v1/messages/count_tokens  (free, no spend)
      - OpenAI:    tiktoken locally (no spend)
T2  representative OUTPUT sample via Claude on the *ambient* auth:
      runs the probe once (or N times) on a Claude model and reads
      response.usage. For Claude Code / subscription users this draws on the
      plan quota via `ant auth login` (OAuth) or ANTHROPIC_API_KEY. For a
      NON-Claude target model, pass --proxy-model to sample output size on a
      cheap Claude model and price it against the target (output length is a
      proxy — disclose it).
T3  ground-truth on the actual provider (spends real money). Gated behind
      --yes-spend AND an interactive confirmation. Never silent.

Auth (read from environment / SDK profile — never hardcode keys):
  Anthropic: ANTHROPIC_API_KEY, ANTHROPIC_AUTH_TOKEN, or `ant auth login`.
  OpenAI:    OPENAI_API_KEY.

Probe file (JSON):
  {
    "provider": "anthropic",
    "model": "claude-haiku-4-5",
    "system": "....",
    "tools": [ {..tool json schemas..} ],
    "messages": [ {"role": "user", "content": "...representative input..."} ],
    "max_tokens": 1024,
    "samples": 1
  }

Usage:
  python measure.py probe.json                 # T1 input count only (free)
  python measure.py probe.json --run           # T1 + T2 sample (Claude quota)
  python measure.py probe.json --run --proxy-model claude-haiku-4-5
  python measure.py probe.json --run --yes-spend   # T3 (paid, confirmed)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


def _eprint(*a: Any) -> None:
    print(*a, file=sys.stderr)


# --------------------------------------------------------------------------- #
# T1 — free input counting
# --------------------------------------------------------------------------- #
def count_input_anthropic(probe: dict[str, Any]) -> int | None:
    try:
        import anthropic  # type: ignore
    except ImportError:
        _eprint("[T1] anthropic SDK not installed (pip install anthropic). Skipping exact count.")
        return None
    try:
        client = anthropic.Anthropic()
        kwargs: dict[str, Any] = {
            "model": probe["model"],
            "messages": probe.get("messages", [{"role": "user", "content": ""}]),
        }
        if probe.get("system"):
            kwargs["system"] = probe["system"]
        if probe.get("tools"):
            kwargs["tools"] = probe["tools"]
        resp = client.messages.count_tokens(**kwargs)
        return int(resp.input_tokens)
    except Exception as exc:  # noqa: BLE001 - surface any auth/network error clearly
        _eprint(f"[T1] count_tokens failed ({type(exc).__name__}): {exc}")
        _eprint("     Check auth: set ANTHROPIC_API_KEY or run `ant auth login`.")
        return None


def count_input_openai(probe: dict[str, Any]) -> int:
    # serialize system + messages to text for an approximate-exact tiktoken count
    from engine import count_tokens_openai  # local import; same scripts dir

    parts = [probe.get("system", "")]
    for m in probe.get("messages", []):
        c = m.get("content", "")
        parts.append(c if isinstance(c, str) else json.dumps(c, ensure_ascii=False))
    if probe.get("tools"):
        parts.append(json.dumps(probe["tools"], ensure_ascii=False))
    return count_tokens_openai("\n".join(parts), probe.get("model", "gpt-4o"))


# --------------------------------------------------------------------------- #
# T2 / T3 — output sampling
# --------------------------------------------------------------------------- #
def sample_anthropic(probe: dict[str, Any], model: str, n: int) -> list[dict[str, int]]:
    import anthropic  # type: ignore

    client = anthropic.Anthropic()
    samples: list[dict[str, int]] = []
    for i in range(max(1, n)):
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": int(probe.get("max_tokens", 1024)),
            "messages": probe.get("messages", [{"role": "user", "content": ""}]),
        }
        if probe.get("system"):
            kwargs["system"] = probe["system"]
        if probe.get("tools"):
            kwargs["tools"] = probe["tools"]
        resp = client.messages.create(**kwargs)
        u = resp.usage
        samples.append(
            {
                "input": int(getattr(u, "input_tokens", 0)),
                "output": int(getattr(u, "output_tokens", 0)),
                "cache_read": int(getattr(u, "cache_read_input_tokens", 0) or 0),
                "cache_write": int(getattr(u, "cache_creation_input_tokens", 0) or 0),
            }
        )
        _eprint(f"[T2] sample {i + 1}/{n} on {model}: {samples[-1]}")
    return samples


def sample_openai(probe: dict[str, Any], model: str, n: int) -> list[dict[str, int]]:
    from openai import OpenAI  # type: ignore

    client = OpenAI()
    samples: list[dict[str, int]] = []
    for i in range(max(1, n)):
        messages = probe.get("messages", [{"role": "user", "content": ""}])
        if probe.get("system"):
            messages = [{"role": "system", "content": probe["system"]}, *messages]
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            max_completion_tokens=int(probe.get("max_tokens", 1024)),
        )
        u = resp.usage
        samples.append(
            {"input": int(u.prompt_tokens), "output": int(u.completion_tokens)}
        )
        _eprint(f"[T3] sample {i + 1}/{n} on {model}: {samples[-1]}")
    return samples


def _summarize(samples: list[dict[str, int]], key: str) -> dict[str, float]:
    vals = [s.get(key, 0) for s in samples]
    if not vals:
        return {"min": 0, "avg": 0, "max": 0}
    return {"min": min(vals), "avg": sum(vals) / len(vals), "max": max(vals)}


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(description="Measure real token usage for a probe.")
    ap.add_argument("probe", help="probe JSON file")
    ap.add_argument("--run", action="store_true", help="run a sample to measure output tokens")
    ap.add_argument("--samples", type=int, default=0, help="override sample count")
    ap.add_argument(
        "--proxy-model",
        default=None,
        help="sample output on this Claude model instead of the target (for non-Claude targets)",
    )
    ap.add_argument(
        "--yes-spend",
        action="store_true",
        help="permit a PAID call on a non-Anthropic provider (still asks to confirm)",
    )
    args = ap.parse_args()

    probe = json.loads(Path(args.probe).read_text(encoding="utf-8"))
    provider = probe.get("provider", "anthropic")
    target_model = probe["model"]
    n = args.samples or int(probe.get("samples", 1))

    result: dict[str, Any] = {"provider": provider, "model": target_model, "tiers_used": []}

    # ---- T1: input ----
    if provider == "anthropic":
        ti = count_input_anthropic(probe)
        if ti is not None:
            result["input_tokens_exact"] = ti
            result["tiers_used"].append("T1:count_tokens(free)")
    else:
        result["input_tokens_exact"] = count_input_openai(probe)
        result["tiers_used"].append("T1:tiktoken(local)")
    print(f"[T1] exact input tokens: {result.get('input_tokens_exact', 'unavailable')}")

    # ---- T2 / T3: output ----
    if args.run:
        proxy = args.proxy_model
        if provider == "anthropic" and proxy is None:
            samples = sample_anthropic(probe, target_model, n)
            result["tiers_used"].append(f"T2:claude-sample({target_model})")
        elif proxy is not None:
            _eprint(f"[T2] sampling output size on PROXY {proxy}; pricing target = {target_model}.")
            _eprint("     NOTE: output length differs across models — treat as an estimate.")
            samples = sample_anthropic(probe, proxy, n)
            result["proxy_model"] = proxy
            result["tiers_used"].append(f"T2:proxy({proxy})")
        else:
            # paid, non-Anthropic, no proxy
            if not args.yes_spend:
                _eprint(
                    f"[T3] {provider} '{target_model}' would incur REAL cost. "
                    "Re-run with --yes-spend, or use --proxy-model <claude model> for a free estimate."
                )
                _emit(result)
                return 2
            ans = input(f"Spend real money calling {provider}:{target_model} x{n}? [y/N] ").strip().lower()
            if ans not in ("y", "yes"):
                _eprint("[T3] aborted by user.")
                _emit(result)
                return 2
            samples = sample_openai(probe, target_model, n)
            result["tiers_used"].append(f"T3:live({target_model})")

        result["samples"] = samples
        result["output_tokens"] = _summarize(samples, "output")
        result["measured_input_tokens"] = _summarize(samples, "input")
        print(f"[done] output tokens (min/avg/max): "
              f"{result['output_tokens']['min']:.0f} / "
              f"{result['output_tokens']['avg']:.0f} / "
              f"{result['output_tokens']['max']:.0f}")

    _emit(result)
    return 0


def _emit(result: dict[str, Any]) -> None:
    print("\n--- measurement (JSON) ---")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    raise SystemExit(main())
