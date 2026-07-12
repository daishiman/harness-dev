# ROADMAP

`prompt-creator` plugin の短期 / 中期 / 長期ロードマップ。設計書 33 章 `change-governance` の運用方針に従い、各層は目標・成果物・成功指標 (KPI) を明示する。

## 短期 (本 PR 〜 次 1-2 スプリント)

**目標**: harness-creator 仕様準拠化を完遂し、独立 evaluator + ゲート制御 orchestrator を自走させる。**成果物**: 4 SKILL.md commonCore 化 / `plugin-composition.yaml` / Script First (python3) 全面移行 / CI 配線 / 移行スクリプトの正式リネーム (PENDING 解除)。**KPI**: P0 lint 全緑率 100%、design-evaluate overall=PASS 率 >= 90%、PENDING_RENAME 残数 0。

## 中期 (3-6 ヶ月)

**目標**: 7 層プロンプトの冪等更新ループを完成させ、既存プロンプトの肥大化を抑制しながら継続改善を回す。**成果物**: 冪等更新 policy の lint 化 (重複要素検出)、prompt-rubric.json L1 (ドメイン層) の整備、prompt-creator → harness-creator への評価 feedback 自動化。**KPI**: 同一スキルの 2 回目以降更新で要素重複増加率 <= 5%、L1 rubric 採用プロンプト割合 >= 50%、feedback PR 月次マージ >= 1 本。

### Follow-up (elegant-review v2 / 2026-05-24 検出 → 2026-07-02 elegant-review で処遇確定)

**本 PR 同梱 (解消済み / 実施中)**:
- **責務境界の明確化** [DONE 2026-07-02]: `run-prompt-creator-7layer` Phase 1 を `run-prompt-elicit` への委譲に一本化。elicit 側は単独起動と委譲呼出の両対応を SKILL.md invariant で明文化 (ヒアリング正本の分裂を解消)。
- **`parse_known_args` 統一見直し** [本 PR 実施中]: 8 移行スクリプトの未知 flag 黙殺設計を failfast へ転換 (7layer 側パッチで対応中)。

**期限付き残 (次スプリント = 2026-07 中に消化、未消化なら issue 化して追跡)**:
- **scaffold-prompt.py の呼び出し例明示**: 7layer SKILL.md 本文に scaffold-prompt.py 呼び出し例を 1 行追加し `script_refs` との対応を可視化。
- **frontmatter コメント正規化**: 7layer SKILL.md の YAML コメント (`# context-budget (CD-005)`) を正式フィールド (`context_budget`) に昇格。
- **shared scripts 表記**: `plugin-composition.yaml` に `shared_scripts` セクションを追加し、`run-prompt-create` から `run-prompt-creator-7layer/scripts/` への cross-skill 参照意図を明示。

## 長期 (6 ヶ月以降)

**目標**: 7 層構造を他プラグインへ横展開し、SubAgent / Skill 全体のプロンプト品質を底上げする。**成果物**: 7 層 schema の plugin 横断採用、cross-plugin プロンプト品質ダッシュボード。**KPI**: 7 層採用プラグイン数 >= 5、ダッシュボード evaluator pass 率 >= 85%、dogfooding 自己適用率 >= 90% の継続維持。

> **dogfooding (自プロンプトを自評価) は 2026-07-02 の plugin-wide elegant-review (run 20260702T065933) で本 PR にて実施済み**: Layer 5 契約 (l5-contract v2.0.0) への自プロンプト冪等更新 + verify-completeness / validate-prompt の before/after 機械 baseline 採取 (`eval-log/prompt-creator/_plugin/elegant-review/20260702T065933/before-machine-baseline.txt`)。長期には継続 KPI のみ残す。
