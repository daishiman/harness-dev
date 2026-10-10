# エージェントへ渡すルートの契約

親スキルは「実行時のルートの決め方」で解決した値を各 Task の入力へ渡す。サブエージェントは cwd や未設定の環境変数から推測しない。

| 入力 | 出所 | 検証・用途 |
|---|---|---|
| `plugin_root` | host が示した親 SKILL.md の絶対パスから特定したプラグインのルート | 必須。絶対パス、実在する定義ファイル（`.codex-plugin/plugin.json` または `.claude-plugin/plugin.json`）を確認し `PLUGIN_ROOT` に設定する |
| `project_root` | host が示した呼び出し元プロジェクトのルート。Claude Code では `CLAUDE_PROJECT_DIR` | eval-log を参照する Task で必須。絶対パスを確認し `PROJECT_ROOT` に設定する。plugin_root と混同しない |
| `vault_root` | 親が `UBM_VAULT_ROOT` を絶対パスとして検証した結果 | vault を読む/書く Task で必須。未接続なら親がその Task を実行せず、知識だけの対話へ縮退する。空文字から `/05_Project` 等を作らない |

値が不在・相対パス・宣言した対象範囲と不一致なら、外部の Read/Write/Bash の前に停止する。エージェント本文の `$PLUGIN_ROOT`・`$PROJECT_ROOT`・`$UBM_VAULT_ROOT` はこの検証済みの値を表す。Read/Write/Glob の引数には親または Task が展開した絶対パスを使い、シェル変数の文字列を直接渡さない。Bash を呼ぶたびにそのシェルへ検証済みの値を設定する。

移行中に `CLAUDE_PLUGIN_ROOT` を使う呼び出し元があれば、親が `PLUGIN_ROOT` と同じ値を渡す。エージェントは旧変数への依存を持たず `PLUGIN_ROOT` を使う。シンボリックリンク経由の書き込みは各書き手の対象範囲検証で停止する。
