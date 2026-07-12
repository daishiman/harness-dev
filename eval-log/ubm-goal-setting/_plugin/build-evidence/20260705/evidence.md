# ubm-goal-setting — P11 evidence (build 検証記録)

- **記録日**: 2026-07-05
- **契約正本**: `plugin-plans/ubm-goal-setting/phase-11-evidence.md` §成果物 (evidence 5 要素)
- **生成契機**: elegant-review `eval-log/ubm-goal-setting/_plugin/elegant-review/20260705-082331/` の findings A2-05 / A2-09 / A4-08 (P09-P11 証跡不在) の遡及補完
- **実行 cwd**: repo root (lint) / `plugins/ubm-goal-setting/` (pytest = CI が実際に使う cwd に pin。repo-root 実行結果は CI 緑の証跡として扱わない)

## 要素1 — P0 lint 実行ログ (exit 0)

`plugins/ubm-goal-setting/EVALS.json` の `harness.mechanical` 全 13 行を repo-root cwd で実走した。
**結果: 13/13 exit 0 (赤 0 件)**。コマンド別 exit code と出力末尾は同ディレクトリの
[`p0-lint-run.json`](./p0-lint-run.json) に機械記録した。

対象 lint (kind 被覆): pytest (script/hook 機能テスト) / lint-script-frontmatter (skills+hooks) /
validate-frontmatter / lint-skill-name / lint-skill-description / lint-skill-tree /
lint-dependency-direction / lint-skill-dep-step7 / lint-forbidden-deps / lint-manifest-contents /
lint-agent-prompt-section (sub-agent 10 本) / check-knowledge-split (knowledge 500 行ガード)。

## 要素2 — schema parity テストの結果

- 共有 surface `plugins/ubm-goal-setting/knowledge/schema.json` の実在 + sha256 を
  [`build-trace.json`](./build-trace.json) の `plugin_level_surfaces.shared_knowledge_schema` に記録 (C16 info-collector 読取 / C17 knowledge-extractor 書込の対称参照先)。
- knowledge データ層の parity は `tests/test_knowledge_counts.py` (6 テスト・全 PASS) が機械検証:
  router.json の総エントリ数/カテゴリ別件数/サブカテゴリ合計がディスク上の 28 JSON と一致・
  orphan ファイル 0 件・registry.json 内部整合 (67 ソース) ・legacy null の `_note: legacy` マーキング。
- frontmatter schema parity は要素1 の validate-frontmatter / lint-script-frontmatter が exit 0。

## 要素3 — build-trace coverage の結果

`handoff-run-plugin-dev-plan.json` routes 18 component の build_target について、実在 + sha256
(skill dir は配下全ファイルの sorted `relpath:sha256` 連結 tree digest) を機械生成した。
**結果: 18/18 実在 (missing 0 件)**。plugin-level surface 4 点 (plugin.json /
plugin-composition.yaml / EVALS.json / knowledge/schema.json) も実在 + sha256 を併記。
正本: [`build-trace.json`](./build-trace.json)。

## 要素4 — content-review verdict

独立 content-review は elegant-review run `20260705-082331` (3 analyst 並列・
`eval-log/ubm-goal-setting/_plugin/elegant-review/20260705-082331/findings-phase2-*.json`) を
正本とし、検出された計画↔実体の乖離は同 run の Phase 3 で修正済み。

- 限界の明示 (捏造回避): P09 契約が想定する per-component verdict 18 件 (sha_match 付き) の
  形式では生成しておらず、plugin 全体 scope の findings 形式レビューが実施済みの独立検証である。
  per-component verdict の個別生成は後続改善 (P13 前) の残タスクとして扱う。

## 要素5 — harness coverage

- `plugins/ubm-goal-setting/` cwd で `python3 -m pytest tests/ -v` を実走: **44 passed / 0 failed**
  (ログ: [`harness-pytest.txt`](./harness-pytest.txt))。
- kind 別被覆: script×3 (validate-goal-output 11 / detect-knowledge-updates 8 /
  check-knowledge-split 7) + hook×1 (write-path-guard 12) + knowledge 台帳整合 6 = 44 テスト。
  skill×2 は golden-sample 回帰 (`test_golden_sample_passes` + 変異 FAIL 群) と
  `EVALS.json` `llm_eval` の criteria-test 配線が受入を担う。
- 数値行カバレッジ JSON は未計測 (テストが script/hook を subprocess 実行するため pytest-cov の
  行計測が届かない)。床の担保は `EVALS.json` `threshold_note` の契約どおり pytest 機能テスト +
  golden-master 回帰で行う (数値の捏造をしない)。

## 第三者再現手順

```bash
# repo root で (要素1: 13 行の正本は EVALS.json harness.mechanical)
python3 - <<'EOF'
import json, subprocess
for cmd in json.load(open("plugins/ubm-goal-setting/EVALS.json"))["harness"]["mechanical"]:
    print(subprocess.run(["bash", "-c", cmd]).returncode, cmd)
EOF
# 要素5 (CI cwd に pin)
cd plugins/ubm-goal-setting && python3 -m pytest tests/ -q
```
