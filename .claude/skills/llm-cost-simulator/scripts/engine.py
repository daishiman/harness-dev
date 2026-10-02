"""Cost engine for llm-cost-simulator.

Pure cost math over a pricing table (data/pricing.json) and a scenario
description. No network, no third-party deps required for the core math.
tiktoken is imported lazily only by the optional OpenAI token counter.

Token accounting model (per call):
  full-price input = system + tools + context + history + user_input
  cached read pool  = cache_read           (priced at the cached/read rate)
  cached write pool = cache_write           (priced at the write rate)
  output            = output + thinking     (thinking/reasoning billed as output)
  total prompt tokens = full-price input + cache_read + cache_write

Caching can be expressed two ways on a call's "tokens":
  - explicit:   {"cache_read": N, "cache_write": M}
  - rate-based: {"cacheable_prefix": P}  -> split by cache_hit_rate into
                read = P*hit, write = P*(1-hit)

Agent loops accumulate history; see cost_for_call -> _agent_loop_cost.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

COMPONENT_KEYS = ("system", "tools", "context", "history", "user_input")
OUTPUT_KEYS = ("output", "thinking")


# --------------------------------------------------------------------------- #
# Pricing table
# --------------------------------------------------------------------------- #
def load_pricing(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"pricing file not found: {p}")
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"pricing file is not valid JSON: {p}: {exc}") from exc


def get_model(pricing: dict[str, Any], model_id: str) -> dict[str, Any]:
    """Return a model record with provider defaults merged in (immutably)."""
    match = next((m for m in pricing.get("models", []) if m.get("id") == model_id), None)
    if match is None:
        known = ", ".join(sorted(m.get("id", "?") for m in pricing.get("models", [])))
        raise KeyError(f"model '{model_id}' not in pricing table. Known: {known}")
    provider = match.get("provider", "generic")
    defaults = pricing.get("provider_defaults", {}).get(provider, {})
    generic = pricing.get("provider_defaults", {}).get("generic", {})
    # precedence: model record > provider defaults > generic defaults
    return {**generic, **defaults, **match}


# --------------------------------------------------------------------------- #
# Rate resolution
# --------------------------------------------------------------------------- #
def resolve_rates(model: dict[str, Any], total_input_tokens: float) -> dict[str, float]:
    """Resolve effective per-1M rates, honoring context tiers and cached price."""
    in_price = float(model["input"])
    out_price = float(model["output"])
    for tier in sorted(
        model.get("context_tiers", []),
        key=lambda t: t.get("min_input_tokens", 0),
    ):
        if total_input_tokens >= tier.get("min_input_tokens", 0):
            in_price = float(tier.get("input", in_price))
            out_price = float(tier.get("output", out_price))

    read_mult = float(model.get("cache_read_mult", 0.5))
    if model.get("cached_input") is not None:
        read_price = float(model["cached_input"])
    else:
        read_price = in_price * read_mult

    write_mult_5m = float(model.get("cache_write_5m_mult", 1.0))
    write_mult_1h = float(model.get("cache_write_1h_mult", 1.0))
    return {
        "input": in_price,
        "output": out_price,
        "cache_read": read_price,
        "cache_write_5m": in_price * write_mult_5m,
        "cache_write_1h": in_price * write_mult_1h,
        "batch_mult": float(model.get("batch_mult", 1.0)),
    }


# --------------------------------------------------------------------------- #
# Per-call cost
# --------------------------------------------------------------------------- #
def _split_cache(tokens: dict[str, Any], cache_hit_rate: float) -> tuple[float, float]:
    cache_read = tokens.get("cache_read")
    cache_write = tokens.get("cache_write")
    prefix = tokens.get("cacheable_prefix")
    if cache_read is None and cache_write is None and prefix:
        hr = max(0.0, min(1.0, float(cache_hit_rate)))
        return float(prefix) * hr, float(prefix) * (1.0 - hr)
    return float(cache_read or 0), float(cache_write or 0)


def _usd(
    full_input: float,
    cache_read: float,
    cache_write: float,
    output: float,
    rates: dict[str, float],
    ttl: str,
    batch: bool,
) -> float:
    write_rate = rates["cache_write_1h"] if ttl == "1h" else rates["cache_write_5m"]
    raw = (
        full_input * rates["input"]
        + cache_read * rates["cache_read"]
        + cache_write * write_rate
        + output * rates["output"]
    ) / 1_000_000.0
    return raw * (rates["batch_mult"] if batch else 1.0)


def cost_for_call(
    call: dict[str, Any], pricing: dict[str, Any], cache_hit_rate: float = 0.0
) -> dict[str, Any]:
    """Cost of one call *per flow* (already multiplied by runs_per_flow / loop)."""
    model = get_model(pricing, call["model"])
    tokens = call.get("tokens", {})
    ttl = str(tokens.get("cache_write_ttl", "5m"))
    batch = bool(call.get("batch", False))
    runs = float(call.get("runs_per_flow", 1))

    if call.get("agent_loop"):
        per_run = _agent_loop_cost(call, model, cache_hit_rate, ttl, batch)
    else:
        full_input = sum(float(tokens.get(k, 0)) for k in COMPONENT_KEYS)
        cache_read, cache_write = _split_cache(tokens, cache_hit_rate)
        output = sum(float(tokens.get(k, 0)) for k in OUTPUT_KEYS)
        rates = resolve_rates(model, full_input + cache_read + cache_write)
        per_run = {
            "usd": _usd(full_input, cache_read, cache_write, output, rates, ttl, batch),
            "input_tokens": full_input,
            "cache_read_tokens": cache_read,
            "cache_write_tokens": cache_write,
            "output_tokens": output,
            "iterations": 1,
        }

    total_usd = per_run["usd"] * runs
    return {
        "id": call.get("id", call.get("label", "call")),
        "label": call.get("label", ""),
        "model": call["model"],
        "provider": model.get("provider"),
        "source_ref": call.get("source_ref", ""),
        "confidence": call.get("confidence", "estimated"),
        "runs_per_flow": runs,
        "batch": batch,
        "usd_per_flow": total_usd,
        "tokens": {
            "input": per_run["input_tokens"] * runs,
            "cache_read": per_run["cache_read_tokens"] * runs,
            "cache_write": per_run["cache_write_tokens"] * runs,
            "output": per_run["output_tokens"] * runs,
        },
        "iterations": per_run["iterations"],
        "assumptions": call.get("assumptions", []),
    }


def _agent_loop_cost(
    call: dict[str, Any],
    model: dict[str, Any],
    cache_hit_rate: float,
    ttl: str,
    batch: bool,
) -> dict[str, Any]:
    """Model a tool-use / agent loop where history accumulates each turn.

    iteration 0 writes the stable prefix to cache; later iterations read it.
    'history_growth_per_iter' tokens are added as input each subsequent turn
    (full price unless 'history_cached' is true, then priced at the read rate).
    """
    loop = call["agent_loop"]
    tokens = call.get("tokens", {})
    n = int(loop.get("iterations", 1))
    growth = float(loop.get("history_growth_per_iter", 0))
    prefix = float(loop.get("cached_prefix_tokens", tokens.get("cacheable_prefix", 0) or 0))
    history_cached = bool(loop.get("history_cached", False))

    base_input = sum(float(tokens.get(k, 0)) for k in COMPONENT_KEYS)
    out_per_iter = sum(float(tokens.get(k, 0)) for k in OUTPUT_KEYS)

    total = {"usd": 0.0, "input": 0.0, "cache_read": 0.0, "cache_write": 0.0, "output": 0.0}
    for i in range(max(1, n)):
        grown = growth * i
        if history_cached:
            fresh_input = base_input
            cache_read = (prefix if i > 0 else 0) + grown
            cache_write = prefix if i == 0 else 0
        else:
            fresh_input = base_input + grown
            cache_read = prefix if i > 0 else 0
            cache_write = prefix if i == 0 else 0
        rates = resolve_rates(model, fresh_input + cache_read + cache_write)
        total["usd"] += _usd(fresh_input, cache_read, cache_write, out_per_iter, rates, ttl, batch)
        total["input"] += fresh_input
        total["cache_read"] += cache_read
        total["cache_write"] += cache_write
        total["output"] += out_per_iter

    return {
        "usd": total["usd"],
        "input_tokens": total["input"],
        "cache_read_tokens": total["cache_read"],
        "cache_write_tokens": total["cache_write"],
        "output_tokens": total["output"],
        "iterations": max(1, n),
    }


# --------------------------------------------------------------------------- #
# Flow + projection
# --------------------------------------------------------------------------- #
def cost_for_flow(scenario: dict[str, Any], pricing: dict[str, Any]) -> dict[str, Any]:
    proj = scenario.get("projection", {})
    cache_hit_rate = float(proj.get("cache_hit_rate", 0.0))
    calls = [cost_for_call(c, pricing, cache_hit_rate) for c in scenario.get("calls", [])]
    total = sum(c["usd_per_flow"] for c in calls)
    agg = {
        "input": sum(c["tokens"]["input"] for c in calls),
        "cache_read": sum(c["tokens"]["cache_read"] for c in calls),
        "cache_write": sum(c["tokens"]["cache_write"] for c in calls),
        "output": sum(c["tokens"]["output"] for c in calls),
    }
    return {
        "usd_per_flow": total,
        "calls": calls,
        "tokens_per_flow": agg,
        "cache_hit_rate": cache_hit_rate,
    }


def project(usd_per_flow: float, scenario: dict[str, Any]) -> dict[str, Any]:
    proj = scenario.get("projection", {})
    volumes = proj.get("volumes", [1, 100, 1_000, 10_000, 100_000, 1_000_000])
    monthly_volume = proj.get("monthly_volume")
    table = [{"runs": v, "usd": usd_per_flow * v} for v in volumes]

    dau_rows = []
    flows_per = float(proj.get("flows_per_user_per_day", 1))
    for dau in proj.get("dau_scenarios", []):
        per_day = usd_per_flow * dau * flows_per
        dau_rows.append(
            {
                "dau": dau,
                "flows_per_user_per_day": flows_per,
                "usd_per_day": per_day,
                "usd_per_month": per_day * 30,
                "usd_per_year": per_day * 365,
            }
        )

    out: dict[str, Any] = {"volume_table": table, "dau_table": dau_rows}
    if monthly_volume:
        out["monthly"] = {
            "volume": monthly_volume,
            "usd_per_month": usd_per_flow * monthly_volume,
            "usd_per_year": usd_per_flow * monthly_volume * 12,
        }
    return out


def compare_models(
    scenario: dict[str, Any], pricing: dict[str, Any], model_ids: list[str]
) -> list[dict[str, Any]]:
    """Reprice the same token profile across candidate models (best-effort).

    Each candidate substitutes its id into every call, keeping the token
    counts fixed. Output-length differences across models are NOT modeled —
    this isolates the price effect of swapping the model.
    """
    rows = []
    for mid in model_ids:
        try:
            swapped = {
                **scenario,
                "calls": [{**c, "model": mid} for c in scenario.get("calls", [])],
            }
            flow = cost_for_flow(swapped, pricing)
            model = get_model(pricing, mid)
            rows.append(
                {
                    "model": mid,
                    "display_name": model.get("display_name", mid),
                    "confidence": model.get("confidence", "verify"),
                    "usd_per_flow": flow["usd_per_flow"],
                }
            )
        except KeyError:
            rows.append({"model": mid, "error": "not in pricing table"})
    return sorted(rows, key=lambda r: r.get("usd_per_flow", float("inf")))


# --------------------------------------------------------------------------- #
# Token counting helpers (optional, used by scenario authoring / measure.py)
# --------------------------------------------------------------------------- #
def count_tokens_heuristic(text: str, chars_per_token: float = 4.0) -> int:
    """Rough fallback when no tokenizer is available. Disclose as 'estimate'."""
    if not text:
        return 0
    return max(1, round(len(text) / chars_per_token))


def count_tokens_openai(text: str, model: str = "gpt-4o") -> int:
    """Exact-ish OpenAI input count via tiktoken if installed, else heuristic."""
    try:
        import tiktoken  # type: ignore
    except ImportError:
        return count_tokens_heuristic(text)
    try:
        enc = tiktoken.encoding_for_model(model)
    except KeyError:
        enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))
