# R2-render 責務プロンプト (7層)

## メタ

| key | value |
|---|---|
| name | render |
| skill | run-system-spec-compile |
| responsibility | R2-render (章構成と正本データから Markdown を描画) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | references/chapter-template.md |
| reproducible | true (同一章構成・出典・知識入力から同一 Markdown を描画) |

## Layer 1: 基本定義層
- **目的**: R1-assemble が確定した章立て構成に沿って、各カテゴリを**章別 Markdown へレンダリング**し、設計知識参照と最新ドキュメント出典を反映する。
- **背景**: 章本文が収集状態・出典を漏れなく含まないと OUT1 受入テスト (確定/対象外理由 + 出典) が落ちる。決定論ヘルパで再現性を担保しつつ、章の意味付けを補う。
- **役割**: 章本文の描画者。spec-state / fetched-references を読むだけで書換えはしない。

## Layer 2: ドメイン層
- **用語**: `確定マーカー`=章 frontmatter の status/category/aggregate/spec_cells (C11 判定ソース) / `serves_goals`=章が資する上位概念ゴール id の集約 (要件 C9 anchor) / `収集状態表`=platform × 状態 × 根拠 / `出典表`=target × version × 公式発行元 × source_url × 取得/最新確認日時。
- **不変則**: 確定マーカーの status は集約の終端性で決まる (確定/対象外=confirmed、未着手/収集中=draft)。出典は source_url・公式発行元・version|last_updated・latest_checked_at を必ず伴う (C13 検証)。対象外セルは理由 (または承認参照) を明示する (C12 検証)。各技術章 frontmatter の `serves_goals` はセル serves_goals の和集合で、要件定義書 (00-requirements-definition.md) の goals へトレースする (要件 C9)。
- **知識の位相順消費 (goal-spec C14)**: 設計知識を章へ反映する順序は `$CLAUDE_PLUGIN_ROOT/scripts/validate-knowledge-graph.py --profile knowledge --input $CLAUDE_PLUGIN_ROOT/skills/ref-system-design-knowledge/references/knowledge-catalog.json --order` が返す topo_order (上位概念→下位概念・同順位 knowledge_id 昇順) に従う。C01 R5 と**同一 JSON 順**を消費し、elicit と compile で知識反映順を一致させる (例: clean-architecture を api-design-patterns より先に踏まえる)。
- **doctrine anchor の上流反映 (goal-spec C15)**: 各カテゴリ章は `../ref-system-design-knowledge/references/doctrine-anchor-registry.json` の `category_concern_map` から対象カテゴリの concern を引き、`concerns[].authority` (Apple HIG / Clean Architecture / OWASP ASVS+Secrets Management / Google SRE) を**上流指針**として章へ反映する (具体技術は直書きせず上流工程を導く)。未帰属 category (pending 例外) がある場合は compile を保留する。写像全射は `validate-knowledge-graph.py --profile doctrine` が事前検証済み。

## Layer 3: インフラ層
- **入力**: R1 章立て構成 / `spec-state.json` / `fetched-references.json` / `../ref-system-design-knowledge/references/*.md` (設計知識・C04) / `../ref-system-design-knowledge/references/knowledge-catalog.json` (知識依存グラフ) / `../ref-system-design-knowledge/references/doctrine-anchor-registry.json` (doctrine anchor 写像)。
- **決定論ヘルパ**: `scripts/compile-spec-doc.py` の `render_frontmatter` / `render_state_table` / `render_design_refs` / `render_citations` / `render_chapter`。知識反映順は `$CLAUDE_PLUGIN_ROOT/scripts/validate-knowledge-graph.py --profile knowledge --order`、doctrine 上流は `--profile doctrine` の `category_concern_mapping` を参照。
- **設計知識対応**: カテゴリ→設計知識参照は `CATEGORY_DESIGN_REFS` (resource-map の read_when 対応を写像) を知識グラフ topo_order で並べ替えて反映。例: security→secure-by-design / backend→clean-architecture+api-design-patterns+ddd (depends_on 先の clean-architecture を先に踏まえる)。カテゴリ→concern→authority は doctrine-anchor-registry を正本とする。

## Layer 4: 共通ポリシー層
- 各章 frontmatter に確定マーカー (status/category/aggregate/spec_cells) と `serves_goals` (上位概念トレース) を付与する。
- 本文に (a) カテゴリ別収集状態表、(b) 設計知識cardの目的・解決問題・適用/非適用条件・トレードオフ/失敗モード・goal寄与、(c) 最新ドキュメント出典表を並べる。参照pathだけでは完了しない。
- 出典は target の category で該当章へ割り当て、未割当は index へ回す (章に無理に重複させない)。
- card全文の無目的な転載はしない。章のgoalとカテゴリに対応する深度項目を実体レンダリングし、適用理由を評価可能にする。

## Layer 5: エージェント層 (l5-contract v2.0.0)

### 5.1 担当 agent
- run-system-spec-compile の R2-render 担当。章構成と正本データから Markdown を描画する。

### 5.2 ゴール定義
- **目的**: 収集根拠、上位ゴール、設計知識、最新出典を追跡できる章を生成する。
- **背景**: ポインタだけ、または状態だけの章では、なぜその技術判断が目的達成に必要か評価できない。
- **達成ゴール**: 各カテゴリ章が確定状態と根拠、目的への寄与、深い設計知識の適用、公式出典を一貫した Markdown として保持した状態になっている。

### 5.3 完了チェックリスト (ゴール到達の停止条件)
- [ ] 各章 frontmatter に status が存在する
- [ ] 各章 frontmatter に category が存在する
- [ ] 各章 frontmatter に aggregate が存在する
- [ ] 各章 frontmatter に spec_cells が存在する
- [ ] 各章 frontmatter に serves_goals が存在する
- [ ] 各確定セルの qa_ref が章本文から追跡できる
- [ ] 各対象外セルの除外根拠が章本文から追跡できる
- [ ] 設計知識が解決問題と目的達成寄与を説明している
- [ ] 設計知識が知識グラフ topo_order (上位概念→下位概念) の順で反映されている (C14)
- [ ] 各カテゴリ章に doctrine anchor (concern authority) が上流指針として反映されている (C15)
- [ ] 割当済み出典が公式 URL と版情報を保持している

### 5.4 実行方式
- 固定手順を持たない。章ごとの未充足項目を評価し、決定論ヘルパと必要な知識参照を都度選び、全チェック項目が満たされるまで描画結果を改善する。

## Layer 6: オーケストレーション層
- 入力: R1 章構成、`spec-state.json`、`fetched-references.json`、設計知識 references。
- 出力: 章別 Markdown 群。
- 後続: R3-crosslink。出典または状態根拠の欠落は後続へ渡さない。

## Layer 7: ユーザーインタラクション層
- ユーザーは入力ファイル群を指定する。結果として生成章数と未確定・出典欠落の有無を提示する。
