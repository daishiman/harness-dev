# 改善要件メモ（Phase 3 improvement-executor の必須入力）

## 元の運用課題
初回利用で `/run-notion-gmail-dry-run` 実行時、repo-root に `.notion-config.json` が無く（plugin 内に `.notion-config.json.example` のみ）、config ローダーが ConfigError → exit 2 で停止。`.example` には本番実 DB ID + 送信元 `no-reply@shonai.inc` が焼き込まれている。完了チェックリスト先頭「dry-run で plan.json と APPROVE 文字列を得る」が未達。設定不在時の初期セットアップ/オンボーディング体験が破綻。

## ユーザーからの明示要件（2026-06-26 追記）
- **R-USER-1**: 設定（config）が必要であれば、その設定方法を **README に明記**しておくこと。設定が前提なら、何を・どこに・どの値で作るのかをドキュメントで迷わず辿れる状態にする。

## 親 context が事前検出した latent smell（Phase 2 で検証対象）
- **S1**: `.notion-config.json.example` に本番実 DB ID + 実送信元が焼き込まれている（git に載る example が本番固有値を持つ → 漏洩 / SSOT smell）。placeholder であるべきか、実値が必要なら出所と運用を明確化すべきか要検証。
- **S2**: `.gitignore` の negation `!.notion-config.example.json` が実ファイル名 `.notion-config.json.example` と不一致（保険が効いていない整合性 smell）。
- **S3**: config 不在エラーが受動的案内（「.example を参照」）にとどまり、その場で前進する scaffold/init 手段が無い（オンボーディングのデッドエンド）。

## 改善の制約
- 不可逆メール送信の安全設計（承認済み plan / 人間承認ゲート / 冪等ログ）を弱めないこと。fail-closed は維持。
- README の既存構成（TL;DR 5ステップ / セットアップ / 使い方 / 安全設計）と整合させること。
- 実 DB ID / 実送信元を新たに git 追跡ファイルへ拡散させないこと。
