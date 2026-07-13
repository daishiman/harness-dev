# source-inventory — slide-report-generator-v2 (責務再均衡・非回帰被覆 SSOT)

> 本ファイルは v2 (責務再均衡) 計画の **非回帰完全性 SSOT**。v1 (`plugins/slide-report-generator/`・commit 7afede4・build 済 golden 源) の**全資産を1つ残らず** v2 の disposition (温存 / 薄化 / 昇格 / 新設) へ対応づけ、各資産の**非回帰検査法**を明示する。「機能を変えず責務再均衡する」主張は §5 被覆チェックリストで **抜け漏れ 0 (回帰 0)** を照合して初めて成立する。
> 正本関係: 数量・disposition の機械 SSOT は `component-inventory.json`。本ファイルはその**被覆の網羅性(collectively exhaustive)**を人間可読 + 機械照合可能な台帳で保証する層であり、build_target/依存 DAG を再記述しない (正規化)。
> 比較源: v1 tree = commit 7afede4 固定。vendor byte 正本 = `plugin-plans/slide-report-generator/vendor-digest-manifest.json` (195 files sha256 pin)。live tree ではなく manifest / commit SHA を比較基準とする。

---

## 0. 責務再均衡の不変原則

1. **機能非追加**: v2 は機能を1つも追加・削減しない。手続き知識・HTML/CSS 規範・評価 rubric の**置き場所**を repo 配置原則 (references=SSOT 正本・agents=薄いアダプタ) に沿って是正するのみ。
2. **vendor / schemas 不可侵 (goal-spec C7)**: Node engine (byte 維持) と意匠/技術コア SSOT (schemas) は変更対象外。再設計対象は agent⇔skill 間の情報配置境界のみ。
3. **v1 非破壊**: v1 は削除・改変しない。byte コピー元テンプレート兼比較 golden 源として read-only 温存する。
4. **非回帰の被覆単位**: skill 単位 OUT1 (golden diff) と agent 単位 golden fixture の 2 粒度だけでなく、**v1 の機能全域 (mode×reportType×生成/修正/横断×vendor script 経路)** を §5 で列挙し各々に検査法を対応づける (代表サンプルへの縮退を防ぐ)。

---

## 1. v1 全資産の全数 (実測) と v2 での扱い

| 種別 | v1 数 | v2 disposition | 非回帰検査法 |
|---|---|---|---|
| sub-agent (`agents/*.md`) | 16 | maintain 5 + thin-adapter 11 (§2) | maintain=byte-identical / thin-adapter=per-agent golden fixture (diff=0) |
| skill (`skills/*`) | 3 | progressive disclosure 化 (§3) | 各 skill OUT1 (golden diff) + criteria-test |
| slash-command (`commands/*.md`) | 2 | 温存 (C21/C22・名称不変) | 機能不変・manifest entry 一致 |
| hook (`hooks/*`) | 1 | 温存 (C20・mode-aware) | 機能不変・PostToolUse 配線一致 |
| plugin-root script | 1 (validate-output-mode.py=C23) | 温存 + 新設 1 (C24) | C23=不変 / C24=新設 (tests_min≥80) |
| references (content `references/*.md`) | 直下46 (=既存42[resource-map.md 含む] + report4) + feedback/5 | 直下 content 45 (既存41 + report4) + feedback/5 = 50 温存 + 新設 11 昇格 = 61 (§4) | 既存 50=byte-identical / 新設 11=thin-adapter 本文からの抽出・C24 帰属検証 |
| 帰属メタ | resource-map.md ×1 (散文) | resource-map.yaml ×1 (構造化) へ置換 | C24 (lint-reference-attribution.py) が機械検証 |
| Node scripts (`vendor/.../*.js/.cjs`) | 30 (+ report 新規 render-report.js/mermaid-render.js) | vendor whole-tree byte 温存 (無変更・C7) | lint-vendor-parity.py が manifest と byte 一致検査 |
| HTML templates (`vendor/.../templates/`) | 118 | vendor whole-tree byte 温存 (無変更・C7) | 同上 (whole-tree copy が網羅保証) |
| schemas (真 schema5 + fixture3) | 8 | vendor schemas-fixtures 温存 (無変更・C7) | S-SCHEMAS checks (P02-P10 無変更確認) |
| assets / style-genome / d3-components / pagination / print-styles | 多数 | vendor whole-tree byte 温存 (無変更・C7) | lint-vendor-parity.py |

> v1 の references 直下件数の正本: v1 source-inventory §1.1 は「直下46本 = 既存42 (resource-map.md=item23 を含む) + report 新規4」。v2 は resource-map.md を content 外の帰属メタへ再分類するため、v2 content 直下 = 46 − 1(resource-map.md) = **45** = 既存41 + report4。この換算は §6 の勘定表を正本とする。

---

## 2. 16 sub-agent の disposition 写像 (機械 SSOT=component-inventory.json)

> disposition の第一判定は行数でなく (a) 抽出可能な汎用塊の存在 + (b) consumers[]≥2 の単一 SSOT 成立。実測行数 (measured_at=2026-07-05 09:31 JST) は起点シグナル。**非回帰検査法**を各件に明示する (本台帳の主眼)。

### maintain 5 (薄化しない=v1 と本文不変)

| id | agent | 非回帰検査法 |
|---|---|---|
| C04 | hearing-facilitator | v1 から byte-identical コピー (再生成する場合は golden fixture diff=0) |
| C06 | structure-validator | 同上 |
| C10 | slide-renderer | 同上 |
| C18 | visual-strategist | 同上 |
| C19 | report-composer | 同上 |

### thin-adapter 11 (本文薄化 + 手続き知識を plugin-root references/ へ昇格)

| id | agent | 抽出先 reference (delegation) | 非回帰検査法 |
|---|---|---|---|
| C05 | structure-designer | structure-design-rules.md | per-agent golden fixture (薄化前後で生成物 diff=0) + C24 帰属 |
| C07 | d3-diagram-designer | d3-diagram-rules.md | 同上 |
| C08 | data-visualizer | data-visualization-rules.md | 同上 |
| C09 | html-generator | html-generation-rules.md | **pilot** (先行薄化・golden PASS を残10の前提) + C24 |
| C11 | layout-optimizer | layout-optimization-rules.md | per-agent golden fixture + C24 |
| C12 | ui-quality-reviewer | ui-quality-checklist.md | 同上 |
| C13 | deck-evaluator | deck-evaluation-rubric.md (C20 hook も実消費=真の consumers≥2) | 同上 |
| C14 | ai-image-diagram-producer | ai-image-pipeline.md | 同上 |
| C15 | slide-report-modifier | modification-rules.md | 同上 |
| C16 | cross-deck-reviewer | cross-deck-consistency-rules.md | 同上 |
| C17 | report-structure-designer | report-structure-types.md | 同上 |

---

## 3. 3 skill の progressive disclosure (機能非回帰=OUT1)

| id | skill | 非回帰 (OUT1) | 移行 |
|---|---|---|---|
| C01 | run-slide-report-generate | 代表 slide/report の golden diff PASS | SKILL.md→plugin-root references/ ポインタ・references_new 9件 |
| C02 | run-slide-report-modify | 修正フロー代表出力の golden diff PASS | references_new 1件 (modification-rules.md) |
| C03 | run-cross-deck-review | 横断検証 (3並列×4条件) 代表出力の golden diff PASS | references_new 1件 (cross-deck-consistency-rules.md) |

> C02/C03 の代表出力も golden-pin 集合へ含める (11 thin-adapter 限定の fixture では skill 機能面が被覆されないため・§5 参照)。

---

## 4. references 帰属 (D2 一本化: plugin-root references/ 一層)

- **既存 50 温存** (byte-identical): 直下 content 45 (既存41 + report4) + feedback/5。
- **新設 11 昇格**: thin-adapter 11 agent の抽出先 (§2)。plugin-root references/ 直下へ配置 (skill 私有階層は新設しない)。
- **帰属メタ**: resource-map.yaml (content 外別勘定・owner_component/consumers[]/category)。C24 が全 content 61 件 + resource-map を機械検証。
- write-owner: 新設 11 は skill routes (C01-C03 の build_args.references_new) が routes 内で生成。S-REFERENCES stage-b は配置検査のみ (二重書込みでなく単一 owner)。

---

## 5. 被覆チェックリスト (v1 全資産 → v2・非回帰 0 を保証)

> 各行は「v1 資産 → v2 での扱い → 非回帰検査法」。orphan (未対応 v1 資産) 0 を機械照合する (将来 C24 拡張 or 新規 governance glue で件数パリティ検査を推奨=§7 backlog)。

- [ ] 16 sub-agent → C04-C19 (maintain5=byte / thin-adapter11=golden fixture)。§2 で全16件が disposition + 検査法を保持
- [ ] 3 skill → C01/C02/C03 (OUT1 golden diff・C02/C03 も golden-pin 集合へ)
- [ ] 2 slash-command → C21/C22 (温存・manifest entry 一致)
- [ ] 1 hook → C20 (温存・PostToolUse 配線不変)
- [ ] validate-output-mode.py → C23 (温存)。新設 lint-reference-attribution.py → C24 (tests_min≥80)
- [ ] 直下 content references 45 (既存41+report4) + feedback/5 = 50 → byte-identical コピー
- [ ] 新設 11 references → thin-adapter 抽出・C24 帰属検証
- [ ] resource-map.md → resource-map.yaml へ置換 (C24 機械検証)
- [ ] 30 Node scripts (+report新規2) → vendor whole-tree byte 温存 (lint-vendor-parity.py)
- [ ] 118 templates → vendor whole-tree byte 温存
- [ ] 真 schema5 + fixture3 → vendor schemas-fixtures 温存 (S-SCHEMAS checks・C7)
- [ ] style-genome / d3-components / pagination / print-styles / assets → vendor whole-tree byte 温存
- [ ] Codex Image2 チェーン → C14 + vendor (機能不変)
- [ ] 30種思考法 生成後評価 (evaluate-deck.js + deck-evaluator + post-generation-evaluation.md + deck-postgen-hook.js) → C13 + C20 + vendor (機能不変)
- [ ] A4印刷/letterbox/印刷CSS → vendor (print-styles.css/style-builder.cjs) 温存
- [ ] GASデプロイ → vendor + references 温存
- [ ] 決定論レンダラ (render-slide.cjs 等 + templates) → C10 driver + vendor 温存
- [ ] spec-registry/decision-tree/unit-system → references + C06 gate (温存)

### v1 機能全域 → v2 非回帰チェック (代表縮退の防止)

- [ ] output_mode=slide 生成経路 → C01 (slide) OUT1 golden
- [ ] output_mode=report 生成経路 (4 reportType) → C01 (report) OUT1 golden × 4 reportType 代表
- [ ] 修正フロー (C02/C15) → C02 OUT1 golden
- [ ] 横断検証 (C03/C16・3並列×4条件) → C03 OUT1 golden
- [ ] 全面画像化ゲート (Codex Image2) → C14 経路の決定論 byte diff (regression-floor)
- [ ] 生成後評価ゲート (30種思考法・mode-aware) → C13/C20 起動の非回帰

---

## 6. references 勘定 換算表 (勘定基準の一本化)

| 体系 | content 内訳 | 帰属メタ (content 外) | 総数 |
|---|---|---|---|
| v1 (source-inventory §1.1 基準) | 直下46 (既存42=resource-map.md 含む + report4) + feedback5 = **51** ではなく content=直下46+feedback5=**51**… ※下段で正規化 | — (resource-map.md は§1.1 で既存42内) | 直下46 + feedback5 = 51 |
| v1 (v2 と同一勘定=resource-map を content 外へ) | 直下45 (既存41 + report4) + feedback5 = **50** | resource-map.md ×1 | 51 |
| v2 | 直下45 (既存41 + report4) + feedback5 + 新設11 = **61** | resource-map.yaml ×1 | 62 |

> 勘定の鍵: **resource-map (.md/.yaml) は content 外の帰属メタとして別勘定**。この 1 基準で v1/v2 を数えると v1 content=50・v2 content=61・帰属メタは各系 1 件。component-inventory.json references_config_assets.contents / index.md 換算表 / 本表は同一基準で一致する。

---

## 7. 既知 backlog (本台帳では未機械化・human_review)

1. **件数パリティの機械検証**: 「v2 の agents/references/vendor 実数 == v1 実数 (+新設11 +C24)」を C24 拡張 or 新規 governance glue で機械照合する (現状は本台帳の人間可読照合)。
2. **consumers≥2 の反証機構**: thin-adapter 判定の consumers に「抽出で生まれた薄化 agent 本体」を数えない外部 consumer≥2 要件、または「reference 正本と agent 本文の重複段落 0」を C24 の実閾値判定へ (自己成就ループの機械 backstop)。
3. **prose cross-reference lint**: handoff/index/progress の散文内 cross-reference (plan-findings フィールド名・findings 添字・waiver 伝播先 check id・pilot 前提 route id) が実在物へ解決するかを build gate で fail-closed 検査 (記録系 stale 同期契約の機械化)。
