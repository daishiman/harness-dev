# 完成度評価の採点基準 (人間向け詳細)

機械判定ルールの正本は `scoring-rubric.json`。本ファイルはその意味判定の補助基準。
各観点は独立 context で fork する監査 sub-agent に接地し、評価者自身は仕様書を書き換えない
(修正は elicit/doc-fetch/compile へ差し戻す = Goodhart 防止)。

## 観点↔評価主体 対応表

| 観点 (aspect id) | ラベル | 評価主体 (component) | 主入力 | 決定論ゲート |
|---|---|---|---|---|
| `foundation_trace` | 上位概念trace | C05 R1-score | `requirements_foundation` / 00要件定義章 | `validate-coverage-matrix.py --require-foundation` |
| `decision_guidance` | 意思決定支援 | C05 R1-score | `decisions[]` / 00要件定義章 | 同上 |
| `matrix_coverage` | マトリクス網羅性 | `system-spec-matrix-auditor` (C07) + sub-input `system-spec-hearing-auditor` (C06) | `spec-state.json` | `validate-coverage-matrix.py` |
| `design_knowledge_reflection` | 設計知識反映 | C05 R1-score が自前評価 (**独立 auditor なし**) | `system-spec/*.md` / `resource-map.yaml` | (機械層=ポインタ存在 / 意味層=原則の具体適用) |
| `doc_freshness` | 最新ドキュメント出典 | `system-spec-doc-freshness-auditor` (C08) | `fetched-references.json` | `validate-source-citation.py` (C08 内実行) |
| `prompt_quality` | prompt-creator準拠 | C05 R1-score | 全`prompts/*.md` | `verify-completeness.py` + `validate-prompt.py` |

> C06 (hearing-auditor) は `system-spec/*.md` を読まずヒアリング品質 (聞き漏れ/誘導/早期停止/トレーサビリティ) のみを監査するため、`design_knowledge_reflection` へ束縛するのは虚偽対応だった。C06 は `matrix_coverage` の sub-input (網羅性・トレースの補助根拠) へ再配置し、設計知識反映は C05 が `system-spec/*.md` と `resource-map.yaml` から自前評価する。

## 観点別の合否判定

### 0. 上位概念trace / 意思決定支援
- U1-U9は値または理由付きN/Aで確定し、goal-objective-intent-cell-chapter参照にdanglingがない。
- decisionは2〜3案、無料/低コスト案、goal fit/TCO/security/operations/lock-in、最新公式証拠、推奨理由・注意点を持つ。AI推奨だけでconfirmedにしない。

### 1. マトリクス網羅性 (matrix_coverage / C07 + C06 sub-input)
- 決定論ゲート `validate-coverage-matrix.py --require-complete` の exit0 を一次根拠にする。
- 未収集セルの残存・対象外理由の placeholder・確定 qa_ref の dangling・集約真理値表の不一致・
  canonical platform 行の欠落を FAIL 要因として拾う。
- スクリプトが通っても、matrix-auditor の意味層 (対象外理由の具体性・qa_ref が確定を裏付けるか) が
  FAIL を出せば観点 FAIL。
- **sub-input (C06 hearing-auditor)**: ヒアリング品質の 4 軸 (聞き漏れ / 誘導質問 / 早期停止 /
  トレーサビリティ) を網羅性・トレースの補助根拠として併せる。設計判断が誘導なく漏れなく引き出され、
  確定セルが Q&A に遡れることを確認する。ヒアリングが不健全なら網羅性の裏付けが崩れるため
  matrix_coverage を FAIL に寄せうる。
- **C16 必須情報カタログ被覆 (追加次元)**: `validate-knowledge-graph.py --profile required-info` の
  exit0 (全 in-scope domain 被覆・item 最低形状・収集順序・coverage certificate) を機械層根拠にする。
  `missing_effect=block` の item が未回答のまま確定 (confirmed) へ進んだ確定セルは C01 R5 収集ゲート
  素通り (機械層ゲート validate-knowledge-graph.py (component C14) は coverage certificate に blocking_items を列挙するのみで runtime 施行はせず、決定論 writer
  施行 = apply-spec-transition への block 検査組込は follow-up。収集すべき必須情報の欠落) として
  matrix_coverage を FAIL に寄せる。

### 2. 設計知識反映 (design_knowledge_reflection / C05 自前評価・独立 auditor なし)
- 本観点は独立 auditor を立てず C05 R1-score が `system-spec/*.md` と `resource-map.yaml` を直接読んで評価する
  (C06 は設計知識を読まないため束縛しない = 虚偽対応の撤去)。
- **機械層**: コンパイル済み各章が `ref-system-design-knowledge` 由来の設計知識ポインタ節
  (クリーンアーキテクチャ / デザインパターン / API デザイン / セキュアバイデザイン / DDD /
  クリーンコード) を持つ (compile の `render_design_refs` が resource-map から注入)。
- **意味層**: そのポインタが指す原則が当該カテゴリの確定セル要件へ具体的に適用されているかを照合する。
- **Goodhart 防止**: ポインタは compile が機械注入するため、その存在確認だけで PASS にしない
  (機械注入→存在確認の自己循環を禁じる)。具体原則の適用が無く汎用ポインタ (resource-map 索引) だけの章、
  反映が形骸化している章は medium 以上で拾う。
- **C13 知識グラフ (追加次元)**: `validate-knowledge-graph.py --profile knowledge` の exit0 を機械層根拠に
  する (knowledge-catalog が typed 辺グラフで循環/dangling/孤立/root到達不能 0、depends_on/refines/
  conflicts_with の型則充足)。孤立 node が設計知識へ接地していなければ意味層で拾う。この機械層が保証するのは
  well-formedness (形状・辺型則・写像全射) と位相順の決定性のみで、知識辺の意味妥当性 (依存関係が設計上
  正しいか) は content-review/human の未閉塞責務。
- **C14 位相順消費 (追加次元)**: `--profile knowledge --order` が返す topo_order を C01 (R5-decision-guide)
  と C03 (R2) が同一順 (上位概念→下位概念) で消費していることを確認する。位相順を破って下位技術を先に
  確定した章を FAIL に寄せる。
- **C15 doctrine anchor (追加次元)**: `validate-knowledge-graph.py --profile doctrine` の exit0
  (7 concern の concern_id 一意 + 各 authority 非空・全 category→concern 写像全射。authority は 4 種で
  concern 間共有可・authority 一意性は非検査) を機械層根拠にする。意味層は
  `doctrine-anchor-registry.json` の concern authority (Apple HIG=presentation / Clean Architecture=
  application-architecture・data-access / OWASP ASVS+Secrets Management=authentication・security /
  Google SRE=reliability・operations) が指す上流指針が生成章の確定セル要件へ具体反映されているかを
  照合する。設計知識反映と同じ Goodhart 防止で、registry の存在確認だけでは PASS にしない。

### 3. 最新ドキュメント出典 (doc_freshness / C08)
- doc-freshness-auditor の二層 (形式=`validate-source-citation.py` / 内容鮮度=公式サイト再照合) を
  一次根拠にする。
- C13 (形式) が通っても、非公式 host・世代落ち version・実効性を欠く latest_checked_at は
  内容鮮度層で FAIL にする。到達不能 target は「鮮度未確認」として surface し PASS と誤認しない。

### 4. prompt品質
- 全promptでprompt-creatorの機械validatorがPASSし、L5は成果状態・原子的停止条件・動的実行方式を持つ。
- 独立C1-C4評価でLayer役割、L7→L1、再現性、Self-Evaluationを意味層でも確認する。

## 総合判定 (fail-closed)
- 全観点PASSかつhigh severity finding 0件のときだけ総合PASS。
- 1 観点でも FAIL/INDETERMINATE、または high finding が 1 件でもあれば総合 FAIL。
- scoring-rubricの全観点を過不足なく評価していなければ総合FAIL。
- 総合判定は `aggregate-completeness.aggregate_verdict` で再導出でき、レポートの `verdict` と
  一致すること (総合判定が観点スコアに接地しているかの整合検査)。

## INDETERMINATE の扱い
- 監査 sub-agent は入力欠落・破損・公式サイト到達不能で `INDETERMINATE` を返しうる。
- INDETERMINATE 観点は fail-closed で総合 FAIL に寄せ、不足事項一覧に「再実行が必要な観点」として記す。
  仕様書の修正ではなく監査の再実行/入力補完を促す差し戻しにする。
