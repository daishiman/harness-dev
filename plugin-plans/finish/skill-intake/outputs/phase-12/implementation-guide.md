# skill-intake procedure 軸拡張 — 実装ガイド

skill-intake plugin に「現状実施手順 (as-is procedure)」の構造化抽出軸を追加した拡張の総合ガイド。

## 1. 何が追加されたか

5 軸ヒアリング (出力先/情報源/共有相手/真の課題/ナレッジ資産) に加え、ユーザーの**現状の実施手順**を構造化 JSON として `interview.json` → `intake.json` へ格納する。手順を言語化できないユーザーには決定論フォールバックで概略収集へ切り替え、ヒアリングを停止させない。purpose (真の課題) と procedure の両方が揃うまで下流ハンドオフ (run-skill-create / run-plugin-dev-plan) へ進めないゲートを設ける。

## 2. データモデル

### procedure ブロック (2 モード)

```jsonc
// detailed モード
"procedure": {
  "mode": "detailed",
  "steps": [
    { "action": "...", "input": "...", "output": "...", "tool": "...", "frequency": "..." }
  ]
}

// overview_fallback モード (手順化困難時)
"procedure": {
  "mode": "overview_fallback",
  "difficulty_flag": true,
  "overview": { "step_count_estimate": "...", "participants": "...", "frequency": "..." }
}
```

- 正本 schema: `skills/run-intake-interview/schemas/output.schema.json` (procedure は additive・required 外)。
- intake 側: `references/intake.schema.json` の `$defs/procedure` + `sections.6_five_axes_summary.procedure`。
- validation: `$defs/validation_block.procedure_completeness` (complete/mode/missing/contamination) → root `validation`。

## 3. コンポーネント (DAG: C01→C02→C03→C04)

| id | 種別 | 実体 | 役割 |
|----|------|------|------|
| C01 | skill | `skills/run-intake-interview/` | procedure 抽出 + フォールバック + as-is 忠実記録 |
| C02 | script | `scripts/validate-procedure-completeness.py` | 完全性 + contamination 検証 |
| C03 | skill | `skills/run-intake-finalize/` | dual-gate 実行 + validation 格納 |
| C04 | script | `scripts/quality_gate.py` | `--require-procedure` で purpose+procedure 両立強制 |

## 4. 決定論分岐 (C2 — 停止しない原則)

`validate-answer-abstraction.py --axis procedure` が回答を判定:
- 空/未回答フレーズ検出 → abstract=True かつ unanswered=True。
- **2 連続**の abstract/unanswered → `overview_fallback` へ切替。
- 同一入力 → 同一経路 (LLM 判断非介在)。

## 5. as-is/to-be 分離 (C7)

`to-be-vocabulary-patterns.md` を正本に C02 が 3 層で機械パース:
- **強シグナル** (べきである/理想は/本来は/一般的には): 単独出現で混入。
- **弱シグナル** (最適化/効率化/自動化): 当為表現との共起でのみ混入。名詞的用法は `detected=false` + warn。
- **当為表現**: 弱シグナルの近傍共起語。

混入検出時は Phase4 へ差し戻し。同一 axis 上限 2 回で warning 降格 + 人間確認 1 回へ escape (停止回避)。

## 6. 使い方 (finalize dual-gate)

```bash
# procedure 完全性 + as-is フィールドへの to-be 非混入
python3 ${CLAUDE_PLUGIN_ROOT:-plugins/skill-intake}/scripts/validate-procedure-completeness.py \
  --interview output/<hint>/interview.json
# → exit 0=complete&clean / 1=incomplete or contaminated / 2=usage

# purpose + procedure 両立強制
python3 ${CLAUDE_PLUGIN_ROOT:-plugins/skill-intake}/scripts/quality_gate.py \
  --require-procedure output/<hint>/intake.json
```

exit 0 のときのみ procedure を `sections.6_five_axes_summary.procedure` へ、C02 stdout を `validation.procedure_completeness` へ格納する。

## 7. 後方互換

- procedure は schema の required 外 (additive) → 既存 v1/v2 intake 非破壊。
- **migration_warn パターン**: procedure 非認識 intake は quality_gate でゲート降格 (警告のみ)。既存 45 テストが緑維持。
- true_purpose は dual-source 抽出 (`sections.3.true_purpose` OR `sections.6.axes[real_problem].answer`) で v1/v2 格納位置差を吸収。

## 8. 保守: 派生スナップショットの再生成順序 (重要)

criteria を増減したら、**必ず roster → coverage の順**で再生成する (逆順だと coverage が stale):

```bash
python3 tests/criteria/build_criteria_roster.py --write   # ① 先に roster を確定
python3 scripts/validate-llm-coverage.py --all            # ② roster に依存する coverage を再生成
```

plugin version を bump したら:
```bash
# plugin.json と marketplace.json の version を揃えてから
python3 scripts/lint-config-version-sync.py --write        # baked-config lockfile 再生成
```

## 9. テスト

- `tests/scripts-plugins/test_skill_intake__validate_procedure_completeness.py` (43)
- `tests/scripts-plugins/test_skill_intake__interview_procedure.py` (25)
- `tests/scripts-plugins/test_skill_intake__quality_gate.py` (procedure 拡張分含む)
- 全体回帰: `python3 -m pytest tests/ -q` → 6380 passed / 0 failed。

## 10. 既知の残課題 (backlog)

- purpose-excavator (8 技法) への procedure 接続は本サイクル見送り (P01 gap)。procedure 抽出は非 adversarial な直接聴取のため独立 SubAgent 化の動機がなく、会話継続性の中で完結する設計を採用。
