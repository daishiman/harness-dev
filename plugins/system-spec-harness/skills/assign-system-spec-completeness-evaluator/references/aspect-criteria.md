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

> C06 (hearing-auditor) は `system-spec/*.md` を読まずヒアリング品質 (R6-audit-hearing の監査 5 軸) のみを監査するため、`design_knowledge_reflection` へ束縛するのは虚偽対応だった。C06 は `matrix_coverage` の sub-input (網羅性・トレースの補助根拠) へ再配置し、設計知識反映は C05 が `system-spec/*.md` と `resource-map.yaml` から自前評価する。

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
- **sub-input (C06 hearing-auditor)**: ヒアリング品質を網羅性・トレースの補助根拠として併せる。
  軸は C06 の SSOT `../../run-system-spec-elicit/prompts/R6-audit-hearing.md` の監査 5 軸
  (聞き漏れ / 誘導質問 / 早期停止 / トレーサビリティ / 上位概念の遡及性) で、本ファイルでは軸を数え直さない。
  C06 の検出が matrix_coverage をどう動かすかは、次節「ヒアリング監査 (C06) の重大度と判定の対応」
  だけが決める。C06 自身の verdict を観点の判定にそのまま使わない。
- **C16 必須情報カタログ被覆 (追加次元)**: `validate-knowledge-graph.py --profile required-info` の
  exit0 (全 in-scope domain 被覆・item 最低形状・収集順序・coverage certificate) を機械層根拠にする。
  `missing_effect=block` の item が未回答のまま確定 (confirmed) へ進んだ確定セルは C01 R5 収集ゲート
  素通り (機械層ゲート validate-knowledge-graph.py (component C14) は coverage certificate に blocking_items を列挙するのみで runtime 施行はせず、決定論 writer
  施行 = apply-spec-transition への block 検査組込は follow-up。収集すべき必須情報の欠落) として
  matrix_coverage を FAIL に寄せる。

### 1a. ヒアリング監査 (C06) の重大度と判定の対応 (正本)

C06 の各検出には R6 が重大度 (high / medium / low / info) を付ける。重大度の付け方は R6、
重大度から matrix_coverage の sub-input 判定への対応はこの表が**唯一の正本**である。
R1-score・R2-delegate・`scoring-rubric.json`・C06 の起動アダプタはこの表を参照し、書き写さない。
決定論の実装は `scripts/aggregate-completeness.py` の `derive_hearing_verdict`
(`--hearing <C06 出力> --state <spec-state.json>`) で、表と食い違ったら表を正とする。

| 検出の状態 | sub-input の扱い | 理由 |
|---|---|---|
| 誘導の検出 (軸 2) で、その問が有効に置き換え済み | **閉じた検出**。判定に数えず、報告に残す | 同じ論点を中立に問い直し、利用者の回答を取り直している。凍結された問は消せないので、閉じたことを記録で示す |
| high | **FAIL** | 網羅性かトレースの裏付けが崩れている |
| medium・誘導の検出 (軸 2) で、その問が確定セルの主たる接地根拠 (`qa_ref`) | **FAIL** | 確定の根拠そのものが誘導の疑いを持つ |
| medium・誘導の検出 (軸 2) で、その問が主たる接地根拠でない (裏付けの `qa_refs` だけ・対象外セルの `qa_ref`・未参照) | PASS に残す注記 | 確定の根拠は別の問にある。問の欠陥は記録に残す |
| medium・軸 2 以外 (聞き漏れ・早期停止・トレース・上位概念) | **FAIL** | 緩和は問に限る。セルや進捗の欠陥は根拠の有無そのものに関わる |
| low / info | PASS に残す注記 | 答えを左右したとは読めない偏り。報告から消さない |
| C06 が INDETERMINATE、または検出の形が不正 (未知の軸・重大度、対象の欠落、存在しない qa_id) | **INDETERMINATE** | 監査の再実行か入力の補完が要る。fail-closed で観点は FAIL に寄せる |

- **有効な置き換え**: 旧い qa に `superseded_by` があり、次を全て満たすもの。(a) 置き換え先の問が
  中立 — C06 が `supersession_valid: true` と判定し、かつ置き換え先に medium 以上の誘導の検出が無い。
  (b) 同じ論点 — 同じく C06 の `supersession_valid: true` が示す。(c) 利用者の回答 — 置き換え先に
  `answer`・`basis: user-decision`・`answered_at` が揃っている。加えて旧い問が確定セルの主たる接地根拠で
  ないこと。どれかを欠く置き換えは無効で、その検出は重大度どおりに扱う。基準の正本は
  `../../run-system-spec-elicit/references/neutral-question-criteria.md`。
- **PASS に残す注記**: C05 レポートの `findings[]` に、C06 の重大度のまま (medium / low / info)
  `bucket: matrix_coverage` で残す。`gaps` には入れない (差し戻しの対象ではない)。
  閉じた検出は `severity: info` で「閉じた検出 (置き換え先: <qa_id>)」と書く。
- 以前は C06 が「1 軸以上に検出があれば FAIL」とし、R1-score が「監査 verdict FAIL → 該当観点 FAIL」と
  していたため、low 1 件で matrix_coverage が FAIL になり総合判定も FAIL になった。また凍結された問の
  検出は問い直しても毎周同じ形で再発した。この表はその 2 つを解くために置いた。判定を緩めたのではなく、
  確定の根拠に効く検出 (high と、主たる接地根拠の問への medium) は従来どおり FAIL のままである。

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
  C06 は、上の対応表で INDETERMINATE になる場合 (検出の形の不正を含む) も同じ扱いにする。
- INDETERMINATE 観点は fail-closed で総合 FAIL に寄せ、不足事項一覧に「再実行が必要な観点」として記す。
  仕様書の修正ではなく監査の再実行/入力補完を促す差し戻しにする。
