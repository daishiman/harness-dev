# system-spec-harness リリースノート (P13)

## バージョン 0.1.0 (初回 build)

14 component (skill×5 / sub-agent×3 / slash-command×2 / hook×1 / script×3) + envelope surface (manifest / EVALS / RUNBOOK / plugin-composition / CI additive wiring) を build。全 component が p0_lint (kind別) exit0・pytest 375 passed・route-build-report×14 valid。知識グラフ追加サイクルでは `validate-knowledge-graph.py` の knowledge / required-info / doctrine / cross 4 profile が exit0。

## リリース準備 soft note (PR/配布はゲート化しない)
- PR: feature branch から main への PR は soft note に留める (本 plugin の完了条件に PR merge を含めない)。
- marketplace 登録と `harness-full` bundle 配線は distributable 承認済みの現行 manifest に反映済み。
- `.claude/` symlink 反映 (`build-claude-symlinks.py` + `make sync`) を配布前に実施。

## ドメイン外 DROP 記録 (写像対象外)
本 plugin の purpose は「システム構築仕様のヒアリング収集と仕様書化」であり、以下は component 写像対象外として意図的に DROP:
- **IPC (プロセス間通信) の実装**: 仕様として章に記録する対象ではあるが、IPC 実装そのものは本 plugin の生成物でない (仕様書に書く内容であって plugin が作る機能ではない)。
- **Cloudflare 等 特定ベンダー連携**: インフラカテゴリのヒアリング項目として扱うが、特定 CDN/WAF ベンダー固有の実装は component 化しない (最新情報は C02 doc-fetch が公式ドキュメントとして取得)。
- **MCP / app connector 経由のドキュメント取得**: WebSearch/WebFetch で完結する方針のため今回は新設せず (`GAP-MCP-DOCFETCH` として保留)。

## 配布状態
- **GAP-DISTRIBUTION-DECISION は解消済み**: 現行 manifest は `distributable: true` で、marketplace と `harness-full` bundle に登録済み。
- package 契約は `validate-plugin-packages.py` で blocking finding なしを確認する。

## 残タスク (次サイクル候補)
- 実運用での往復ヒアリング実走フィードバックに基づく質問バンク (C01 references) の拡充。
- task-graph の checklist ownership 射影を component owner 単位へ再設計し、covered task を再生成する。
- C16 required-info の `missing_effect=block` を単一 writer で決定論施行し、coverage certificate を spec-state に保存する。
