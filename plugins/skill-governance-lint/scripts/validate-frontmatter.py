#!/usr/bin/env python3
# /// script
# name: validate-frontmatter
# purpose: Validate SKILL.md frontmatter fields and combination rules.
# inputs:
#   - argv: SKILL.md path, --skills-dir <dir>, or --self-test (schema と fallback の drift 検査)。どの形も余分な引数は usage error
# outputs:
#   - stdout: OK status (--help は usage)
#   - stderr: frontmatter findings (warn: で始まる指摘は exit に影響しない)
#   - exit: 0=ok (warn だけを含む) / 1=findings or self-test drift / 2=usage error (--skills-dir の走査 0 件と余分な引数を含む)
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""Validate Skill frontmatter: required fields and combination sanity.

Usage:
  validate-frontmatter.py /path/to/SKILL.md
  validate-frontmatter.py --skills-dir plugins/harness-creator/skills
  validate-frontmatter.py --self-test

frontmatter は YAML の部分集合として読む。scalar と list の要素は引用符を外し、
block list の途中のコメント行や空行は list を終わらせない。読めない・UTF-8 でない
SKILL.md は traceback にせず指摘として報告する。scalar のはずのキーが list で書かれて
いても、型の指摘にして残りの検査と残りの skill を続ける。パス形の参照は、実在しても
repo の外を指すなら指摘にする。

Exit 0 = ok (warn: だけの指摘を含む), 1 = 指摘あり / self-test の drift, 2 = usage error
(余分な引数を含む。2つ目以降のパスを黙って捨てると、検査したつもりの SKILL.md が素通りする).
--skills-dir は直下の */SKILL.md だけを見る。走査が 0 件なら 2 を返す。検査が空振り
したまま 0 を返すと、`--skills-dir plugins` のような打ち間違いで CI が素通りするので止める。
"""
from __future__ import annotations
import datetime
import json
import re
import sys
from pathlib import Path

# --- commonCore 必須集合の SSOT ローダー -------------------------------------
# 正本 = capability-manifest.schema.json#/definitions/commonCore.required。
# lint はこの正本を動的ロードし、必須集合のハードコードを廃する(三重定義の解消)。
# schema を読めない環境(配布断片化等)でのみ下記 fallback を使う。fallback と
# 正本の drift は `--self-test` (CI 配線可能) が検出して exit 1 する。
_FALLBACK_COMMON_CORE_REQUIRED = ("name", "description", "kind", "version", "owner")
_SCHEMA_RELPATH = (
    "plugins/harness-creator/skills/run-build-skill/references/capability-manifest.schema.json"
)


def _find_schema() -> Path | None:
    """__file__ から上位へ歩いて capability-manifest.schema.json を探す。"""
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        cand = parent / _SCHEMA_RELPATH
        if cand.exists():
            return cand
    return None


def _load_common_core_required() -> tuple[str, ...]:
    """commonCore.required を schema(正本)から読む。失敗時のみ fallback。"""
    schema = _find_schema()
    if schema is None:
        return _FALLBACK_COMMON_CORE_REQUIRED
    try:
        data = json.loads(schema.read_text(encoding="utf-8"))
        req = data["definitions"]["commonCore"]["required"]
        if isinstance(req, list) and req and all(isinstance(x, str) for x in req):
            return tuple(req)
    except (json.JSONDecodeError, KeyError, OSError):
        pass
    return _FALLBACK_COMMON_CORE_REQUIRED


# doc/21 source-traceability 準拠の必須化（ref-* は source 必須 / 他 kind は WARN）
SOURCE_REQUIRED_FOR_KIND = {"ref"}
SOURCE_TIER_VALUES = {
    # doc/21 source-traceability.md 定義に厳密準拠
    "article-text",      # 元記事 Markdown 本文を確認済み（Agent Skill 大全等）
    "image-derived",     # 画像 OCR / 手描き図由来の翻文を含む
    "code-unavailable",  # 実コード未取得（記事説明由来の推定）
    "code-verified",     # 実コードを取得し検証済み
    "internal",          # 本リポジトリ内部発祥（doc/ 配下の内製設計書を含む）
    "external-spec",     # 外部公式仕様書（claude.com docs 等）
}
KIND_VALUES = {"run", "ref", "assign", "wrap", "delegate", "workflow", "reference",
               "evaluator", "generator"}
# CapabilityManifest (capability-manifest.schema.json) の非 skill kind。
# SKILL.md 以外の Capability ファイル (agents/ commands/ hooks/ ...) で使う。
NON_SKILL_KINDS = {"agent", "hook", "command", "plugin-composition", "prompt", "workflow"}
# commonCore: 全 Capability kind 共通必須。正本は schema から動的ロード(SSOT)。
# SKILL.md / 非SKILL.md(agent/hook/...) の双方がこの同一集合を共有する。
COMMON_CORE_REQUIRED = _load_common_core_required()
# kind 固有の必須フィールド (同 schema の kind<Kind>.required)。
# agent の tools 宣言は oneOf (tools か tools-inherit: true のどちらか一方) なので
# ここには置かず、_agent_tools_errors で検査する。
KIND_SPECIFIC_REQUIRED = {
    "agent": ("isolation",),
    "command": ("argument-hint", "allowed-tools"),
    "hook": ("event", "command"),
    "plugin-composition": ("capabilities",),
    "prompt": ("layers",),
    "workflow": ("phases",),
}
SEMVER_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
EFFECT_VALUES = {"none", "conversation-output", "local-artifact", "external-mutation"}
MERGE_STRATEGY_VALUES = {"deep-merge", "strict", "override", "layered"}
CONFLICT_POLICY_VALUES = {"most-specific-wins", "error", "warn-and-merge"}
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# 検査が文字列として読むキー。list で書かれたら型の指摘にし、以降の検査では空の scalar として
# 扱う。traceback で落とすと --skills-dir の残りの skill が報告されないまま終わる。
SCALAR_FIELDS = tuple(dict.fromkeys((
    *COMMON_CORE_REQUIRED, "effect", "merge_strategy", "conflict_policy", "source",
    "source-tier", "last-audited", "cross_platform", "disable-model-invocation",
    "user-invocable", "context",
)))


def _scalar(fm: dict, key: str, default: str = "") -> str:
    """fm[key] を scalar として返す。list なら default (型の指摘は _scalar_type_errors が出す)。"""
    value = fm.get(key, default)
    return value if isinstance(value, str) else default


def _scalar_type_errors(fm: dict) -> list[str]:
    return [
        f"field '{key}' must be a scalar, got list: {fm[key]!r}"
        for key in SCALAR_FIELDS
        if isinstance(fm.get(key), list)
    ]


def _inside(repo: Path, path: Path) -> bool:
    """symlink をたどった実体が repo の中にあるか (lint-rubric-refs-exist.py と同じ扱い)。"""
    try:
        path.resolve().relative_to(repo.resolve())
    except (ValueError, OSError):
        return False
    return True


def _without_yaml_comment(value: str) -> str:
    """Keep quoted hashes and plain path fragments; remove actual YAML comments."""
    quote = None
    escaped = False
    scalar_start = True
    flow_list = value.lstrip().startswith('[')
    index = 0
    while index < len(value):
        char = value[index]
        if escaped:
            escaped = False
            index += 1
            continue
        if char == '\\' and quote == '"':
            escaped = True
        elif quote:
            if char == quote:
                if quote == "'" and value[index:index + 2] == "''":
                    index += 2
                    continue
                quote = None
        elif char in ('"', "'") and scalar_start:
            quote = char
            scalar_start = False
        elif char == '#' and (index == 0 or value[index - 1].isspace()):
            return value[:index].rstrip()
        elif flow_list and char in ('[', ','):
            scalar_start = True
        elif not char.isspace():
            scalar_start = False
        index += 1
    return value.strip()


def _unquote(value: str) -> str:
    """YAML の引用符つき scalar ('a''b' / "a\\"b") を値に戻す。引用符が無ければそのまま。"""
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1].replace("''", "'")
    if len(value) >= 2 and value[0] == value[-1] == '"':
        try:
            decoded = json.loads(value)
        except ValueError:  # JSON に無い YAML の escape は中身をそのまま使う
            return value[1:-1]
        return decoded if isinstance(decoded, str) else value[1:-1]
    return value


def parse_fm(text: str) -> dict:
    """Parse YAML-ish frontmatter. Supports scalar values and `- ` list items.

    List values (e.g. `rubric_refs:` followed by `  - item`, or `[a, b]`) become a
    list of strings. Scalars and list items are trimmed and unquoted. As in YAML,
    blank and comment lines inside a block list do not end it; the next key does.
    """
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    fm: dict = {}
    current_list_key: str | None = None
    for raw in parts[1].splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue  # blank and comment lines never end a block list in YAML
        # list item under current key
        m_item = re.match(r"^\s*-\s+(.+?)\s*$", line)
        if m_item and current_list_key is not None:
            if fm.get(current_list_key) == "":
                fm[current_list_key] = []
            if isinstance(fm[current_list_key], list):
                fm[current_list_key].append(_unquote(_without_yaml_comment(m_item.group(1))))
            continue
        m = re.match(r"^([a-zA-Z_-]+):\s*(.*)$", line)
        if m:
            key = m.group(1)
            val = _without_yaml_comment(m.group(2))
            if val == "":
                # may be start of list block
                fm[key] = ""
                current_list_key = key
            elif val.startswith("[") and val.endswith("]"):
                inner = val[1:-1].strip()
                fm[key] = [
                    _unquote(item)
                    for item in inner.split(",")
                    if item.strip()
                ]
                current_list_key = None
            else:
                fm[key] = _unquote(val)
                current_list_key = None
    return fm


def _repo_root(p: Path) -> Path:
    """Find repo root by walking up until we find .git or fallback."""
    cur = p.resolve()
    for parent in [cur, *cur.parents]:
        if (parent / ".git").exists():
            return parent
    return cur.parent


def check_refs_exist(fm: dict, skill_path: Path) -> list[str]:
    """Verify rubric_refs / reference_refs / script_refs targets exist.

    - `ref-*` style entries (ref/run/assign/wrap/delegate-*): require one of
      `plugins/harness-creator/skills/<name>/` (共有 skill の正本)、
      `.claude/skills/<name>/`（vault 側）、
      または参照元 skill の兄弟 `<この skill の skills/>/<name>/`（同一 plugin 内）
      が存在すること。兄弟を解決先に含めるのは、plugin が自前の `skills/` に
      L1 rubric を持つ配置が実在するため（例 guide-doc-generator の
      `assign-handout-readability-evaluator` → `ref-handout-design-system`）。
      harness-creator と `.claude/` だけを見ると、同じ plugin 内の実在する
      参照先を「無い」と報告してしまう。
      一方、別の plugin の `skills/` は解決先に含めない。install された plugin が
      持つのは自分の `skills/` だけなので、「どこかの plugin にあれば通る」を
      許すと配布先で参照が切れることを見逃す。
    - other entries: treat as path; first try repo-root relative, then
      skill-directory relative. 解決先が repo の外 (`../` や絶対パス、外を指す
      symlink) なら、実在しても参照として認めない。
    Returns a list of `MISSING_REF:` / `OUTSIDE_REPO_REF:` error strings.
    """
    errs: list[str] = []
    repo = _repo_root(skill_path)
    skill_dir = skill_path.parent
    skill_roots = [
        repo / "plugins" / "harness-creator" / "skills",
        repo / ".claude" / "skills",
        # 参照元と同じ `skills/` 配下の兄弟 skill
        skill_dir.parent,
    ]
    for field in ("rubric_refs", "reference_refs", "script_refs"):
        items = fm.get(field)
        if not items:
            continue
        if isinstance(items, str):
            # comma-separated scalar fallback
            items = [s.strip() for s in items.split(",") if s.strip()]
        for entry in items:
            entry = entry.strip().strip('"').strip("'")
            if not entry:
                continue
            if re.match(r"^(ref|run|assign|wrap|delegate)-[a-z0-9-]+$", entry):
                if not any((root / entry).exists() for root in skill_roots):
                    errs.append(
                        f"MISSING_REF: {field} '{entry}' not found under "
                        f"plugins/harness-creator/skills/, .claude/skills/, "
                        f"or {skill_dir.parent}/ (同一 plugin 内の兄弟 skill)"
                    )
            else:
                cand_root = repo / entry
                cand_local = skill_dir / entry
                found = [c for c in (cand_root, cand_local) if c.exists()]
                if not found:
                    errs.append(
                        f"MISSING_REF: {field} '{entry}' not found "
                        f"(tried {cand_root} and {cand_local})"
                    )
                elif not any(_inside(repo, c) for c in found):
                    errs.append(
                        f"OUTSIDE_REPO_REF: {field} '{entry}' resolves outside the repository "
                        f"({repo})"
                    )
    return errs


def _check_source_tier_demotion(
    tier: str, source: str, last_audited: str, skill_path: Path
) -> str | None:
    """source-tier の降格が必要かを判定する。

    doc/21 再監査ルール（rubric-bump / source-update / quarterly）に対応する
    自動部分のみを扱う。返り値が None の場合は降格不要。

    判定対象:
      - code-verified / article-text / external-spec の高位 tier が、
        正本ファイルの不在・URL未記載・最終監査の古さで降格すべきか
      - code-unavailable のままで rubric が更新されたか

    """
    if not tier:
        return None
    source = source.strip()
    if tier == "external-spec":
        if source and not re.match(r"^https?://", source):
            return "external-spec は http(s) URL を source に持つ必要がある"
    elif tier in {"article-text", "image-derived", "code-verified"}:
        if not source:
            return f"{tier} は確認済み正本パスを source に持つ必要がある"
        if not re.match(r"^https?://", source):
            repo = _repo_root(skill_path)
            if not (repo / source).exists():
                return f"source path not found: {source}"
            if not _inside(repo, repo / source):
                return f"source path outside the repository: {source}"

    if last_audited and ISO_DATE_RE.match(last_audited):
        audited = datetime.date.fromisoformat(last_audited)
        age_days = (datetime.date.today() - audited).days
        if age_days > 180:
            return f"last-audited is {age_days} days old"
    return None


def _agent_tools_errors(fm: dict) -> list[str]:
    """kindAgent の tools 宣言: `tools` (空でない) か `tools-inherit: true` のどちらか一方だけ。

    正本は capability-manifest.schema.json#/definitions/kindAgent の oneOf。
    tools に 'inherit' をツール名として書くと全継承にならないので、それも指摘する。
    """
    ref = "(capability-manifest.schema.json#/definitions/kindAgent)"
    has_tools = "tools" in fm
    has_inherit = "tools-inherit" in fm
    if has_tools and has_inherit:
        return [f"kind=agent: declare only one of 'tools' or 'tools-inherit: true', not both {ref}"]
    if has_inherit:
        value = fm["tools-inherit"]
        if not isinstance(value, str) or value not in ("true", "True", "TRUE"):
            return [f"kind=agent: 'tools-inherit' must be true, got {value!r} {ref}"]
        return []
    tools = fm.get("tools")
    if tools in (None, "", []):
        return [f"kind=agent: missing required field 'tools' or 'tools-inherit: true' (exactly one) {ref}"]
    names = tools if isinstance(tools, list) else tools.split(",")
    if any(str(t).strip().lower() == "inherit" for t in names):
        return [f"kind=agent: 'inherit' is not a tool name; omit tools and declare 'tools-inherit: true' {ref}"]
    return []


def validate_capability(p: Path, fm: dict, text: str) -> tuple[str, list[str]]:
    """SKILL.md 以外の Capability (agent/command/hook/...) を commonCore + kind 固有で検証する。

    CapabilityManifest (capability-manifest.schema.json) に整合。skill 専用ルール
    (trigger count==2 / assign fork / source-tier skill enum) は適用しない。
    """
    errs = _scalar_type_errors(fm)
    kind = _scalar(fm, "kind").split("#", 1)[0].strip()
    name = _scalar(fm, "name")

    # commonCore 必須
    for field in COMMON_CORE_REQUIRED:
        if field not in fm or not fm[field]:
            errs.append(f"commonCore: missing required field '{field}' for kind={kind} "
                        "(capability-manifest.schema.json#/definitions/commonCore)")
    # version は SemVer
    ver = _scalar(fm, "version")
    if ver and not SEMVER_RE.match(str(ver).split("#", 1)[0].strip()):
        errs.append(f"version '{ver}' must be SemVer (X.Y.Z)")
    # name は kebab-case
    if name and not re.match(r"^[a-z][a-z0-9-]*$", name):
        errs.append(f"name '{name}' must be kebab-case (^[a-z][a-z0-9-]*$)")
    # kind 固有の必須フィールド
    for field in KIND_SPECIFIC_REQUIRED.get(kind, ()):  # noqa: B007
        if field not in fm or fm[field] in (None, "", []):
            errs.append(f"kind={kind}: missing required field '{field}' "
                        f"(capability-manifest.schema.json#/definitions/kind{kind.title().replace('-', '')})")
    if kind == "agent":
        errs.extend(_agent_tools_errors(fm))
    # 未展開テンプレート変数
    _unresolved_re = re.compile(r"\{\{[^}]+\}\}")
    for _k, _v in fm.items():
        if isinstance(_v, str) and _unresolved_re.search(_v):
            errs.append(f"unresolved template variable in '{_k}': {_v}")
    return name or p.stem, errs


def validate_file(p: Path) -> tuple[str, list[str]]:
    if not p.exists():
        return str(p), [f"not found: {p}"]

    try:
        text = p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return str(p), [f"cannot read as UTF-8: {p} ({type(e).__name__}: {e})"]
    fm = parse_fm(text)

    # SKILL.md 以外で非 skill kind を宣言する Capability は専用検証へ分岐
    if p.name != "SKILL.md" and _scalar(fm, "kind").split("#", 1)[0].strip() in NON_SKILL_KINDS:
        return validate_capability(p, fm, text)

    errs = _scalar_type_errors(fm)

    # commonCore 必須項目の存在検査。SKILL.md も非SKILL.md と同一の必須集合
    # (COMMON_CORE_REQUIRED = schema 由来 SSOT) を共有する。検査は「存在 + 形式」のみ。
    # 内容の質 (description の良し悪し / version bump 幅 / kind 選定) は rubric+AI が担う
    # 二層分離: 機械=再現性、AI=自由度。
    for r in COMMON_CORE_REQUIRED:
        if r not in fm or not fm[r]:
            errs.append(f"missing required field: {r} "
                        "(commonCore SSOT: capability-manifest.schema.json#/definitions/commonCore.required)")

    # version: SemVer 形式 (X.Y.Z)。存在は上記 commonCore ループが担保。
    # kind は SKILL.md では sub-role prefix のため KIND_VALUES (下記) で別途 enum 評価。
    ver = _scalar(fm, "version")
    ver_norm = str(ver).split("#", 1)[0].strip()
    if ver_norm and not SEMVER_RE.match(ver_norm):
        errs.append(f"version '{ver_norm}' must be SemVer (X.Y.Z)")

    # description quality: 日本語トリガー句 (〜とき/〜場合/〜際/〜時) または
    # 英語の "Use when" / "Read when" のいずれかを含むこと。
    desc = _scalar(fm, "description")
    JP_TRIGGERS = ("とき", "場合", "際", "時に")
    has_en_trigger = ("Use when" in desc) or ("Read when" in desc)
    has_jp_trigger = any(t in desc for t in JP_TRIGGERS)
    if desc and not (has_en_trigger or has_jp_trigger):
        errs.append("description should contain a trigger phrase "
                    "(〜とき/〜場合/〜際/〜時 or 'Use when'/'Read when')")

    # trigger count: hard rule == 2 (設計書03)
    if desc:
        if has_en_trigger:
            # 英語: "when " の単純出現数を採用（接続詞 max ロジックは廃止）
            n = desc.count("when ")
        else:
            # 日本語: 「とき」「場合」「際」「時に」の出現回数を直接カウント
            # （接続詞による加算ロジックは廃止し、純粋な出現数で判定）
            n = sum(desc.count(t) for t in JP_TRIGGERS)
        if n != 2:
            errs.append(f"trigger count = {n} (expected exactly 2; hard rule)")

    # kind enum
    k = _scalar(fm, "kind")
    if k and k not in KIND_VALUES:
        errs.append(f"kind '{k}' not in {sorted(KIND_VALUES)}")
    # effect フィールド: 存在する場合は許容値を検証 (P1-1)
    effect_val = _scalar(fm, "effect")
    if effect_val and effect_val.split("#")[0].strip() not in EFFECT_VALUES:
        errs.append(
            f"effect '{effect_val.split('#')[0].strip()}' not in {sorted(EFFECT_VALUES)}"
        )

    merge_strategy = _scalar(fm, "merge_strategy")
    if merge_strategy and merge_strategy not in MERGE_STRATEGY_VALUES:
        errs.append(
            f"merge_strategy '{merge_strategy}' not in {sorted(MERGE_STRATEGY_VALUES)}"
        )
    conflict_policy = _scalar(fm, "conflict_policy")
    if conflict_policy and conflict_policy not in CONFLICT_POLICY_VALUES:
        errs.append(
            f"conflict_policy '{conflict_policy}' not in {sorted(CONFLICT_POLICY_VALUES)}"
        )

    # --- doc/21 source-traceability 検証 ---
    kind_val = _scalar(fm, "kind")
    source_val = _scalar(fm, "source").strip().strip('"').strip("'")
    source_tier = _scalar(fm, "source-tier").strip().strip('"').strip("'")
    last_audited = _scalar(fm, "last-audited").strip().strip('"').strip("'")

    # ref-* は source 必須、それ以外は WARN
    if kind_val in SOURCE_REQUIRED_FOR_KIND:
        if not source_val:
            errs.append("missing required field for kind=ref: source (doc/21)")
        if not source_tier:
            errs.append("missing required field for kind=ref: source-tier (doc/21)")
    else:
        if not source_val:
            errs.append("warn: source field missing (doc/21 recommends for traceability)")

    if source_tier and source_tier not in SOURCE_TIER_VALUES:
        errs.append(f"source-tier '{source_tier}' not in {sorted(SOURCE_TIER_VALUES)}")

    if last_audited and not ISO_DATE_RE.match(last_audited):
        errs.append(f"last-audited '{last_audited}' must be ISO date YYYY-MM-DD")

    # source-tier 降格判定（doc/21 再監査ルールの自動部分）
    demote_reason = _check_source_tier_demotion(source_tier, source_val, last_audited, p)
    if demote_reason:
        errs.append(f"warn: source-tier '{source_tier}' may need demotion ({demote_reason})")

    # cross_platform 契約検証 (doc/22-cross-platform-runtime)
    # frontmatter に cross_platform: true があれば、本文に <important if="os=...">
    # 分岐が最低 1 つは存在することを要求する。OS 分岐の機械検証は creator-kit
    # 量産時に Windows 経路の欠落を防ぐ。
    cross_platform = _scalar(fm, "cross_platform", "false").lower() == "true"
    if cross_platform:
        # text 全体（frontmatter 含む）に OS 分岐タグが含まれるかを確認
        if not re.search(r"<important\s+if\s*=\s*[\"']?os=", text):
            errs.append(
                "cross_platform=true requires at least one "
                "'<important if=\"os=...\">' branch in body (doc/22)"
            )

    # テンプレート変数の未展開検出（creator-kit 量産品質ゲート / doc/21 backfill依存ループ断ち切り）
    # 実体 SKILL.md に {{...}} が残存していたら ERROR で弾く。
    # templates/*.md は --skills-dir の */SKILL.md glob 対象外のため自動的に除外される。
    _unresolved_re = re.compile(r"\{\{[^}]+\}\}")
    for _k, _v in fm.items():
        if isinstance(_v, str) and _unresolved_re.search(_v):
            errs.append(f"unresolved template variable in '{_k}': {_v}")
        elif isinstance(_v, list):
            for _item in _v:
                if isinstance(_item, str) and _unresolved_re.search(_item):
                    errs.append(f"unresolved template variable in '{_k}' list: {_item}")

    # combo sanity
    dmi = _scalar(fm, "disable-model-invocation", "false").lower() == "true"
    ui = _scalar(fm, "user-invocable", "true").lower()
    ui_false = ui == "false"
    if dmi and not ui_false:
        # ref系: disable-model + user-invocable false ok
        # warn only when also user-invocable true explicit
        if ui == "true":
            errs.append("warn: disable-model-invocation=true + user-invocable=true (unusual)")

    # ref-fields existence (fail-fast: 依存注入の不在 → ref → fail-fast)
    errs.extend(check_refs_exist(fm, p))

    # assign系の必須
    name = _scalar(fm, "name")
    if name.startswith("assign-"):
        if _scalar(fm, "context") != "fork":
            errs.append("assign-* requires context: fork")
        if ui != "false":
            errs.append("assign-* requires user-invocable: false")

    return name, errs


def main() -> int:
    args = sys.argv[1:]
    usage = "usage: validate-frontmatter.py /path/to/SKILL.md | --skills-dir /path/to/skills | --self-test"
    if not args:
        print(usage, file=sys.stderr)
        return 2
    if args[0] in ("-h", "--help"):
        print(usage)
        return 0

    # --self-test: schema(正本) と fallback 定数の drift を検出するゲート。
    # 三重定義の再発防止: schema を改訂したら fallback も同期されているかを CI で機械検証する。
    if "--self-test" in args:
        if args != ["--self-test"]:
            print(f"--self-test takes no other arguments: {args}\n{usage}", file=sys.stderr)
            return 2
        schema = _find_schema()
        if schema is None:
            print(f"self-test FAIL: schema not found ({_SCHEMA_RELPATH})", file=sys.stderr)
            return 1
        loaded = _load_common_core_required()
        if tuple(loaded) != _FALLBACK_COMMON_CORE_REQUIRED:
            print("self-test FAIL: commonCore.required drift "
                  f"(schema={list(loaded)} != fallback={list(_FALLBACK_COMMON_CORE_REQUIRED)}). "
                  "schema 改訂時は _FALLBACK_COMMON_CORE_REQUIRED も同期せよ。", file=sys.stderr)
            return 1
        print(f"self-test ok: commonCore.required = {list(loaded)} (schema == fallback)")
        return 0

    if "--skills-dir" in args:
        if len(args) != 2 or args[0] != "--skills-dir":
            print("usage: validate-frontmatter.py --skills-dir /path/to/skills", file=sys.stderr)
            return 2
        skills_dir = Path(args[1])
        if not skills_dir.is_dir():
            print(f"not a directory: {skills_dir}", file=sys.stderr)
            return 2
        skill_mds = sorted(skills_dir.glob("*/SKILL.md"))
        if not skill_mds:
            print(
                f"config error: no SKILL.md scanned under {skills_dir}/*/SKILL.md "
                f"(cwd={Path.cwd()})",
                file=sys.stderr,
            )
            return 2
        total_errs: list[str] = []
        warn_only = True
        for skill_md in skill_mds:
            name, errs = validate_file(skill_md)
            for e in errs:
                total_errs.append(f"{skill_md.parent.name}: {e}")
                if not e.startswith("warn:"):
                    warn_only = False
        if total_errs:
            for e in total_errs:
                print(e, file=sys.stderr)
            return 0 if warn_only else 1
        print(f"ok: {skills_dir} ({len(skill_mds)} skills)")
        return 0

    if args[0].startswith("-"):
        print(f"unknown option: {args[0]}\n{usage}", file=sys.stderr)
        return 2
    if len(args) != 1:
        # 2つ目以降のパスを黙って捨てると、検査したつもりの SKILL.md が素通りする
        print(f"only one SKILL.md path is accepted, got {len(args)}: {args}\n{usage}",
              file=sys.stderr)
        return 2
    p = Path(args[0])
    name, errs = validate_file(p)
    if errs:
        for e in errs:
            print(e, file=sys.stderr)
        # warn-only do not fail; but any non-warn is fail
        hard = [e for e in errs if not e.startswith("warn:")]
        return 1 if hard else 0
    print(f"ok: {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
