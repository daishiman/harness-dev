---
name: improve-app
description: 既存Webアプリへ機能追加・UX改善・不具合修正を1件ずつ安全に実装して公開する。Codexで「既存アプリを改善」「機能を追加」「$improve-app」と依頼されたときに使用する。
---

# Improve app

1. `$improve-app` と同じメッセージに書かれた内容を今回の改善依頼として扱う。
2. 依頼が短い場合は `docs/product/backlog.md`、Issue、利用ログ、未完フロー、テスト失敗を読み、影響度・頻度・依存・リスクから**最有力の1件**を選ぶ。候補一覧を返して選択待ちにしない。
3. 複数要望は内部で分割・採点し、今回進める縦切り1件を確定する。残りは理由つきで残課題へ置く。
4. **catalog-default入口契約**: 依頼文の「デザイン」「見づらい」等の語ではなく、実際の変更予定で判定する。DOM/JSX/HTML、描画component、通常の新画面追加、layout、style/token、利用者が操作するinteractionのいずれかを作る・変えるなら `jp-web-design` の `references/catalog-default-contract.md` を適用対象として委譲する。可視UIへ一切触れない場合だけ `NON_VISUAL(理由)` を渡す。適用・証跡・検査の詳細は同契約だけを正本とする。
5. **Cloudflare MCP の user scope 登録と wrangler 実行はエージェントが代行する。OAuth 認証と git 管理外の `.mcp.json` だけ本人が行う**(INV-11)。`codex mcp get <name> --json` で `docs` / `bindings` / `observability` を確認し、未登録・不通・明示的な legacy `type:sse` なら `codex mcp remove <name>` の後 `codex mcp add <name> --url https://<name の製品名>.mcp.cloudflare.com/mcp` を自分で実行する。`/mcp`を推奨するが、`/sse` URLがStreamable HTTP互換aliasとして動作する場合はそれだけで移行しない。legacy SSE GETが410になる`type:sse`だけを移行対象とする。既存アプリでは登録が後から壊れていることがあり、ここで見ないと誰も直さない。今回の改善がbindings変更またはobservability調査を必要とし、その対象が認証待ちのときだけ、対象1件のブラウザ認可(`codex mcp login <name>`)を依頼する。未使用MCPの認証は求めず、承認を待たずに次へ進む。
6. **成熟度を複数の信号で判定する**。まず `git fetch --tags --prune` を試み(オフライン・権限不足で失敗しても判定を続ける)、次を読む。
   - release tag: exact `v1`、`v1.*`、またはそれ以降の明示的release tag
   - project marker: T4 の v1 Go・受入確認、またはプロジェクトの正本にある明示的な `stage: v1+` / 本番稼働マーカー(READMEの宣伝文は根拠にしない)
   - 安全運用信号: デプロイ用workflowまたはWorkers Builds、production Environment、default branch保護、PR運用のいずれか
7. exact `v1` / `v1.*` / 以降のrelease tag、または明示的な v1+ project marker があれば `app_orchestrator` へ「追加開発モード・成果物先行」で委譲する。**main 直反映を許すのは、新規AIDDプロジェクトで、T2/T4等の正本が pre-v1/v0 を明示し、上記の安全運用信号と矛盾しない場合だけ**。その場合は「v0→v1 の育てるループとしてステージ3-B・6、main 直反映」と委譲する。既存repoで判定に確信がない、fetchできない、または信号が矛盾する場合は**安全側のブランチ + PR**とし、main に直接反映しない。いずれもcatalog-default判定を含めて渡し、完了まで待つ。利用できないクライアントでは現在のスレッドで `$app-orchestrator` を使用して完遂する。
8. **v1+または判定不確実ならブランチ作成からpreview/PRまで、明確な新規pre-v1 AIDDだけ main 直反映とpreviewまで**自律的に進め、依頼者には成果物への差分を求める。公開・マージなど権限境界は既存の承認規律を守る。
9. 最終報告は、今回できるようになったこと、試してほしい操作、採用理由、更新後の残課題、次に自動選定した候補の順で書く。可視UIを変更した場合はcatalog-default判定結果だけを1行添える。git用語は使わず、`app-orchestrator` の語彙対応表に従う。
