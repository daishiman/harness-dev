#!/usr/bin/env python3
# 発火: UserPromptSubmit hook (Claude Code)
# 副作用境界: stdout に hint(JSON) を出力するのみ。FS/network 変更なし。
# 想定 input: {"prompt": "..."} 形式の JSON を stdin から読み取る。
# 失敗時: silent exit 0 (Claude をブロックしない)。
"""ref-task-context-map の context-map から prompt に該当する ref を抽出する preload hook."""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
CONTEXT_MAP_CANDIDATES = [
    SKILL_DIR / "references" / "context-map.yaml",
    SKILL_DIR / "references" / "context-map.json",
    SKILL_DIR / "references" / "task-context-map.yaml",
]


def _read_stdin_json() -> dict:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return {}
        return json.loads(raw)
    except Exception:
        return {}


def _load_context_map() -> str:
    for path in CONTEXT_MAP_CANDIDATES:
        try:
            if path.exists():
                return path.read_text(encoding="utf-8")
        except Exception:
            continue
    return ""


def _grep_refs(prompt: str, corpus: str) -> list[str]:
    if not prompt or not corpus:
        return []
    hits: list[str] = []
    # corpus 内の `ref-*` / `run-*` / `wrap-*` 識別子を抽出
    tokens = set(re.findall(r"\b(?:ref|run|wrap)-[a-z0-9][a-z0-9-]*", corpus))
    prompt_lower = prompt.lower()
    for tok in tokens:
        # トークンに含まれるキーワード(ハイフン分割)が prompt に登場すれば候補
        keywords = [k for k in tok.split("-")[1:] if len(k) >= 3]
        if any(k in prompt_lower for k in keywords):
            hits.append(tok)
    return sorted(set(hits))[:10]


def main() -> int:
    try:
        payload = _read_stdin_json()
        prompt = payload.get("prompt") or payload.get("user_prompt") or ""
        corpus = _load_context_map()
        refs = _grep_refs(prompt, corpus)
        if refs:
            hint = {
                "hook": "preload-context-map",
                "suggested_refs": refs,
                "source": "ref-task-context-map",
            }
            sys.stdout.write(json.dumps(hint, ensure_ascii=False))
    except Exception:
        # silent: プラグインが Claude を止めないこと最優先
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
