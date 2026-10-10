#!/usr/bin/env python3
"""vendored SSOT (plugin へ実体コピーした共有ローダ) が正本と byte 一致するか検証する。

背景: 一部 plugin は単独インストール (marketplace から当該 plugin のみ install) で
コアフローが自己完結動作することを要件とする。このため、従来 plugin 境界を越えて
symlink / 上方 import していた共有ローダを各 plugin の scripts/ へ実体コピー (vendoring) する。
symlink や plugin 外への import-time 依存は単独 install で dangling / ImportError になる。

二重実体は drift (内容乖離) リスクを生む。本 lint は「vendored 版 == 正本」を byte 単位で
機械検証し、乖離していれば exit 1 (fail-closed)。これにより「移植性のための実体コピー」と
「SSOT 単一正本」を両立させる。

正本 (canonical) は repo-root scripts/ 側。vendored は plugin/scripts/ 側。
runtime / build-time 中核モジュールのみ byte 一致を強制する (doc は plugin 別に localize
するため対象外: コードは一致強制 / doc は localized の役割分担)。

本 lint は従来の lint-intake-vendored-ssot.py を一般化した後継。新規 vendored ペアは
VENDORED_PAIRS に1行足すだけで byte 一致が強制される。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# (canonical 正本, vendored 複製) のペア。byte 一致を強制する runtime/build-time SSOT のみ。
VENDORED_PAIRS = [
    # ガバナンスのローカル/配布実行面は同じ承認・cooldown境界を検査する。
    (ROOT / "scripts/guard-change-category.py", ROOT / "plugins/skill-governance-automation/scripts/guard-change-category.py"),
    # 共通フィードバックのアンカー validator。新規配備は skill ディレクトリごとコピーし、
    # 既存配備も同じ生成元と byte 一致を強制する。兄弟 plugin への実行時依存は増やさない。
    *[
        (
            ROOT / "plugins/harness-creator/skills/run-build-skill/templates/goal-seek-runtime/scripts/validate-inline-goal-seek-anchor.py",
            skill.parent / "scripts/validate-inline-goal-seek-anchor.py",
        )
        for skill in sorted(ROOT.glob("plugins/*/skills/run-skill-feedback/SKILL.md"))
        if not skill.is_symlink()
    ],
    # Tenant selection and credential-reference derivation are shared by every
    # tenant-aware standalone plugin. The repo-root copy is the only edit point.
    *[
        (ROOT / "scripts" / "tenant_runtime.py", target)
        for target in (
            ROOT / "plugins" / "harness-creator" / "scripts" / "tenant_runtime.py",
            ROOT / "plugins" / "skill-intake" / "scripts" / "tenant_runtime.py",
            ROOT / "plugins" / "contract-generator" / "lib" / "tenant_runtime.py",
            ROOT / "plugins" / "skill-governance-automation" / "scripts" / "tenant_runtime.py",
        )
    ],
    # skill-intake 単独 install 用に同梱した Notion config ローダ。
    (
        ROOT / "plugins" / "harness-creator" / "scripts" / "notion_config.py",
        ROOT / "plugins" / "skill-intake" / "scripts" / "notion_config.py",
    ),
    # harness-creator 単独 install 用に同梱した feedback_contract 境界 SSOT。
    # runtime hook (check-review-trigger.py) / build-time validator が import-time に
    # 解決するため、plugin 外 repo-root への依存を断ち plugin 内へ vendoring する。
    (
        ROOT / "scripts" / "feedback_contract_ssot.py",
        ROOT / "plugins" / "harness-creator" / "scripts" / "feedback_contract_ssot.py",
    ),
    # harness-creator の内容 lint (lint-agent-prompt-content.py) が本文 7 層検証に用いる
    # prompt-creator の verify-completeness.py コアロジック。C02 は agents/prompts の
    # l5-contract v2.0.0 準拠検証を自己完結させるため canonical を byte 一致で vendoring し、
    # lint-agent-prompt-content.py --check-vendor-parity と本 registry の両輪で drift を封じる。
    (
        ROOT / "plugins" / "prompt-creator" / "skills" / "run-prompt-creator-7layer"
        / "scripts" / "verify-completeness.py",
        ROOT / "plugins" / "harness-creator" / "vendor" / "prompt-creator" / "verify-completeness.py",
    ),
    # slide-report-generator の IN2 ゲート (情報優先度宣言) は system-spec-harness の
    # validator/schema を使うが、SRG は system-spec-harness に依存しない配布 plugin なので
    # install 先に兄弟がある保証が無い。stdlib-only・read-only の validator と schema を同梱する。
    *[
        (
            ROOT / "plugins" / "system-spec-harness" / rel,
            ROOT / "plugins" / "slide-report-generator" / rel,
        )
        for rel in (
            "scripts/validate-information-priority.py",
            "schemas/information-priority-map.schema.json",
        )
    ],
    # dev-graph の node/decompose/requirements が reference_refs で読む exact-13 package 契約。
    # 正本は system-dev-planner (ミクロ層) だが、install 先では `../../../system-dev-planner/` が
    # 兄弟に届かない。localize せず同じ契約を読ませたいので、doc でも byte 一致を強制する。
    (
        ROOT / "plugins" / "system-dev-planner" / "references" / "feature-execution-package-contract.md",
        ROOT / "plugins" / "dev-graph" / "references" / "feature-execution-package-contract.md",
    ),
    # assign-skill-design-evaluator の render-findings-score.py が subprocess で起動する rubric 合成器。
    # harness-creator は skill-governance-automation に依存しない配布 plugin なので、stdlib-only の
    # 正本を byte 一致で同梱する。
    (
        ROOT / "plugins" / "skill-governance-automation" / "scripts" / "compose-rubrics.py",
        ROOT / "plugins" / "harness-creator" / "scripts" / "compose-rubrics.py",
    ),
    # 兄弟 plugin の root を install 配置に依存せず解決する CLI。external-mutation の
    # guard block (build-artifact-delivery.py) が自 plugin の scripts/ から呼ぶ。全 plugin が
    # 外部変更 skill (run-skill-feedback) を持つので、manifest を持つ全 plugin へ vendoring する。
    # 一覧を手書きしないので、plugin を足して vendor を忘れると存在検査で落ちる。
    *[
        (
            ROOT / "scripts" / "extract-plugin-root.py",
            manifest.parents[1] / "scripts" / "extract-plugin-root.py",
        )
        for manifest in sorted(ROOT.glob("plugins/*/.claude-plugin/plugin.json"))
    ],
]


def check_pairs(pairs):
    """各ペアの存在・非 symlink・byte 一致を検査し failures リストを返す。"""
    failures = []
    for canonical, vendored in pairs:
        rel_c = canonical.relative_to(ROOT)
        rel_v = vendored.relative_to(ROOT)
        if not canonical.exists():
            failures.append(f"canonical 不在: {rel_c}")
            continue
        if not vendored.exists():
            failures.append(
                f"vendored 不在: {rel_v} (単独 install 用の同梱が欠落)。"
                f" 正本 {rel_c} から実体コピーで再同期。"
            )
            continue
        # symlink に戻っていないか (単独 install で dangling する回帰を検出)。
        if vendored.is_symlink():
            failures.append(
                f"vendored が symlink に回帰: {rel_v} -> {vendored.readlink()}。"
                f" 単独 install で dangling になる。実体コピーへ戻すこと。"
            )
            continue
        if canonical.read_bytes() != vendored.read_bytes():
            failures.append(
                f"SSOT drift: {rel_v} が正本 {rel_c} と不一致。"
                f" 正本から再同期 (cp {rel_c} {rel_v})。"
            )
    return failures


def main():
    failures = check_pairs(VENDORED_PAIRS)
    if failures:
        sys.stderr.write("[lint-vendored-ssot] FAIL\n")
        for f in failures:
            sys.stderr.write(f"  - {f}\n")
        return 1
    print(
        f"[lint-vendored-ssot] OK: vendored SSOT {len(VENDORED_PAIRS)} 件が正本と byte 一致"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
