# Phase 01 — 要件確定レポート

- 対象: skill-intake plugin 拡張 (existing-plugin-update)
- 実装区分の判断: 本計画は `component-inventory.json` で `build_status=planned` の**計画ドキュメント**だったが、7 層コード実装プロンプト CONST_006 (実態 over ラベル) に従い、ゴール「procedure 軸を intake.json ハンドオフへ格納」は**実コード変更**を要すると判断し実装を実施した。ドキュメントのみに留めず `plugins/skill-intake/` 配下へ実装した根拠を本サイクル冒頭で明示する。

## 要件 (goal-spec 由来)

現状 `interview.json` に **現状実施手順 (as-is procedure)** の軸が無く、手順が推測ベースで build され手戻りが発生している。これを解消するため:

1. **C1/C6 procedure 抽出**: run-intake-interview に 6 本目の軸として procedure (順序付きステップ × 入力/出力/使用ツール/頻度) を追加し `interview.json` に構造化格納する。
2. **C2 決定論フォールバック**: 手順を言語化できないユーザー向けに、2 連続抽象判定/未回答で `overview_fallback` (工程数目安/関与者/頻度) へ**決定論的に**切り替え、ヒアリングを停止させない。
3. **C3 dual-gate**: purpose (真の課題) と procedure の両方が揃うまで Phase9 (run-intake-finalize) / `quality_gate.py` で下流ハンドオフ (run-skill-create/run-plugin-dev-plan) へ進めない。
4. **C7 as-is/to-be 分離**: handoff 対象 as-is フィールド (`procedure.*` / 真の課題) に to-be 語彙 (べきである/理想は/最適化/より良い方法/一般的には 等) を混入させないゲート。
5. **C8 具体性記録**: 課題/流れ/実行したいことを固有名詞・実例・頻度・関与者の相手固有の具体性で記録し、平均回帰・一般化を禁止する。

## component (4 本, 新規 sub-agent/command/hook なし)

| id | kind | build_target | 責務 |
|----|------|--------------|------|
| C01 | skill | `skills/run-intake-interview/` | procedure 抽出 + フォールバック + as-is 忠実記録 (拡張) |
| C02 | script | `scripts/validate-procedure-completeness.py` | 完全性 + contamination 検証 (新設) |
| C03 | skill | `skills/run-intake-finalize/` | dual-gate 実行 + validation 格納 (拡張) |
| C04 | script | `scripts/quality_gate.py` | `--require-procedure` で purpose+procedure 両立強制 (拡張) |

## 非スコープ

手順の最適化・理想化 (to-be 設計) は後段 build の責務。procedure-excavator 相当の新規 SubAgent は非 adversarial な直接聴取のため新設しない (既存 4 SubAgent の分離パターン=起動独立性×LLM 自律 dispatch に該当しない)。
