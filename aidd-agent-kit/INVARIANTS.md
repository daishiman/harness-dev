# INVARIANTS — どんな縮小でも消してはならない規則

キットを削減・再配置するときの「必要」の集合。各 INV の本文は右の正本1箇所にだけ置き、他のファイルは INV-id で参照する(本文を複製しない)。削減 PR は「参照元から INV-id が消えていない」ことを確認してからマージする(`verify-codex-layout.sh` が正本ファイルに各 INV-id が在ることを機械検査する)。

| id | 規則 | 正本 |
|---|---|---|
| INV-1 | 秘密情報は `wrangler secret put` のみ。コード・vars・git に平文を置かない(`.dev.vars` は gitignore) | `skills/mvp-first-development/SKILL.md` §4-2 / `skills/cloudflare-secure-deploy/SKILL.md` §5 |
| INV-2 | deploy / secret put / d1 migrations apply は wrangler CLI 既定(MCP に能力があっても)。読み取り・調査は MCP | `skills/wrangler/references/mcp-vs-cli-routing.md` |
| INV-3 | v0 は CRITICAL ゼロ、v1 は CRITICAL ゼロ + 悪用可能な HIGH ゼロ。例外は T4 に責任者・受容理由・補償統制・解消期限を書いたリスク受容だけ。ダークパターン該当は CRITICAL | `skills/launch-security/SKILL.md` 段階別判定 |
| INV-4 | 認証方式は `better-auth-google-gate` §0 の単一決定表で決め、この表を経ずに公開しない | `skills/better-auth-google-gate/SKILL.md` §0 |
| INV-5 | リリース可否の判定は3つだけ(mvp-first §4 の必須4項目 / launch-security の段階別ゲート / その公開段階のゲート)。それ以外の理由で止めない | `agents/app-orchestrator.md` 裁定ルール1 |
| INV-6 | main にマージした版だけをデプロイし、デプロイ後にタグ。取り消しは `git revert` のみ(`reset --hard` / force push 禁止) | `agents/app-orchestrator.md` 絶対原則6 / `skills/solo-git-flow/SKILL.md` §7 |
| INV-7 | 本番 DB のスキーマ変更前に `wrangler d1 export`。適用順は migration → deploy。適用済み migration は書き換えない | `skills/mvp-first-development/SKILL.md` §4-4, §7-4 / `skills/ci-cd-pipeline/SKILL.md` §2 |
| INV-8 | N3 ゲート(何を1件と数えるか / 型と単位 / 誰のデータか)を書き終えるまでテーブルを作らない | `agents/app-orchestrator.md` ステージ3-A |
| INV-9 | mvp-first §4 の必須4項目(遮断 / 秘密をコードに書かない / 削除に確認 / スキーマ変更前バックアップ)は v0・v1 とも省略不可 | `skills/mvp-first-development/SKILL.md` §4 |
| INV-10 | Cloudflare Account を最初に固定し、判別不能・不一致なら作成・secret 更新・deploy を停止 | `skills/cloudflare-secure-deploy/SKILL.md` §0, §10 |
| INV-11 | Cloudflare MCP の user scope 登録と wrangler 実行はエージェントが代行する。OAuth 認証と git 管理外の `.mcp.json` だけ本人が行う | `skills/wrangler/references/mcp-vs-cli-routing.md` 裁定(5行) 3・4 |
| INV-12 | 依頼者に見せる確認とデプロイ前確認は `pnpm run preview`(Workers ランタイム)。`pnpm dev` で「動いた」と判断しない | `agents/app-orchestrator.md` 絶対原則5 / `skills/mvp-first-development/SKILL.md` §5 |
| INV-13 | 破壊操作(D1/R2 削除・DROP TABLE・本番 UPDATE/DELETE)・課金拡大・ドメイン変更は利用者確認なしに実行しない | `skills/cloudflare-secure-deploy/SKILL.md` §10 |
| INV-14 | インストーラは上書き前に backup、失敗時は manifest 単位で rollback、stale 削除は旧 manifest との差分だけ、HOME 外へ書かない | `install-mac.command` / `install-windows.bat` |
| INV-15 | UI の配色は平賀カラー(`hiraga-color-system.css` の役割トークン)を唯一の既定とし、ライトのみ。Pop は利用者の明示指定時だけ。既存アプリの旧配色は色だけ移行する | `skills/jp-web-design/references/hiraga-color-system.md` §0 |
