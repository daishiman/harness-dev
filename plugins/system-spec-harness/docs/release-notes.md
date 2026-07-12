# system-spec-harness リリースノート (P13)

## バージョン 0.1.0 (初回 build)

13 component (skill×5 / sub-agent×3 / slash-command×2 / hook×1 / script×2) + envelope surface (manifest / EVALS / RUNBOOK / plugin-composition / CI additive wiring) を build。全 component が p0_lint (kind別) exit0・pytest 181 passed / coverage 98%・route-build-report×13 valid・`validate-plan-coverage --all` exit0 (計画↔実体 completeness)。

## リリース準備 soft note (PR/配布はゲート化しない)
- PR: feature branch から main への PR は soft note に留める (本 plugin の完了条件に PR merge を含めない)。
- marketplace 登録は distributable 承認後 (下記 GAP-DISTRIBUTION-DECISION)。
- `.claude/` symlink 反映 (`build-claude-symlinks.py` + `make sync`) を配布前に実施。

## ドメイン外 DROP 記録 (写像対象外)
本 plugin の purpose は「システム構築仕様のヒアリング収集と仕様書化」であり、以下は component 写像対象外として意図的に DROP:
- **IPC (プロセス間通信) の実装**: 仕様として章に記録する対象ではあるが、IPC 実装そのものは本 plugin の生成物でない (仕様書に書く内容であって plugin が作る機能ではない)。
- **Cloudflare 等 特定ベンダー連携**: インフラカテゴリのヒアリング項目として扱うが、特定 CDN/WAF ベンダー固有の実装は component 化しない (最新情報は C02 doc-fetch が公式ドキュメントとして取得)。
- **MCP / app connector 経由のドキュメント取得**: WebSearch/WebFetch で完結する方針のため今回は新設せず (`GAP-MCP-DOCFETCH` として保留)。

## 配布判断待ち (open_issues 引き継ぎ)
- **GAP-DISTRIBUTION-DECISION** (medium): marketplace 配布可否 (distributable) は未確定。利用単位 (個人利用か、チーム/複数プロジェクト共通の再利用資産か) の判断を含む。現状 `distributable: false` で計画・build。ユーザー承認後に `envelope-draft/plugin.json` と `index.plugin_meta.distribution` を `true` へ更新し、`.claude-plugin/marketplace.json` / `bundles.json` へ登録して配布フローへ進める。
- pkg 契約番号は配布判断確定後に割当 (`index.plugin_meta.pkg_contract.applicable: false`)。

## 残タスク (次サイクル候補)
- C11 hook と C03 章 frontmatter の粒度整合 (`spec_cells` list 解釈) — elegant review で是正 (下記参照)。
- 実運用での往復ヒアリング実走フィードバックに基づく質問バンク (C01 references) の拡充。
