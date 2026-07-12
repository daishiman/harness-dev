# plugin-rename-checklist — plugin 単位改名の不可分セットと手順

2026-07-02 の `skill-creator` → `harness-creator` 改名で確立した依存 DAG の恒久化。skill 単位の改名は `run-skill-rename` が担うが、plugin 単位の改名は fail-closed 機構のキー再割当と等価であり、以下を**単一 atomic commit** で行う。

## 不可分セット (別 commit に割ると中間状態で lint が FAIL する)

| # | 対象 | 場所 | 更新漏れ時の症状 |
|---|---|---|---|
| 1 | plugin dir | `plugins/<name>/` (git mv) | 全固定パス断線 |
| 2 | plugin.json `name` | `.claude-plugin/plugin.json` | validate-plugin-completeness の name==dir 検査 FAIL |
| 3 | plugin-composition.yaml `name` | plugin 直下 | composition lint 不整合 |
| 4 | `SELF_DOGFOODING_PLUGIN` | `scripts/feedback_contract_ssot.py` **正本+vendored の2実体** (byte 一致必須) | Stop hook 自己ブロック+feedback 自己配備の同時誤作動 (test は緑のまま) — parity test が fail-closed 化済み |
| 5 | `NEVER_DISTRIBUTE` | `scripts/validate-plugin-completeness.py` | 配布二重ロックの無音失効 — 実在 test が fail-closed 化済み |
| 6 | `VENDORED_PAIRS` 固定パス | `scripts/lint-vendored-ssot.py` | canonical 不在で FAIL |
| 7 | CI 固定パス | `.github/workflows/*.yml` + `Makefile` | red 化 or lint 対象消失の silent skip |
| 8 | enabledPlugins キー | `.claude/settings.json` | plugin 未ロード (hooks が黙って外れる)。**各ローカル環境の切替周知も必須** |
| 9 | upstream-pins | `plugins/plugin-dev-planner/.../upstream-pins.json` (path+sha256+verified_at) | check-upstream-pins fail-closed。**pin bump は matrix 行再監査と同一変更**。SSOT ファイルは 2 度触らず編集確定後に sha を 1 回再計算 |
| 10 | in-repo symlink repoint | 量産先 `run-skill-feedback` 群+`.claude/` (make sync 再生成) | dangling (R7 は warning 止まり) |
| 11 | テストファイル名 | `test_<old>__*` → `test_<new>__*` (underscore 形) | 命名規約と coverage 突合の非対称破損 |
| 12 | criteria_roster / coverage 台帳 | `tests/criteria/criteria_roster.py`, `eval-log/{llm,code,harness}-coverage.json` | criteria 突合 FAIL |
| 13 | 大文字 env 変数 | `<OLD>_*` → `<NEW>_*` (例: HARNESS_CREATOR_NO_REVIEW_BLOCK) | ハイフン/下線形の grep から漏れる。**全変形 (ハイフン/下線/大文字/camel/空白/日本語) を走査すること** |
| 14 | ファイル名に旧名を含むファイル | git grep でなく `find -name` で検出し git mv | 本文だけ新名でファイル名が旧名の不整合 |

## verdict (content-review) の移行

- SKILL.md 内容 sha 不変 → pointer-only retarget (`retargeted_from` キー、protocol §retarget 規約)
- 内容が変わった skill → 独立 SubAgent による genuine 再生成 (SHA 手書換は偽装)
- 旧 eval-log は凍結+tombstone README。新 run は新パスへ

## 完了検証 battery (機械層 8 + 意味論層 2)

1. 旧名 grep 残存が allowlist (凍結層) と一致
2. make lint 全通過 (vendored-ssot / legacy-plugin-name / content-review --all / plugin-completeness / upstream-pins)
3. 中央 pytest 直接実行 (run-ci-checks は pytest 非包含)
4. CI と同一 cwd での再現 (repo-root 緑は CI 緑を保証しない)
5. build-claude-symlinks --check
6. plugin 単独コピーで import-time クラッシュ無し
7. `is_stop_block_exempt("<new>")==True` smoke
8. git archive HEAD clean-checkout 検証
9. 概念判定インベントリ (判定台帳) の成果物化
10. proposer≠approver の独立レビューで台帳突合 APPROVE

## 再発防止

- 旧固有名の denylist lint (`scripts/lint-legacy-plugin-name.py` 型) を CI 配線し、並行 worktree からの merge 再流入を遮断
- 意図的リテラル (NEVER_DISTRIBUTE / pins / test assert) は**動的化しない** — fail-closed の設計意図 (改名時は本 checklist で全数同時更新)
