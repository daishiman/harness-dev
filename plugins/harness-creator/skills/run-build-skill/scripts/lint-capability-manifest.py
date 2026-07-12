#!/usr/bin/env python3
# 発火: PostToolUse:Edit|Write hook (Claude Code)
# 副作用境界: stderr に lint 結果のみ。ファイル変更なし。常に exit 0(非ブロック)。
# 想定 input: {"tool_input": {"file_path": "..."}} 形式 JSON。
# 対象: SKILL.md / commands|agents の *.md / plugin-composition.yaml。
"""CapabilityManifest schema で frontmatter を検証する lint hook (非ブロック)."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

try:
    import jsonschema  # type: ignore

    HAS_JSONSCHEMA = True
except Exception:
    HAS_JSONSCHEMA = False

try:
    import yaml  # type: ignore

    HAS_YAML = True
except Exception:
    HAS_YAML = False

SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent
    / "references"
    / "capability-manifest.schema.json"
)


def _read_stdin_json() -> dict:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return {}
        return json.loads(raw)
    except Exception:
        return {}


def _is_target(path: Path) -> bool:
    name = path.name
    if name == "SKILL.md":
        return True
    if name == "plugin-composition.yaml":
        return True
    if path.suffix == ".md":
        parts = {p.lower() for p in path.parts}
        if "commands" in parts or "agents" in parts:
            return True
    return False


def _extract_frontmatter(text: str) -> dict | None:
    # YAML frontmatter (--- ... ---) を抽出し、簡易 key:value パース
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not m:
        return None
    block = m.group(1)
    data: dict = {}
    for line in block.splitlines():
        line = line.rstrip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line or line.startswith(" "):
            # ネスト/リストはスタブでは無視
            continue
        key, _, val = line.partition(":")
        data[key.strip()] = val.strip().strip('"').strip("'")
    return data


def _stringify_dates(obj):
    # YAML は無引用の日付を datetime.date に自動変換するが schema は string を要求するため ISO 文字列へ正規化する。
    import datetime

    if isinstance(obj, dict):
        return {k: _stringify_dates(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_stringify_dates(v) for v in obj]
    if isinstance(obj, (datetime.date, datetime.datetime)):
        return obj.isoformat()
    return obj


def _load_composition(text: str) -> tuple[dict | None, str]:
    # plugin-composition.yaml は frontmatter ではなくファイル全体が YAML ドキュメント。
    # yaml があれば全文パース、無ければ最上位キーのみの最小パースへ graceful fallback する。
    if HAS_YAML:
        try:
            data = yaml.safe_load(text)
            if isinstance(data, dict):
                return _stringify_dates(data), "yaml"
            return None, "yaml"
        except Exception:
            return None, "yaml"
    # 最小パース: インデントなし top-level `key:` 行のみ拾う (yaml 非搭載環境の safety net)
    data = {}
    for line in text.splitlines():
        if not line or line[0] in (" ", "\t", "#", "-"):
            continue
        if ":" in line:
            key = line.split(":", 1)[0].strip()
            if key:
                data.setdefault(key, True)
    return data, "minimal"


def _composition_errors(data: dict, mode: str, schema: dict | None) -> list[str]:
    if mode == "yaml" and HAS_JSONSCHEMA and schema:
        try:
            jsonschema.validate(data, schema)
            return []
        except jsonschema.ValidationError as e:  # type: ignore
            return [str(e.message)]
        except Exception as e:
            return [f"validator error: {e}"]
    # fallback: kindPluginComposition の必須キーのみ確認
    errors = []
    for key in ("name", "kind", "capabilities"):
        if key not in data or not data[key]:
            errors.append(f"missing required key: {key}")
    if data.get("kind") not in (None, True) and data.get("kind") != "plugin-composition":
        errors.append("kind must be 'plugin-composition'")
    return errors


def _load_schema() -> dict | None:
    try:
        if SCHEMA_PATH.exists():
            return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None
    return None


def _fallback_check(fm: dict) -> list[str]:
    # jsonschema 無しでも最低限の必須キーを確認
    errors = []
    for key in ("name", "description"):
        if key not in fm or not fm[key]:
            errors.append(f"missing required key: {key}")
    return errors


def main() -> int:
    try:
        payload = _read_stdin_json()
        tool_input = payload.get("tool_input") or {}
        file_path_str = tool_input.get("file_path") or ""
        if not file_path_str:
            return 0
        path = Path(file_path_str)
        if not _is_target(path) or not path.exists():
            return 0

        text = path.read_text(encoding="utf-8", errors="ignore")
        schema = _load_schema()
        errors: list[str] = []
        schema_used = False

        if path.name == "plugin-composition.yaml":
            # ファイル全体を YAML ドキュメントとして検証する (frontmatter ではない)。
            data, mode = _load_composition(text)
            if data is None:
                sys.stderr.write(
                    json.dumps(
                        {
                            "hook": "lint-capability-manifest",
                            "file": str(path),
                            "error": "yaml parse failed",
                        },
                        ensure_ascii=False,
                    )
                )
                return 0
            errors = _composition_errors(data, mode, schema)
            schema_used = bool(mode == "yaml" and HAS_JSONSCHEMA and schema)
        else:
            fm = _extract_frontmatter(text)
            if fm is None:
                sys.stderr.write(
                    json.dumps(
                        {
                            "hook": "lint-capability-manifest",
                            "file": str(path),
                            "error": "frontmatter not found",
                        },
                        ensure_ascii=False,
                    )
                )
                return 0
            if HAS_JSONSCHEMA and schema:
                schema_used = True
                try:
                    jsonschema.validate(fm, schema)
                except jsonschema.ValidationError as e:  # type: ignore
                    errors.append(str(e.message))
                except Exception as e:
                    errors.append(f"validator error: {e}")
            else:
                errors.extend(_fallback_check(fm))

        if errors:
            sys.stderr.write(
                json.dumps(
                    {
                        "hook": "lint-capability-manifest",
                        "file": str(path),
                        "errors": errors,
                        "schema_used": schema_used,
                    },
                    ensure_ascii=False,
                )
            )
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
