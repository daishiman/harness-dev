# 章別 Markdown 構造テンプレート

`scripts/compile-spec-doc.py` が各カテゴリ章 (`system-spec/<category>.md`) を生成する際の決定論構造。
下記は形状の説明であり、実体は compile-spec-doc.py の `render_chapter` が生成する。

**正本関係**: 章の**構造** (節の順序・frontmatter キー・各節が何を載せるか) の正本は本ファイル。その構造を**生成する実装**の正本は `scripts/compile-spec-doc.py` の `render_chapter`、受入は `../fixtures/expected-*.md` (`tests/` の下ではなく skill root 直下)。実装を変えたら本ファイルと golden を同じ commit で追随させる (実装だけ進んで説明が取り残されると、本ファイルを読んで書いた章が実体と食い違う)。

## frontmatter (確定マーカー・C11 hook 判定ソース)

```
---
status: confirmed        # 終端カテゴリ (集約=確定/対象外) は confirmed / 進行中 (未着手/収集中) は draft
category: <category-id>  # 章のカテゴリ id (例: database)
aggregate: 確定          # 真理値表導出の集約状態 (未着手/収集中/確定/対象外)
spec_cells: [<category>.web, <category>.mobile, <category>.tablet, <category>.desktop-windows, <category>.desktop-linux, <category>.desktop-macos]
serves_goals: [G1, G2]   # 確定セルの serves_goals の和集合 (canonical platform 順・初出順)
---
```

- `status`: 集約が終端 (確定/対象外) のとき `confirmed`、進行中 (未着手/収集中) のとき `draft`。
- `aggregate`: セル状態から真理値表で再導出 (`category_aggregate` 宣言値を鵜呑みにしない)。
- `spec_cells`: 章が対応する `<category>.<platform>` セル id 一覧 (canonical platform 順)。
- `serves_goals`: 章が資する上位概念 (要件定義書 U3 ゴール) の id 一覧。各セルの `serves_goals` から導出し、空なら `[]`。

## 本文セクション

節順は「状態 → 上流指針 → 確定内容 → 規範 (To-Be/Delta) → 参考 (設計知識) → 出典」。

順序厳守。**承認節 (3) を除く全節を常に出力する** (入力の有無で節を落とさない)。該当データが無い節は見出しを残したまま不在を明示する placeholder を置く (例: 確定セルが 0 件の章でも `## 確定内容 (質疑録)` を出し、`- (確定セルなし。全セルが対象外または未収集であり、確定内容を持たない)` を置く)。空節を落とすと「確定セルが 0 件である」事実が章から消え、未確定が不可視になる — fail-visible を優先する設計であり、受入は `../fixtures/expected-maintenance-ops.md` (確定セル 0 件) が固定している。承認節だけは、状態表が「承認: <id>」としか言えない (承認参照を引く対象外セルがある) ときに置く。

1. **見出し + 集約サマリ**: `# <label> (<category>)` と集約状態・確定マーカー。
2. **カテゴリ別収集状態** 表: 各 canonical platform の状態 (未収集 / 対象外+理由 / 確定+qa_ref・qa_refs・資するゴール)。

   | プラットフォーム | 状態 | 根拠 |
   |---|---|---|
   | Web (web) | 確定 | 確定質疑: qa-database。資するゴール: G1 |
   | ... | 対象外 | 理由: <除外理由> |

3. **対象外の承認範囲**: 対象外セルが承認 (`approval_ref`) を引いているときだけ置く。承認 note と、その承認を名指ししている質疑。
4. **上流指針 (doctrine anchors)**: doctrine registry から引く category → concern → authority と、spec-state の `doctrine_applications` にある章固有の適用 (未記入なら「未記入」)。
5. **確定内容 (質疑録)**: 確定セルごとの主たる接地根拠 (`qa_ref`) と裏付け質疑 (`qa_refs`) の問・答 (逐語)。
6. **To-Be / Delta**: 到達すべき状態 (To-Be)・受入条件 (Delta の判定点)・本章がかなえる具体的やりたいこと (U9)・本章に効く確定意思決定。章の規範。
7. **適用された設計知識**: カテゴリに割り当てた `ref-system-design-knowledge/references/*.md` の card と、本章での適用 (非規範の参考資料)。並びは `### 本章での適用` → card 群 (知識グラフ topo_order・C14) → project candidate → `---` → `### 確定判断ごとの原則採否`。card 本文は共有資産の逐語なので、最後の節で `qa_log[].design_applications` の原則・`applied|not_applicable`・章固有理由・trade-off を確定 `qa_ref`・対応セル・`serves_goals` へ束縛して描く。記録が無い旧 state は記録経路 `unrecorded` を明示し、compiler が定型の「適用済み」文で補完しない。確定セルが無い章は適用先が未確定であることを明示する。
8. **最新ドキュメント出典** 表: 割り当てた fetched-references (対象 / version / 公式発行元 (host) / source_url / 取得 / 最新確認)。target の category (主たる章) に加え、`also_categories` で宣言した章にも同じ出典を載せる。未割当は index.md の全体出典へ。

逐語 (問・答・承認 note・ゴールなど) の描き方は SKILL.md の Key Rules 6 に従う。

## canonical platform 順序 (厳守)

`web, mobile, tablet, desktop-windows, desktop-linux, desktop-macos`
