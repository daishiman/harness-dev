---
name: slide-report-status
description: 生成中の slide デッキ / レポートの進行フェーズを確認 — vendor workflow-manager で現在 Phase と次アクションを表示する
argument-hint: "<project-dir>"
allowed-tools: Bash, Read
disable-model-invocation: false
---

# /slide-report-status

生成中の出力ディレクトリ `$ARGUMENTS` の進行状況 (現在 Phase・次アクション) を確認する。

## 振る舞い

1. `$ARGUMENTS` を対象プロジェクトディレクトリ (`index.html` / `report.html` / `structure.*` / `report-structure.*` を含むデッキ or レポートの出力先) として受け取る。
2. vendor の workflow-manager で現在 Phase と次アクションを判定する:

   ```bash
   node "${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/vendor/scripts/workflow-manager.js" "$ARGUMENTS" --check --next
   ```

   - `--check`: プロジェクトディレクトリのファイル状態 (structure.md / index.html / styles.css / scripts.js / .workflow-state.json 等) から現在 Phase を判定・検証する。
   - `--next`: 次に実行すべき Phase / agent をガイドする。
3. 出力の Phase (P1 ヒアリング → P2 構成設計 → P2.5 仕様確定ゲート → P3 HTML 生成 → P3.5 UI 検証 → 完了) と、次アクションを要約して表示する。

## 備考

- `$ARGUMENTS` (project-dir) が未指定の場合は、直近に生成した出力ディレクトリのパスを尋ねてから実行する。
- report mode の出力 (`report.html` / `report-structure.json`) でも同じ workflow-manager でファイル状態から進行を確認できる。
- `python3 "${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/scripts/validate-output-mode.py" --preflight` で node/npm と plugin-local Chromium の状態を確認する。Chromium欠落時は `setup-playwright.py --install` でプラグイン配下へ復元する。
