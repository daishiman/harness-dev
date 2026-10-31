---
graph_node_id: "spec-guide-doc-visual"
artifact_kind: "specification"
artifact_subtypes: []
title: "資料の表現選定と可読性の仕様"
project_id: "guide-doc-generator"
domain: "documentation"
status: "draft"
priority: null
start_date: null
target_date: null
iteration: null
owners: ["harness-maintainers"]
tags: ["visual-expression", "mvp-review"]
file_path: "specs/guide-doc-visual.md"
template_id: "specification"
template_version: "1.0.0"
confirmation_status: "draft"
evaluation_status: "pending"
confirmation_evidence: {"evaluated_digest": null, "evaluator": null, "evidence_ref": null}
source_lineage: {"imported_at": null, "origin_kind": "manual", "source_digest": null, "source_path": null, "source_plugin": null, "source_version": null}
created_at: "2026-10-31T09:58:26.388836Z"
updated_at: "2026-10-31T09:58:26.388836Z"
depends_on: []
related_nodes: []
resource_scope: []
purpose: null
goal: null
scope_in: []
scope_out: []
acceptance: []
architecture_refs: []
parent_feature: null
feature_package_id: null
phase_ref: null
classification_confidence: 0.99
classification_reason: "既存資料生成プラグインの差分を目的別の正規成果物として記録する。"
classification_candidates: [{"artifact_kind": "specification", "candidate_path": "specs/guide-doc-visual.md", "confidence": 0.99}, {"artifact_kind": "document", "candidate_path": "docs/guide-doc-visual.md", "confidence": 0.01}]
tracker_binding: "none"
beads_linkage: null
github_publication: {"labels": [], "milestone": null, "mode": "local_only", "project_aliases": []}
issue_linkage: null
github_project_linkages: []
pull_request_linkages: []
execution_contexts: []
completion_evidence: {"completed_at": null, "evidence_refs": [], "policy": "manual", "reconciled_at": null, "source": null, "status": "not_applicable"}
implementation_readiness: {"checked_at": "2026-10-31T09:58:26.388836Z", "missing_sections": [], "status": "complete"}
---

# 目的と成功状態

説明の関係から図・表・カード・手順を選び、文字を縮めず読める単一HTMLを再現可能に生成する。図の枚数を目的化しない。

## スコープ

対象：guide-doc-generatorの選定、描画、逆抽出、素材連携、証跡配置。対象外：他プラグインの変更、外部サービス追加、HTMLのみからのメタデータ完全復元。

## 用語と主体

C05は内容と表現を選ぶ。C11はHTMLの単一writer。C14は構造データを検証してSVGを描く。C19は構成・素材・選定証跡を配置する。意味上の適合は独立レビューが判断する。

## ユースケースとユーザーフロー

1. 伝えたい問いと事実を整理する。
2. 複数の候補から図・HTML部品・文章を選ぶ。
3. 構成を正規化し、素材を埋め込んで生成する。
4. 静的ゲートと必要な実表示を確認する。

## 機能要件

- FR-1：選定ログは対象部品・原文・候補・保持事実を持つ。
- FR-2：関係・順序・時点・期間・数量などに合う表現を選ぶ。カタログ外は専用作図素材へ接続できる。
- FR-3：接続先欠落、孤立、線と箱の衝突などを入力エラーで拒否する。
- FR-4：表紙素材IDと構成を逆抽出し、証跡を構成ハッシュへ結び付ける。

## 非機能要件

SVGの説明文字は実表示14px以上を保つ。1440/768/375pxでページの横はみ出しを抑え、必要な表や図は内部で移動できる。色だけに意味を依存させない。同一構成・素材・実装でHTMLをバイト一致再生成する。

## UI・状態遷移

補足は閉じた状態から開ける。図はEnterで拡大し、Escapeで閉じて元のボタンへ戻る。実習は操作・成功の目安・救済を組にし、狭幅では縦に並ぶ。印刷前に詳細を開き、終了後に復元する。

## ビジネスルールと検証

図の種類の一覧は万能性の保証ではない。順序のない選択肢へ矢印を付けない。図と本文の重複を避ける。未生成・未確認を成功へ読み替えない。警告と未正規化を混同しない。

## API契約

N/A: ローカルCLIとHTML生成の改善であり、公開HTTP APIの追加・変更はない。

## データモデル

handout-config.schema.jsonのB17.data.titleは任意の短い実習見出し。diagramsのパターン語彙はconfig/handout-diagrams.jsonが正本。選定ログは正規構成の外に置き、config_sha256とtarget_part_idsで照合する。

## 認証・認可

N/A: 新しい認証主体や権限を追加しない。生成HTMLの外部取得禁止と既存の素材・出力先境界を維持する。

## エラー・例外・回復

不正な関係や古い選定ハッシュは停止して構成へ差し戻す。図が大きい場合は分割・内部スクロール・HTML部品へ選び直す。HTMLの手直しで検査を回避しない。

## イベント・非同期処理

ブラウザ内の開閉、拡大、印刷イベントのみ。外部キューやバックグラウンドサービスは追加しない。

## 可観測性

4静的ゲートの全行、実装と構成のハッシュ、未実施理由、選定証跡、実ビューポートを記録する。固定UIを含む縦長合成画像だけで遮蔽を断定しない。

## 互換性・移行・リリース

既存構成を維持し、実習見出しは任意追加。SVGの表示幅指定を優先し、viewBoxは補助にする。変更時はlocal release writerで対象プラグインだけ採番する。旧資料はバックアップを残して再生成する。

## テストと受入条件

- 図解、HTML描画、逆抽出、配置、素材連携と変更した説明契約の既存テストを実行する。
- 選定証跡の欠落・参照切れ・古いハッシュを拒否する。
- 同一入力の再生成、4静的ゲート、3幅の最小スモークを確認する。

## 未決事項

harness-ws7j：実資料をHTMLだけから逆抽出すると、画像計画・配列順・null等のメタデータ差分が残る。今回の再現単位は同梱JSONと素材である。

