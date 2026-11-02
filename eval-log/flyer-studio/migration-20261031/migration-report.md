# flyer-studio 移行・互換性確認

2026-10-31。移行版は **1.3.1**。`HarnessHub/plugins/flyer-studio` から `/Users/dm/dev/dev/個人開発/harness/plugins/flyer-studio` へ反映した。元リポジトリは保持し、元ファイルの欠落と素材の内容差異は0件。依存キャッシュ・セッション記録は取り込まず、開発計画と過去の検証記録は履歴として保持した。詳しい対応は [migration-manifest.json](migration-manifest.json)。

## 適合のための変更

- 全6スキルの登録と利用者の直接入口4つを区別し、Codexで専門観点を完成評価へ渡す経路、ホスト別の実行ルートを明記した。
- ホスト公開面のDAG、スキル内部の4担当、FIXの差し戻しを別々に宣言した。自己検査は全てを照合する。
- 初稿の引き渡しと選択後の改善・独立評価を分けた。初稿を納品完了とは扱わず、最初から検証まで明示された依頼は再確認しない。
- JSON形式の部品台帳を共通検査と採番ツールでも読めるようにし、破損・型不正の拒否を回帰検査した。共通側は harness-creator 1.4.50、skill-governance-lint 0.1.21。
- 個人素材の公開配布は禁止したまま、ClaudeのローカルカタログとCodexのリポジトリカタログへ登録した。通常のユーザー設定・インストール状態・信頼設定は変更していない。
- 単独キットではリポジトリ専用の観測依存と中央ポリシー投影を除く。制作の依存ライブラリは固定済みlockfileから導入する。

## 実施結果

| 確認 | 結果・証跡 |
|---|---|
| plugin本体 | 224件成功、条件付き5件スキップ。[tests.log](tests.log) |
| 単独キットの回帰検査 | 6件成功。[kit-regression-tests.log](kit-regression-tests.log) |
| 共通ツールの回帰検査 | 243件成功。全体の採番状態を見る1件は下記の対象外差分を切り分けて除外。[common-tests.log](common-tests.log) |
| creatorの正式パッケージ検査 | PKG-002〜008・014の8項目成功。[独立検査](independent-package-check.json)、[意味の独立レビュー](independent-package-review.json) |
| plannerの仕様 | 正式11ゲート成功。歴史計画の構造は適合するが現物との差がある。[独立所見](plan-findings.json) |
| Claude Code 2.1.314 | 一時的な専用設定ディレクトリで実インストール成功。[claude-install.json](claude-install.json) |
| Codex CLI 0.165.0 | 一時的な専用設定ディレクトリで実インストール成功。app-serverのskills/listで6スキル全て有効と確認。[導入](codex-install.json)、[実検出](codex-skills.json) |
| 最終版の単独コピーからの実行 | `/tmp` を作業場所とし、doctor成功、2案のHTML/PDF/PDF由来PNGを生成。QR等の機械検査でfail=0。[doctor.json](doctor.json)、[render.log](render.log)、[render-check.json](render-check.json) |
| 登録・共通制御 | 両ホスト同期・ローカルカタログ・公開登録の完全性・部品台帳・初稿引渡し規則の検査に成功。各checkログを同ディレクトリへ保存 |

単独キットは `/private/tmp/flyer-harness-migration-final-20261031`（157ファイル）と隣接ZIP。全ファイルとZIPのSHAを独立照合した。[kit.json](kit.json)

## 確認範囲と残件

描画試験は既存背景を明示再利用した2案で、対話から新しい背景を生成して完成品を独立採点する全工程の試験ではない。画像の表示も確認したが、美観の合格や実機印刷の保証へ読み替えていない。ユーザーの通常環境での永続導入・ログイン済み会話の全工程・全リポジトリCIは実施していない。

旧計画は4スキル・固定13案等を前提とし、現物の6スキル構成へ未追随。参照用タスクグラフは `dispatch_ready:false` で自動build用ではない。履歴を書き換えず、現行化を **harness-35yo** に記録した。

今回変更した3プラグインの採番検査は成功。一方、全体検査は対象外の `dev-graph 0.1.19` と `system-briefing-book 0.2.10` の内容と台帳の差分で失敗する。両者を自動採番せず **harness-59nn** に記録した。[release-fleet-check.log](release-fleet-check.log)

## 起動

本体で `npm ci --ignore-scripts` を実行済み。Claude Codeで一時的に使う場合:

```bash
claude --plugin-dir /Users/dm/dev/dev/個人開発/harness/plugins/flyer-studio
```

新しい会話の入口は `/flyer-studio:run-intake-flyer`。永続導入と単独キットの手順は [INSTALL.md](/Users/dm/dev/dev/個人開発/harness/plugins/flyer-studio/INSTALL.md)。

確認した外部仕様は [Claude Codeのmanifest仕様](https://code.claude.com/docs/en/plugins-reference) と [OpenAIのパッケージ仕様](https://developers.openai.com/plugins/build/plugins)。実際の受理は上記のローカルCLIと検出APIで確認した。コミット・push・外部公開は行っていない。
