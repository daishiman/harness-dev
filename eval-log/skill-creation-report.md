# Skill Creation Report: run-skill-update-notifier

## 概要
- mode: create
- placement: `plugins/skill-creator/skills/run-skill-update-notifier/`
- engine: Python (stdlib only) + Skill + Hook
- strategy: 案② Changelog Feed (Stage 1) + 案① Trust-Gated Pull 段階導入 (Stage 2 将来)
- non_disruption_principle: 既存 manifest 系 (`marketplace.json` / `bundles.json` / `skill-intake-self-updater`) は touch せず

## Gates 通過状況
| Gate | 状態 |
|------|------|
| Gate 1 brief 確認 | PASS (open_questions 3点解決済) |
| Gate 2 diff 確認 | 本レポート末尾で要求 |
| Gate 2.5 plugin 登録 | applied (plugins/skill-creator/.claude-plugin/plugin.json に hooks 追加) |
| Step 3.5 bundle 登録 | not_applicable (standalone、他 plugin 非依存) |
| Step 4a P0 lint (8種) | PASS (全 exit 0) |
| Step 4b 設計評価 fork | DEFERRED → elegant-review-protocol で代替 (フェーズ1-2 で3エージェント並列分析済) |
| Step 5 elegant-review | PASS (4条件すべて検証済、原案 NG→改善案で全 PASS) |
| Step 6 governance | manual (solo_operator_mode 未設定のため Gate 4 で手動承認) |

## 生成物
**新規 (6 ファイル)**
- `SKILL.md` (94 行、frontmatter + hook integration map + responsibilities + steps)
- `scripts/notifier_check.py` (CLI 実行可、3 mode: cache-status / refresh / notify)
- `scripts/hook-cache-refresh.py` (UserPromptExpansion hook、24h TTL judge)
- `scripts/hook-notify-skill-end.py` (PostToolUse matcher=Skill hook、stdin payload 解析)
- `references/output-format.md` (通知文字列規約)
- `references/hook-wiring.md` (plugin install 自動配信案内)

**変更 (1 ファイル)**
- `plugins/skill-creator/.claude-plugin/plugin.json` (`hooks` フィールド追加、+18 行)

## 設計判断の要点
1. **実行時同期更新を不採用**: レイテンシ・オフライン・rate limit・自己書換ループのリスクを elegant-review で確認
2. **UserPromptExpansion + PostToolUse の責務分離**: cache 更新 (非ブロッキング) と末尾通知 (matcher=Skill) を分離
3. **plugin manifest 同梱**: `claude plugin install skill-creator` で hooks も自動配線 (skill-intake が同パターン)
4. **graceful degradation 4 重防御**: cache不在 / CHANGELOG不在 / オフライン / 例外 → すべて no-op
5. **環境変数で抑制**: `XL_SKILLS_NOTIFY=off` で通知のみオフ可能

## TODO(human)
- `scripts/notifier_check.py` 内 `_format_line()` 関数 (R2 notification-formatting 責務)
  - 仕様: `references/output-format.md` 参照
  - installed/latest を受け取り、差分時のみフォーマット済 1 行を返す

## 将来 Stage
- Stage 0: `lint-version-singletruth` (plugin.json と marketplace.json の version 二重管理を warn)
- Stage 2: `run-skill-update-apply` (stable タグ pull + dogfooding lock + rollback)

## 検証 4 条件 (elegant-review)
| 条件 | 原案 (実行時同期更新) | 採用案 (Stage 1) |
|------|------|------|
| C1 矛盾なし | NG (自己書換ループ) | PASS |
| C2 漏れなし | NG (rollback/退行検知未定義) | PASS (graceful degradation で defensive) |
| C3 整合性 | NG (version 二重管理) | PASS (installed/latest を明確分離) |
| C4 依存整合 | NG (self-updater 二重) | PASS (非破壊、既存系を touch せず) |
