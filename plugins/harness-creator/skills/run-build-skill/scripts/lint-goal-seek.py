#!/usr/bin/env python3
# /// script
# name: lint-goal-seek
# purpose: 実行系 Skill が固定手順ではなくゴールシーク (Goal+Checklist+Loop) で構成されているか検査する。
# inputs:
#   - argv: SKILL.md path(s) or --skills-dir <dir>
# outputs:
#   - stdout: OK status
#   - stderr: violation findings
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""harness-creator が生成する実行系 Skill のゴールシーク準拠を機械検証する lint。

ルール (run-build-skill SKILL.md Key Rule 18 / references/goal-seek-paradigm.md):
  - 実行系 kind (run / wrap / delegate / assign / orchestrator / agent / hook) は
    `## ゴールシーク実行` 見出しを持つこと。
  - 固定手順の連番羅列 (`## 手順` セクション直下の番号付き / `### Step N:` の 2 連以上が
    局面カタログ「見出しセクション」外で出現) は violation。本文引用のラベルは効力なし。
  - ref-* (read-only) は対象外 (skip)。

Exit 0 = ok, 1 = violation, 2 = usage error。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

GOAL_SEEK_HEADING = "## ゴールシーク実行"
# 行頭の実見出しのみを一致 (本文中に `## ゴールシーク実行` を引用しただけでは不可)。
GOAL_SEEK_HEADING_RE = re.compile(r"^##\s*ゴールシーク実行\s*$", re.MULTILINE)
# 実行系とみなす prefix/kind。ref は除外。
EXECUTION_PREFIXES = ("run", "wrap", "delegate", "assign")
# loop 実行系 (達成までループを回す)。assign は一発採点でループしないため除外。
LOOP_PREFIXES = ("run", "wrap", "delegate")
# 局面カタログ配下の `### Step` は許容 (順序非固定の例示)。
# ラベルは「見出し (##/###) として宣言されたカタログセクション」内でのみ効力を持つ。
# 本文引用・コメント中のラベル出現では Step 連番を免除しない (catalog label escape 封鎖:
# LS-01b/PF-META。従来の body 全域 substring 判定は引用 1 箇所で全 Step を素通しした)。
CATALOG_MARKERS = ("局面カタログ", "順序は都度判断", "順序非固定")
# WIRING_SECTION_RE と同型の見出しスコープ: カタログ見出し行から次の ## 見出し (または EOF) まで。
CATALOG_SECTION_RE = re.compile(
    r"^#{2,3}(?!#)[^\n]*(?:" + "|".join(re.escape(m) for m in CATALOG_MARKERS) + r")[^\n]*\n"
    r".*?(?=^##\s|\Z)",
    re.MULTILINE | re.DOTALL,
)
STEP_RE = re.compile(r"^### Step\s*\d+\s*[:：]", re.MULTILINE)
FIXED_PROCEDURE_HEADING_RE = re.compile(r"^## 手順\s*$", re.MULTILINE)
# 完了チェックリスト領域と二値項目。
CHECKLIST_HEADING_RE = re.compile(r"^###\s*完了チェックリスト", re.MULTILINE)
NEXT_HEADING_RE = re.compile(r"^#{2,3}\s", re.MULTILINE)
CHECKLIST_ITEM_RE = re.compile(r"^- \[[ xX]\]\s*(.+)$", re.MULTILINE)
# YES/NO 判定不能な曖昧語 (goal-seek-paradigm.md「チェックリストの良し悪し」)。
VAGUE_TERMS = ("丁寧", "品質を高める", "適切に", "きちんと", "しっかり", "なるべく", "可能な限り")
# with-goal-seek combinator が注入する実行配線サブセクション。
# 行頭の実見出しのみ一致 (本文に見出し名を引用しただけでは満たさない)。
WIRING_HEADING = "### ゴールシーク配線"
WIRING_HEADING_RE = re.compile(r"^###\s*ゴールシーク配線", re.MULTILINE)
# 中間成果物アンカー (ドリフト圧縮機構) の配線存在検査。
# AND マッチで「配線実体」を保証する。1 トークン欠落でも warning (F-LS-002 / F-MD-010 / F-SS-004)。
# (1) jsonl パス, (2) 不変アンカー original_goal, (3) 次周回必須入力 merged_directive_for_next の 3 トークン全部が
# `### ゴールシーク配線` セクション内に出現することを要件化する。
INTERMEDIATE_REQUIRED_TOKENS = ("intermediate.jsonl", "original_goal", "merged_directive_for_next")
# 量産スキルが中間成果物の機械検証 bash を埋め込んでいるかの token 検査 (run-goal-seek/SKILL.md と同型)。
VERIFICATION_REQUIRED_TOKENS = ("required_keys", "original_goal_hash", "hashlib.sha256")
# `### ゴールシーク配線` + 直後に並置される `### ゴールシーク検証` 両方を scope 内に取り込む。
# 停止条件を ## level に緩めることで、中間成果物トークンと検証 bash トークンを同一 wiring_text で AND 検査可能になる
# (F-MD-003 / F-SS-006 / F-LS-002 解消: body 全体 scope の偽陰性/偽陽性両方を回避)。
WIRING_SECTION_RE = re.compile(
    r"^###\s*ゴールシーク配線.*?(?=^##\s|\Z)", re.MULTILINE | re.DOTALL
)


def parse_frontmatter(text: str) -> dict[str, str]:
    """軽量 frontmatter パーサ (key: value のフラットなもののみ)。yaml import しない。"""
    fm: dict[str, str] = {}
    if not text.startswith("---"):
        return fm
    end = text.find("\n---", 3)
    if end == -1:
        return fm
    for line in text[3:end].splitlines():
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if m:
            fm[m.group(1)] = m.group(2).strip()
    return fm


def is_execution_skill(fm: dict[str, str]) -> bool:
    prefix = (fm.get("prefix") or fm.get("kind") or "").strip().strip('"')
    return prefix in EXECUTION_PREFIXES


def body_after_frontmatter(text: str) -> str:
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[end + 4 :]
    return text


def skill_prefix(fm: dict[str, str]) -> str:
    return (fm.get("prefix") or fm.get("kind") or "").strip().strip('"')


def checklist_region(body: str) -> str | None:
    """`### 完了チェックリスト` 見出しから次見出しまでの本文を返す (無ければ None)。"""
    m = CHECKLIST_HEADING_RE.search(body)
    if not m:
        return None
    start = m.end()
    nxt = NEXT_HEADING_RE.search(body[start:])
    end = start + nxt.start() if nxt else len(body)
    return body[start:end]


def lint_file(path: Path) -> tuple[list[str], list[str]]:
    """(findings=exit1 違反, warnings=exit0 助言) を返す。"""
    findings: list[str] = []
    warnings: list[str] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        return [f"{path}: read error: {e}"], warnings

    fm = parse_frontmatter(text)
    prefix = skill_prefix(fm)
    if prefix not in EXECUTION_PREFIXES:
        return findings, warnings  # ref など実行系以外は対象外

    body = body_after_frontmatter(text)

    # 1. ゴールシーク見出しの存在 (行頭の実見出しのみ; 本文引用では満たさない)
    if not GOAL_SEEK_HEADING_RE.search(body):
        findings.append(
            f"{path}: 実行系 Skill に '{GOAL_SEEK_HEADING}' 見出しがない "
            "(固定手順ではなく Goal+Checklist+Loop で構成すること)"
        )

    # 2. 固定 `## 手順` セクションの残存
    if FIXED_PROCEDURE_HEADING_RE.search(body):
        findings.append(
            f"{path}: 実行系 Skill に固定 '## 手順' セクションが残存 "
            "(ゴールシークへ移行すること)"
        )

    # 3. 局面カタログ見出しセクション外での `### Step N:` 連番羅列 (2 連以上)。
    # 許容はカタログ見出しセクション配下のみ (本文引用のラベルでは免除しない)。
    catalog_spans = [m.span() for m in CATALOG_SECTION_RE.finditer(body)]
    outside_steps = [
        m
        for m in STEP_RE.finditer(body)
        if not any(s <= m.start() < e for s, e in catalog_spans)
    ]
    if len(outside_steps) >= 2:
        findings.append(
            f"{path}: 局面カタログ見出しセクション外で固定手順の連番 (### Step N:) が "
            f"{len(outside_steps)} 件検出された。順序固定の手順は書かず、"
            "'## 局面カタログ (順序は都度判断)' 見出しセクション配下として記述すること"
        )

    # 4. loop 実行系 (run/wrap/delegate): チェックリスト二値性 + 曖昧語 + 配線
    if prefix in LOOP_PREFIXES:
        region = checklist_region(body)
        # template placeholder ({{...}}) 未展開の中間物は二値検査をスキップ。
        if region is not None and "{{" not in region:
            items = CHECKLIST_ITEM_RE.findall(region)
            if not items:
                findings.append(
                    f"{path}: loop実行系に二値チェックリスト項目 (- [ ] / - [x]) が無い "
                    "(ゴール達成の受入基準を YES/NO 判定可能な項目で列挙すること)"
                )
            for item in items:
                hit = [t for t in VAGUE_TERMS if t in item]
                if hit:
                    findings.append(
                        f"{path}: チェックリスト項目に曖昧語 {hit} があり YES/NO 判定不能: "
                        f"'{item.strip()}' (観測可能な条件へ書き換えること)"
                    )
        # 実行配線サブセクション + 中間成果物アンカーの 2 検査を独立 if で分離する (F-LS-007 / F-SS-014)。
        # 配線サブセクション不在は warning (既存スキル grace)。中間成果物トークン欠落は scope 限定 AND 検査。
        wiring_match = WIRING_SECTION_RE.search(body)
        if not wiring_match:
            warnings.append(
                f"{path}: '{WIRING_HEADING}' が無い "
                "(with-goal-seek combinator で goal-spec/progress JSON/fork 委譲を配線推奨)"
            )
        # 中間成果物トークンは「配線サブセクション内に AND で全 3 トークン揃う」ことを要件化する。
        # 配線サブが無くても (上記 warning とは別系統で) 中間成果物欠落を独立に警告する。
        wiring_text = wiring_match.group(0) if wiring_match else body
        missing_tokens = [t for t in INTERMEDIATE_REQUIRED_TOKENS if t not in wiring_text]
        if missing_tokens:
            warnings.append(
                f"{path}: ゴールシーク配線に中間成果物アンカー必須トークン {missing_tokens} "
                "が不在 (3 トークン AND 必須: intermediate.jsonl + original_goal + "
                "merged_directive_for_next。with-goal-seek combinator 再適用で注入)"
            )
        # 量産スキルにも機械検証 bash が注入されているか検査 (run-goal-seek/SKILL.md と同型 SSOT)。
        # WIRING_SECTION_RE が ## level まで拡張されたため `### ゴールシーク検証` も同 scope に含まれる。
        # wiring_text 限定 AND 検査により body 全体 scope の偽陰性/偽陽性を排除する。
        missing_verify = [t for t in VERIFICATION_REQUIRED_TOKENS if t not in wiring_text]
        if missing_verify:
            warnings.append(
                f"{path}: ゴールシーク配線に機械検証 bash 必須トークン {missing_verify} "
                "が不在 (3 トークン AND 必須: required_keys + original_goal_hash + hashlib.sha256。"
                "with-goal-seek combinator 再適用で注入。run-goal-seek/SKILL.md と同型機械検査)"
            )

        # engine:task-graph を concrete 宣言する生成 SKILL.md のみ、consumption verifier /
        # dependency graph knowledge consult トークンの存在を検査する (route C04・非 task-graph は非対象)。
        # engine 宣言は frontmatter (goal_seek.engine) にあるため full text で検出するが、
        # トークン検査は base 検査 (INTERMEDIATE/VERIFICATION) と同じく wiring_text へ scope 限定する
        # (本文引用/散文中のトークンで満たされる全文 substring の偽陰性経路を塞ぐ。LS-01b と同型)。
        # template placeholder ({{...}}) の engine 宣言は具体値でないため対象外。
        if _CONCRETE_TASK_GRAPH_ENGINE_RE.search(text):
            missing_tg = [
                t for t in (_TASK_GRAPH_WIRING_TOKENS + _TASK_GRAPH_KNOWLEDGE_TOKENS)
                if t not in wiring_text
            ]
            if missing_tg:
                findings.append(
                    f"{path}: engine:task-graph 宣言スキルに consumption verifier / dependency graph "
                    f"knowledge consult トークン {missing_tg} が不在 "
                    "(with-goal-seek 再適用で task-graph 変種配線を注入すること)"
                )

    return findings, warnings


# --- SSOT drift 自己検査 -----------------------------------------------------
# goal_seek 既定値は物理的に複数ファイルへ分散する (Python定数 / JSON schema / patchテキスト)。
# with-knowledge の lint-knowledge-loop.py check_schema_drift() と同型に、分散コピーの一致を
# 機械保証する。escaped quote(\") と raw quote(") の両方を許容し同一検査器で抽出する。
_RENDER = Path(__file__).resolve().parent / "render-combinators.py"
_PATCH = Path(__file__).resolve().parents[1] / "templates" / "combinators" / "with-goal-seek.patch"
_BUILD_FLAGS = Path(__file__).resolve().parents[1] / "schemas" / "build-flags.schema.json"
_LOOP_SCHEMA = Path(__file__).resolve().parents[1] / "schemas" / "goal-seek-loop.schema.json"
_ENGINE_RE = re.compile(r"goal_seek\.engine \| default\(\\?\"([\w-]+)\\?\"\)")
_FORK_RE = re.compile(r"goal_seek\.fork \| default\(\\?\"([\w-]+)\\?\"\)")
_MAXLOOPS_RE = re.compile(r"goal_seek\.max_loops \| default\((\d+)\)")
# 中間成果物ログファイル名の SSOT 検証 (render定数 / patch / schema description で同名であること)。
_INTERMEDIATE_PATH_RE = re.compile(r"eval-log/\{\{skill_name\}\}-intermediate\.jsonl")

# --- engine:task-graph 変種 (route C04 追加検査) の SSOT トークン ---------------------
# 既存 check_default_drift() のロジックには触れず、check_task_graph_variant() として追加する。
_TASK_GRAPH_ENGINE_VALUE = "task-graph"
# (c-1) consumption verifier トークン: 依存順消費 (ready 集合の最小 id を拘束選択) と
#        self-reflect 追記 item の完了 gate を intermediate.jsonl トレースで機械検査する証跡。
_TASK_GRAPH_WIRING_TOKENS = (
    "ready-set-from-checklist.py",  # ENG-C01 同梱・ready 算出
    "self-reflect-append.py",        # ENG-C02 同梱・自己反映
    "ready_set",                     # intermediate.jsonl additive (算出時点の ready 集合)
    "selected_item",                 # intermediate.jsonl additive (実際に選択した id)
    "依存順消費",                     # consumption verifier: selected_item==ready 最小 id 検査
    "self-reflect 完了 gate",         # consumption verifier: 追記 item が done まで gate
)
# (c-2) dependency graph knowledge consult トークン: ENG-C06/ENG-C07 同梱と各 surface consult 手順。
_TASK_GRAPH_KNOWLEDGE_TOKENS = (
    "extract-capability-dependency-graph.py",  # ENG-C06 同梱
    "record-capability-graph-knowledge.py",    # ENG-C07 同梱
    "dependency graph knowledge",              # 各 surface 実行前 consult 手順
)
# 生成 SKILL.md が concrete に engine: task-graph を宣言しているかの判定。
# frontmatter の YAML 宣言行 (行頭・任意インデント・末尾 YAML コメント許容) のみに一致させ、
# 機能を説明する散文/コメント中の 'engine:task-graph' 言及 (行頭でない or 末尾に散文が続く) は
# 除外する (自己言及ドキュメントへの誤発火を防ぐ)。template placeholder ({{...}}) も非一致。
_CONCRETE_TASK_GRAPH_ENGINE_RE = re.compile(
    r"^\s*engine:\s*task-graph\s*(?:#.*)?$", re.MULTILINE
)


def _extract_defaults(text: str) -> dict[str, str | None]:
    """Python 定数 / patch テキストから engine/fork/max_loops の既定値を抽出する。"""
    e = _ENGINE_RE.search(text)
    f = _FORK_RE.search(text)
    m = _MAXLOOPS_RE.search(text)
    return {
        "engine": e.group(1) if e else None,
        "fork": f.group(1) if f else None,
        "max_loops": m.group(1) if m else None,
    }


def check_default_drift() -> list[str]:
    """render定数 / patch / build-flags schema / goal-seek-loop schema の既定値一致を検証する。"""
    findings: list[str] = []
    try:
        render = _extract_defaults(_RENDER.read_text(encoding="utf-8"))
        patch = _extract_defaults(_PATCH.read_text(encoding="utf-8"))
        build_flags = json.loads(_BUILD_FLAGS.read_text(encoding="utf-8"))
        loop_schema = json.loads(_LOOP_SCHEMA.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return [f"self-test: source read error: {e}"]

    bf_gs = (
        build_flags.get("properties", {}).get("with_goal_seek", {}).get("properties", {})
    )
    ls_props = loop_schema.get("properties", {})
    bf_engine = bf_gs.get("engine", {}).get("default")
    bf_maxloops = bf_gs.get("max_loops", {}).get("default")
    ls_fork = ls_props.get("fork_context", {}).get("default")
    ls_maxloops = ls_props.get("max_loops", {}).get("default")

    # render定数 と patch は逐語一致すべき (apply_patch_file fallback 経路の静かな乖離防止)
    for key in ("engine", "fork", "max_loops"):
        if render[key] is None:
            findings.append(f"self-test: render-combinators.py から goal_seek.{key} 既定を抽出できない")
        if patch[key] is None:
            findings.append(f"self-test: with-goal-seek.patch から goal_seek.{key} 既定を抽出できない")
        if render[key] != patch[key]:
            findings.append(
                f"self-test: goal_seek.{key} 既定が render定数({render[key]}) と patch({patch[key]}) で不一致"
            )

    # engine: render ↔ build-flags schema
    if render["engine"] != bf_engine:
        findings.append(
            f"self-test: engine 既定 drift — render({render['engine']}) vs build-flags.schema({bf_engine})"
        )
    # fork: render ↔ goal-seek-loop schema (fork_context)
    if render["fork"] != ls_fork:
        findings.append(
            f"self-test: fork 既定 drift — render({render['fork']}) vs goal-seek-loop.schema.fork_context({ls_fork})"
        )
    # max_loops: render ↔ 両 schema (int 比較)
    rml = int(render["max_loops"]) if render["max_loops"] else None
    if rml != bf_maxloops:
        findings.append(
            f"self-test: max_loops 既定 drift — render({rml}) vs build-flags.schema({bf_maxloops})"
        )
    if rml != ls_maxloops:
        findings.append(
            f"self-test: max_loops 既定 drift — render({rml}) vs goal-seek-loop.schema({ls_maxloops})"
        )

    # 中間成果物アンカー: render定数 / patch / schema の三者一致を検査する。
    # ファイル名 (eval-log/<skill>-intermediate.jsonl) は patch と render に必ず登場し、
    # schema 側は intermediate_artifacts プロパティと description 内 jsonl 言及を持つ。
    render_text = _RENDER.read_text(encoding="utf-8")
    patch_text = _PATCH.read_text(encoding="utf-8")
    render_has_intermediate = bool(_INTERMEDIATE_PATH_RE.search(render_text))
    patch_has_intermediate = bool(_INTERMEDIATE_PATH_RE.search(patch_text))
    schema_has_intermediate = "intermediate_artifacts" in loop_schema.get("properties", {})
    if not render_has_intermediate:
        findings.append(
            "self-test: render-combinators.py から intermediate.jsonl 配線が欠落"
        )
    if not patch_has_intermediate:
        findings.append(
            "self-test: with-goal-seek.patch から intermediate.jsonl 配線が欠落"
        )
    if not schema_has_intermediate:
        findings.append(
            "self-test: goal-seek-loop.schema.json に intermediate_artifacts プロパティが欠落"
        )
    # 必須キーの一致 (schema が要求する全キーが render/patch 説明文に出現すること)。
    if schema_has_intermediate:
        items_schema = loop_schema["properties"]["intermediate_artifacts"]["items"]
        required_keys = set(items_schema.get("required", []))
        for key in required_keys:
            if key not in render_text:
                findings.append(
                    f"self-test: intermediate_artifacts.{key} が render-combinators.py 配線テキストに不在"
                )
            if key not in patch_text:
                findings.append(
                    f"self-test: intermediate_artifacts.{key} が with-goal-seek.patch 配線テキストに不在"
                )
        # drift_signal の enum 値集合が schema と render/patch (描画される文書) で一致するか検査
        # (F-LS-003 / F-MD-002)。schema が真の SSOT。render/patch には description で enum 値が列挙されている。
        drift_enum = set(
            items_schema.get("properties", {}).get("drift_signal", {}).get("enum", [])
        )
        for value in drift_enum:
            # 各 enum 値が render/patch のどちらかに最低 1 回出現していること。
            # patch は短いので render のみで OK としても良いが SSOT 透明性のため両方検査。
            if value not in render_text and value not in patch_text:
                findings.append(
                    f"self-test: drift_signal enum '{value}' が render/patch どちらにも出現しない "
                    "(schema と配線テキストの enum drift)"
                )

    # 機械検証 bash の SSOT 三者一致 (render定数 ↔ patch ↔ run-goal-seek/SKILL.md)。
    # 量産スキルへの自動注入 (render経由) と patch経由配信 と engine 本体 bash の三者全部に
    # 同型機構が存在することを保証する (F-LS-001 / F-SS-002 / F-MD-001 解消: patch 経路 drift 防止)。
    run_goal_seek = (
        Path(__file__).resolve().parents[2] / "run-goal-seek" / "SKILL.md"
    )
    if not run_goal_seek.exists():
        findings.append(
            "self-test: run-goal-seek/SKILL.md が不在で engine 本体側 bash の SSOT 照合不能 "
            "(F-SS-009: silent skip ではなく error 化。harness-creator deploy に run-goal-seek 必須)"
        )
    else:
        rgs_text = run_goal_seek.read_text(encoding="utf-8")
        for token in VERIFICATION_REQUIRED_TOKENS:
            if token not in render_text:
                findings.append(
                    f"self-test: 機械検証 bash トークン '{token}' が render-combinators.py に不在 "
                    "(量産スキルへの自動注入が機能しない)"
                )
            if token not in patch_text:
                findings.append(
                    f"self-test: 機械検証 bash トークン '{token}' が with-goal-seek.patch に不在 "
                    "(patch 経路 apply 時に検証 bash が欠落し集約化ドリフト検出が無効化される)"
                )
            if token not in rgs_text:
                findings.append(
                    f"self-test: 機械検証 bash トークン '{token}' が run-goal-seek/SKILL.md に不在 "
                    "(engine 本体側の bash が同型でない)"
                )

    # engine:task-graph 変種の追加検査を append する (既存検査ロジックは不変)。
    findings.extend(check_task_graph_variant())
    return findings


def check_task_graph_variant() -> list[str]:
    """engine:task-graph 変種 (route C03) の SSOT 整合 + consumption verifier トークン存在を検査する (route C04)。

    (a) build-flags.schema.json の engine enum に 'task-graph' が存在し、render-combinators.py の
        配線にも 'task-graph' の言及がある (enum と配線コメントの整合)。
    (b) goal-seek-loop.schema.json の checklist item に depends_on additive フィールド (array/default[])
        が存在する (依存充足順に必須・後方互換)。
    (c) render-combinators.py の task-graph 配線サブセクションに consumption verifier トークン
        (依存順消費 + self-reflect 完了 gate) と dependency graph knowledge consult トークンが揃う。
    既存 check_default_drift() の検査には一切干渉せず、追加検査としてのみ機能する (回帰防止)。
    """
    findings: list[str] = []
    try:
        render_text = _RENDER.read_text(encoding="utf-8")
        build_flags = json.loads(_BUILD_FLAGS.read_text(encoding="utf-8"))
        loop_schema = json.loads(_LOOP_SCHEMA.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return [f"self-test(task-graph): source read error: {e}"]

    # (a) engine enum に task-graph が存在し render 配線にも言及がある。
    engine_enum = (
        build_flags.get("properties", {}).get("with_goal_seek", {})
        .get("properties", {}).get("engine", {}).get("enum", [])
    )
    if _TASK_GRAPH_ENGINE_VALUE not in engine_enum:
        findings.append(
            f"self-test(task-graph): build-flags.schema の with_goal_seek.engine enum に "
            f"'{_TASK_GRAPH_ENGINE_VALUE}' が不在 ({engine_enum})"
        )
    if _TASK_GRAPH_ENGINE_VALUE not in render_text:
        findings.append(
            "self-test(task-graph): render-combinators.py 配線に 'task-graph' engine の言及が不在 "
            "(build-flags enum と配線コメントの整合が取れていない)"
        )

    # (b) checklist item に depends_on additive フィールド。
    item_props = (
        loop_schema.get("properties", {}).get("checklist", {})
        .get("items", {}).get("properties", {})
    )
    dep = item_props.get("depends_on")
    if dep is None:
        findings.append(
            "self-test(task-graph): goal-seek-loop.schema の checklist item に depends_on additive "
            "フィールドが不在 (engine:task-graph の依存充足順算出に必須)"
        )
    elif dep.get("type") != "array" or dep.get("default") != []:
        findings.append(
            "self-test(task-graph): depends_on は additive/後方互換のため type=array かつ default=[] "
            f"である必要がある (現状 type={dep.get('type')} default={dep.get('default')})"
        )

    # (c) consumption verifier + dependency graph knowledge consult トークン。
    for tok in _TASK_GRAPH_WIRING_TOKENS:
        if tok not in render_text:
            findings.append(
                f"self-test(task-graph): consumption verifier トークン '{tok}' が render-combinators.py "
                "の task-graph 配線に不在 (依存順消費/self-reflect 完了 gate の機械検査が生成 SKILL.md へ注入されない)"
            )
    for tok in _TASK_GRAPH_KNOWLEDGE_TOKENS:
        if tok not in render_text:
            findings.append(
                f"self-test(task-graph): dependency graph knowledge consult トークン '{tok}' が "
                "render-combinators.py の task-graph 配線に不在 (C06/C07 同梱・consult 手順が欠落)"
            )
    return findings


def collect_targets(argv: list[str]) -> list[Path]:
    if not argv:
        return []
    if argv[0] == "--skills-dir":
        if len(argv) < 2:
            return []
        d = Path(argv[1])
        return sorted(d.glob("**/SKILL.md")) if d.is_dir() else []
    return [Path(p) for p in argv]


def main(argv: list[str]) -> int:
    if argv and argv[0] == "--self-test":
        drift = check_default_drift()
        if drift:
            for d in drift:
                sys.stderr.write(d + "\n")
            return 1
        sys.stdout.write("OK: goal-seek 既定値 SSOT 整合 (engine/fork/max_loops drift なし)\n")
        return 0

    targets = collect_targets(argv)
    if not targets:
        sys.stderr.write(
            "usage: lint-goal-seek.py <SKILL.md> | --skills-dir <dir> | --self-test\n"
        )
        return 2

    all_findings: list[str] = []
    all_warnings: list[str] = []
    for path in targets:
        findings, warnings = lint_file(path)
        all_findings.extend(findings)
        all_warnings.extend(warnings)

    for w in all_warnings:
        sys.stderr.write(f"WARN: {w}\n")

    if all_findings:
        for f in all_findings:
            sys.stderr.write(f + "\n")
        return 1

    suffix = f" ({len(all_warnings)} warning(s))" if all_warnings else ""
    sys.stdout.write(
        f"OK: {len(targets)} skill file(s) passed goal-seek lint{suffix}\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
