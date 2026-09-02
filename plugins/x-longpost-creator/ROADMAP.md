# Roadmap — x-longpost-creator

## 次にやる候補

| 項目 | 目的 | 状態 |
|------|------|------|
| scripts のテスト維持 | x-longpost 固有の text / visual / contract / log parity テスト一式で回帰検証。`validate-headings.js` の F4/F5と失敗原子性に加え、2サムネイルの既定生成・strict寸法・構造一致・review receipt/hash ゲートを検証済み | 実装済み |
| 検証フラグの既定化 | H5 は `--strict-h2-count`、F1〜F5 は `--file` を渡したときだけ FAIL になる。付け忘れると宣言どおりに検証されないため、既定を strict 側へ倒すか呼び出しを機械強制する（`EVALS.json` の known_limitations 参照） | 未着手 |
| `distributable: true` 化 | 個人パスの除去は完了済み（出力先は env のみで解決し fail-closed）。残る非配布理由は特定の書き手のスタイルゲノム依存と個人 vault の運用前提。この 2 点を切り出せるか検討する | 検討中 |
| スタイルゲノムの外部化 | 現在 plugin ルートの `references/style-genome.md` に L1〜L8 の値を焼き込んでいる。書き手ごとに差し替え可能な入力として切り出せば、plugin を書き手非依存にできる | 検討中 |
| 短文投稿フォーマットの追加 | 移植元は 8 パターン。実測 Views の再集計で有効パターンを見直す | 検討中 |
| Codex 経路の実画像検証 | 実行ファイル preflight・argv 構築・dry-run・欠落時の retry ゼロは自動検証済み。課金を伴う実画像生成と session image 回収は Codex 上で未検証 | 一部実装 |

## やらないこと

- scripts の Python 移植 — Node.js のまま維持する（移植時に確定済み）
- 移植元スキルの履歴（v3.13.0 以前）の取り込み — CHANGELOG は v1.0.0 から開始する
- 絵文字の条件付き許可 — 絶対遵守ルールとして例外を設けない
