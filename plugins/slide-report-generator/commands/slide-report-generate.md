---
name: slide-report-generate
description: スライドデッキ / HTML レポートを生成 — --mode slide|report で出力形態を選び、run-slide-report-generate スキル (ヒアリング→構成設計→仕様確定ゲート→生成→生成後評価) を一気通貫で起動する
argument-hint: "[--mode slide|report] [--report-type internal-analysis|client-proposal|tech-doc|learning] <topic>"
allowed-tools: Skill, Task, Read, Write, Edit, Bash
disable-model-invocation: false
---

# /slide-report-generate

ユーザー要望 `$ARGUMENTS` を受け取り、`run-slide-report-generate` スキルを起動して slide デッキ / HTML レポートを生成する。

## 振る舞い

1. `$ARGUMENTS` を解釈し、`Skill(run-slide-report-generate, args="$ARGUMENTS")` を起動する。
2. `--mode` の扱い:
   - `--mode slide` (既定): 1 スライド 1 メッセージのプレゼンデッキ (16:9 / chip 強制 / 長文禁止)。`structure.schema.json` で構成を確定し `index.html` を生成する。
   - `--mode report`: 読み物 HTML レポート (セクション + 段落 + 1 項目 1 ビジュアル)。`report-structure.schema.json` で構成を確定し `report.html` を生成する。`--report-type` が必須。
   - `--mode` 省略時は hearing-facilitator が対話で `output_mode` を確定する。
3. `--report-type` の扱い (report 時のみ有効・4 enum): `internal-analysis` / `client-proposal` / `tech-doc` / `learning`。slide 時に指定するのは矛盾のため、下流送信前に `scripts/validate-output-mode.py` が値域・整合を fail-closed 検証する (値域外・矛盾は exit 2 で停止)。
4. スキル側フロー: R1 ヒアリング (mode 確定) → R2 構成設計 + 仕様確定ゲート → R3 生成 (HTML / 決定論レンダラ / Codex 画像) + 生成後評価 (deck-evaluator, mode-aware)。
5. 完了後、出力ディレクトリ (index.html / report.html 等) と評価結果のパスを返す。

## 事前条件

- node / npm が PATH に在ること (決定論レンダラ・評価に必要)。`python3 "$CLAUDE_PLUGIN_ROOT/scripts/validate-output-mode.py" --preflight` で node/npm/vendor/node_modules/codex CLI の検出を確認できる (欠落は warning・非停止)。
- vendor エンジンは `$CLAUDE_PLUGIN_ROOT/vendor/scripts/` から `node` で起動する。

## 備考

- `report` mode で `--report-type` が無い場合、スキルはヒアリングで reportType を確定するか、明示指定を促す。
- 生成後は PostToolUse フック (`hooks/hook-postgen-eval.py`) が中核ファイル書込を検知し、mode を判定して deck-evaluator による生成後評価を促す。
