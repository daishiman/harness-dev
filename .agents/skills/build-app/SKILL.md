---
name: build-app
description: 新しいWebアプリを要件整理から設計・実装・Cloudflare公開・品質確認まで一貫して構築する。Codexで「アプリを作って」「業務ツールを新規開発」「$build-app」と依頼されたときに使用する。
---

# Build app

1. `$build-app` と同じメッセージに書かれた内容をアプリ要件として扱う。
2. `$app-excellence` の成果物先行契約を適用する。要件が短くても質問で止めず、リポジトリ名、既存資料、データ、業務慣習から最有力仮説を選ぶ。
3. **catalog-default入口契約**: 描画されるWeb UIを持つ新規アプリは、カラー指定や「デザインして」という文言の有無にかかわらず `jp-web-design` の `references/catalog-default-contract.md` を適用対象として委譲する。API・バッチなど可視UIを一切作らない場合だけ `NON_VISUAL(理由)` を渡す。適用・証跡・検査の詳細は同契約だけを正本とし、この入口へ複製しない。
4. **Cloudflare MCP の user scope 登録と wrangler 実行はエージェントが代行する。OAuth 認証と git 管理外の `.mcp.json` だけ本人が行う**(INV-11)。`codex mcp get <name> --json` で `docs` / `bindings` / `observability` を確認し、未登録・不通・明示的な legacy `type:sse` だけを `codex mcp remove <name>` の後 `codex mcp add <name> --url https://<name の製品名>.mcp.cloudflare.com/mcp` で登録し直す。`/mcp`を推奨するが、`/sse` URLがStreamable HTTP互換aliasとして動作しているだけなら移行しない。現在の要件がbindings変更またはobservability調査を必要とし、その対象が認証待ちのときだけ、利用者本人へ対象1件のブラウザ認可(`codex mcp login <name>`)を1行で依頼する。未使用MCPの認証は求めず、承認を待たずに次へ進む。
5. `app_orchestrator` カスタムエージェントへ、**成果物先行・事前質問ゼロ**で要件とcatalog-default判定を委譲し、完了まで待つ。カスタムエージェントを利用できないクライアントでは、現在のスレッドで `$app-orchestrator` を使用して同じ手順を完遂する。
6. 最初の返却物は空欄の質問票ではなく、仮説入りT1/T2、最頻業務を通すWalking Skeleton、操作可能な代表画面のいずれかにする。本人しか決められない秘密・課金・公開・破壊操作があっても、ローカル成果物またはdry-runまでは先に作る。
7. 最終報告の先頭に、公開したURLと現在の段階（v0=関係者向け / v1=本番）、試してほしい操作、今できないこと（残課題）を書く。その後に採用案の根拠、実施テスト、品質監査結果を記載する。可視UIを含む場合はcatalog-defaultの段階別判定結果だけを1行添える。非エンジニアが一度で理解できる言葉を使う。
