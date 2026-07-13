# Phase 11 — エビデンスレポート

本拡張は UI/UX を持たない (ヒアリング skill + 決定論 script) ため、視覚検証に代えて**決定論ゲート・テスト・ゲート実行ログ**をエビデンスとする。

## テスト実行エビデンス

### procedure 関連 (追加分)
```
$ python3 -m pytest tests/scripts-plugins/test_skill_intake__validate_procedure_completeness.py \
    tests/scripts-plugins/test_skill_intake__interview_procedure.py \
    tests/scripts-plugins/test_skill_intake__quality_gate.py -q
127 passed
```

### 派生スナップショット parity
```
$ python3 -m pytest tests/test_llm_coverage_parity.py tests/criteria/test_all_skills_criteria.py -q
153 passed
$ python3 scripts/validate-llm-coverage.py --all --check
OK: llm-coverage.json は最新 (42 skills / 平均 100.0%)
```

### 計画↔実体 completeness ゲート
```
$ python3 plugins/harness-creator/scripts/validate-plan-coverage.py \
    plugin-plans/skill-intake/component-inventory.json
OK: plan coverage — 4 component + required surface すべて実在 (plugins/skill-intake)
```

### config version sync
```
$ python3 scripts/lint-config-version-sync.py
[config-version-lock] OK: 3 件の焼き込みconfigが version と同期しています。
```

## リポジトリ全体回帰

```
$ python3 -m pytest tests/ -q
<最終確定値は本レポート末尾 "全体回帰結果" に追記>
```

## C02 exit code 契約エビデンス

- 完全 + 混入なし → exit 0
- 不完全 or contamination detected → exit 1
- usage エラー → exit 2

## 変更規模 (git diff --stat)

- 実コード/テスト/config: 15 files changed, 520 insertions(+), 28 deletions(-)
- 新規 4 ファイル (C02 script / to-be 語彙 reference / 新規テスト 2)

## 全体回帰結果

```
$ python3 -m pytest tests/ -q
6380 passed, 4 skipped in 122.89s (REAL_EXIT=0)
```

**0 failed**。収束経路: 中間で 1 failed (llm-coverage parity) が出たが、真因は派生物の依存順序 (criteria_roster.py を先に確定してから llm-coverage.json を再生成すべきところ、逆順で生成し stale 化) と判明。roster→coverage の順で再生成し冪等・parity 緑を確認した。
