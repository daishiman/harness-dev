---
name: slide-report-status
description: 生成中の slide デッキ / レポートの進行フェーズを確認 — vendor workflow-manager と成果物の有無で現在 Phase と次アクションを表示する
argument-hint: "<project-dir>"
allowed-tools: Bash, Read
disable-model-invocation: false
---

# /slide-report-status

生成中の出力ディレクトリ `$ARGUMENTS` の進行状況 (現在 Phase・次アクション) を確認する。

## 振る舞い

1. `$ARGUMENTS` を対象プロジェクトディレクトリ (`index.html` / `report.html` / `structure.*` / `report-structure.*` を含むデッキ or レポートの出力先) として受け取る。
2. vendor の workflow-manager で現在 Phase と検証結果を見る:

   ```bash
   node "${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/vendor/scripts/workflow-manager.js" "$ARGUMENTS" --verbose
   # 上の「現在のPhase」が P2_5 か P3 のときだけ
   node "${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/vendor/scripts/workflow-manager.js" "$ARGUMENTS" --check
   ```

   - `--verbose`: gate を回さずに、プロジェクトディレクトリのファイル状態 (structure.md / index.html / deploy-guide.md / .approved / .workflow-state.json) から現在 Phase を判定し、Phase 検証とファイル状態を出す。
   - `--check`: 現在 Phase に紐づく phase-gate.js も回す。P2_5 と P3 の gate は読むだけだが、P3_5 の gate は verify-slides.js が `$ARGUMENTS/screenshots/slide_NN.png` を書くので、P3_5 とほかの Phase には付けない。P3_5 では UI 検証の gate を回していないことを示す。
3. 出力の Phase (P1 ヒアリング → P2 構成設計 → P2.5 仕様確定ゲート → P3 HTML 生成 → P3.5 UI 検証 → 完了) と検証結果を要約し、次アクションは成果物の有無から示す (備考)。

## 備考

- `$ARGUMENTS` (project-dir) が未指定の場合は、直近に生成した出力ディレクトリのパスを尋ねてから実行する。
- workflow-manager の Phase 判定が効くのは `structure.md` を持つ slide デッキだけである。report mode の出力 (`report.html` / `report-structure.json`) と `structure.md` の無いディレクトリでは、その Phase を表示せず、「workflow-manager では判定できない」と示す。workflow-manager の「次のステップ」は旧い Phase の文面なので、どのディレクトリでも表示せず、次アクションは成果物の有無 (R2 の構成・R3 の生成物など) から示す。既定経路では `.approved` を作らないので、「`.approved` マーカー未取得」も次アクションにしない (exit code はそのまま示す)。読み替えの正本は `skills/run-slide-report-status/SKILL.md` の「workflow manager の出力の読み替え」。
- `python3 "${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/scripts/validate-output-mode.py" --preflight` で node/npm と plugin-local Chromium の状態を確認する。Chromium欠落時は、この command からは復元しない。preflight が示す `setup-playwright.py --install` を、利用者が回す remediation として示す。
