#!/usr/bin/env python3
"""vendored SSOT (plugin へ実体コピーした共有ローダ) が正本と byte 一致するか検証する。

背景: 一部 plugin は単独インストール (marketplace から当該 plugin のみ install) で
コアフローが自己完結動作することを要件とする。このため、従来 plugin 境界を越えて
symlink / 上方 import していた共有ローダを各 plugin の scripts/ へ実体コピー (vendoring) する。
symlink や plugin 外への import-time 依存は単独 install で dangling / ImportError になる。

二重実体は drift (内容乖離) リスクを生む。本 lint は「vendored 版 == 正本」を byte 単位で
機械検証し、乖離していれば exit 1 (fail-closed)。これにより「移植性のための実体コピー」と
「SSOT 単一正本」を両立させる。

正本 (canonical) は repo-root scripts/ 側か、当該 SSOT を保持する plugin 側。vendored は
コピー先の plugin 側 (scripts/ のほか lib/・vendor/・references/・schemas/・
skills/run-skill-feedback/ など)。runtime / build-time 中核モジュールに加え、「localize せず
正本と同一であること」を要件とする doc も byte 一致を強制する (plugin 別に文面を変える doc は
対象に入れない)。判断は役割で決める: 配布先で同じ契約を読ませたい doc は一致強制、
plugin 固有の説明は対象外。

本 lint は従来の lint-intake-vendored-ssot.py を一般化した後継。新規 vendored ペアは
VENDORED_PAIRS に1行足すだけで byte 一致が強制される。
"""
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _feedback_skill_mds():
    """run-skill-feedback を持つ plugin ごとに、その SKILL.md のパスを返す (正本の harness-creator も含む)。

    SKILL.md や run-skill-feedback の dir が symlink でも、link 先が消えていても除かない。
    除くとその plugin の組がまるごと検査から消え、回帰も drift も見逃す。symlink は
    check_pairs が回帰として報告する。SKILL.md を glob しないのは、link 先の消えた symlink を
    glob が拾わないため。
    """
    return sorted(
        skills / "run-skill-feedback" / "SKILL.md"
        for skills in ROOT.glob("plugins/*/skills")
        if os.path.lexists(skills / "run-skill-feedback")
    )


# (canonical 正本, vendored 複製) のペア。byte 一致を強制する runtime/build-time SSOT と、
# localize せず正本と同一であることを要件とする doc/schema。
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
        for skill in _feedback_skill_mds()
    ],
    # run-skill-feedback 本体は harness-creator を正本に、量産先へ実体コピーで配備される
    # (render-combinators.py apply_feedback_loop / feedback_contract_ssot.py の
    # is_feedback_deploy_exempt が正本側を除外する)。lint-feedback-protocol.py R7 は配備の
    # 「存在」しか見ないため、コピー後の drift を止めるのは本 lint だけ。この3点は量産先ごとに
    # localize せず正本と同一であることを要件とするので、doc でも byte 一致を強制する。
    # 配備を手書きで列挙しないので、配備の中で3点のどれかを欠くと存在検査で落ちる。
    # 配備 (run-skill-feedback の dir) そのものの有無は lint-feedback-protocol.py R7 が見る。
    *[
        (
            ROOT / "plugins/harness-creator/skills/run-skill-feedback" / rel,
            skill.parent / rel,
        )
        for skill in _feedback_skill_mds()
        if skill.parents[2].name != "harness-creator"
        for rel in (
            "SKILL.md",
            "workflow-manifest.json",
            "references/notion-submit-contract.md",
        )
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


def _symlinked_component(path):
    """ROOT から path までの各要素 (途中の dir と path 自身) のうち、最初の symlink を返す。

    ファイル自身が実体でも、plugins/<p>/scripts のような途中の dir が symlink なら
    単独 install で同じく dangling になる。ROOT より上 (/tmp -> /private/tmp など) は見ない。
    """
    current = ROOT
    for part in path.relative_to(ROOT).parts:
        current = current / part
        if current.is_symlink():
            return current
    return None


def check_pairs(pairs):
    """各ペアの存在・経路上の非 symlink・byte 一致を検査し failures リストを返す。"""
    failures = []
    for canonical, vendored in pairs:
        rel_c = canonical.relative_to(ROOT)
        rel_v = vendored.relative_to(ROOT)
        if not canonical.exists():
            failures.append(f"canonical 不在: {rel_c}")
            continue
        # symlink に戻っていないか (単独 install で dangling する回帰を検出)。
        # 存在確認より先に見る。link 先が消えた symlink も「不在」ではなく回帰として報告する。
        link = _symlinked_component(vendored)
        if link is not None:
            via = "" if link == vendored else f" (経路上の {link.relative_to(ROOT)} が symlink)"
            failures.append(
                f"vendored が symlink に回帰: {rel_v}{via} -> {link.readlink()}。"
                f" 単独 install で dangling になる。実体コピーへ戻すこと。"
            )
            continue
        if not vendored.exists():
            failures.append(
                f"vendored 不在: {rel_v} (単独 install 用の同梱が欠落)。"
                f" 正本 {rel_c} から実体コピーで再同期。"
            )
            continue
        # dir などは byte 比較できない (read_bytes が traceback で落ちる) ので、失敗として報告する。
        not_files = [str(rel) for path, rel in ((canonical, rel_c), (vendored, rel_v)) if not path.is_file()]
        if not_files:
            failures.append(f"通常ファイルでない: {', '.join(not_files)}。byte 比較できない。")
            continue
        if canonical.read_bytes() != vendored.read_bytes():
            failures.append(
                f"SSOT drift: {rel_v} が正本 {rel_c} と不一致。"
                f" 正本から再同期 (cp {rel_c} {rel_v})。"
            )
    return failures


def main(argv=()):
    # 引数は取らない。--help は usage で exit 0、知らない引数は検査せずに exit 2 (argparse)。
    argparse.ArgumentParser(description=__doc__.splitlines()[0]).parse_args(argv)
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
    sys.exit(main(sys.argv[1:]))
