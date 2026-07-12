# 既存レポート 部分修正規約（slide-report-modifier report 経路 手続き知識 SSOT）

> **正本**: このファイルは slide-report-modifier の **report 経路**（output_mode=report）の手続き知識/規範の SSOT。slide 経路の対になる正本が同ディレクトリの [modification-rules.md](modification-rules.md)（slide=`index.html` ⇔ `structure.md`）で、本ファイルは report=`report.html` ⇔ `report-structure.json` を担う。run-slide-report-modify の SKILL.md と agent 本体（agents/slide-report-modifier.md）の双方が mode 分岐でこれを参照する。素材（骨格・書式・ビジュアル規範）の上位正本は plugin-root の `$CLAUDE_PLUGIN_ROOT/references/report-types.md` / `$CLAUDE_PLUGIN_ROOT/references/report-writing-rules.md` / `$CLAUDE_PLUGIN_ROOT/references/report-visual-strategy.md`、構造契約は `$CLAUDE_PLUGIN_ROOT/schemas/report-structure.schema.json` を辿る。

**責務**: 既存 report 成果物（`report.html` ＋ `report-structure.json`）の指定箇所部分修正のドメイン定義（用語集・評価基準・修正タイプ分類・制約カタログ RCONST_001-012）と部分修正規範（reportType 4 骨格の維持・section 構造の局所修正・`report.html` ⇔ `report-structure.json` 同期維持・読み物文体と 1 項目 1 ビジュアルを壊さない修正・履歴の sidecar JSON 追記）の逐語正本。slide-report-modifier（薄化アダプタ）は役割・起動条件・I/O契約に専念し、詳細規範は本 reference を SSOT とする。slide 側の CONST_001-012（[modification-rules.md](modification-rules.md)）と番号帯を分けた **RCONST_001-012** を用いる（衝突回避・additive）。

## 用語集
| 用語 | 定義 | 関連概念 |
|------|------|----------|
| report-structure.json | 本 report 経路の SSoT（単一の正本）。`render-report.js` がここから `report.html` を決定論生成する駆動設計 | RCONST_001 / RCONST_002 / RCONST_012 |
| section | report の主単位（slide の 1 スライドに対応）。`id` / `heading` / `role` / `paragraphs[]` / `visual` / `callouts` を持つ | 骨格 role / 修正タイプ分類 |
| reportType | 目的別骨格の型（4 enum: `internal-analysis` / `client-proposal` / `tech-doc` / `learning`）。決まったナラティブ骨格（節の並び）を持つ | RCONST_005 |
| role | section の骨格節役割（`summary`/`background`/`analysis`/`finding`/`next-action`/`problem`/`solution`/`impact`/`step`/`cta`/`overview`/`prerequisite`/`procedure`/`caution`/`reference`/`question`/`concept`/`diagram-understanding`/`example-application`/`conclusion`/`body`）。骨格の論理順序を担う | RCONST_005 |
| paragraphs[] | 読み物本文。1 要素＝1 段落（markdown 可: 太字/箇条書き/番号リスト/インラインコード/表/リンク）。slide の長文禁止を report では緩和 | RCONST_007 |
| visual 三択 | 各 section のビジュアル（`svg` / `mermaid` / `codex-image` / `none` から内容適合で 1 種）。固定比率を持たない | RCONST_008 / RCONST_011 |
| callouts | 注記・警告ブロック（`note` / `warning` / `tip` / `caution`）。落とし穴・補足の強調 | 書式規律 |
| meta.length | 読み物の長さ方針（`brief` / `standard` / `deep`）。段落密度の目安 | RCONST_007 |
| 修正履歴 sidecar | `report-structure.json` は schema が `additionalProperties: false` ゆえ履歴をインラインできない。外部 JSON（`report-structure.history.json`）＋ `meta.version` semver bump で追跡する | RCONST_004 |

## 評価基準（ドメイン固有の判定基準）
| 基準 | 条件 |
|------|------|
| report-structure.json の有効性 | 受理=`report-structure.schema.json` に valid な `report-structure.json` が指定パスに存在 / 拒否=不在・schema 不適合・必須情報欠落（RCONST_001 でゲート） |
| 修正要求の具体性 | 受理=変更前・変更後が具体テキスト／具体 section で特定できる / 拒否=曖昧要求（例「もっと読みやすく」） |
| 同期整合 | 合格=同期確認チェックリスト4項目を全て満たす（section 数一致・見出し/keyMessage 一致・role 一致・履歴記録） / 不合格=いずれか不一致 |
| 骨格整合 | 合格=`reportType` の骨格 role の論理順序が保たれる（背景→結論／前提→手順／問い→まとめ） / 不合格=骨格順序の破壊・無言の骨格節省略 |
| AI画像図解の実行可否 | 実行可=`codex-image` 生成の明示指示あり | 実行不可=明示指示なし（通常は svg/mermaid/本文で改善・RCONST_011） |

## 修正タイプ分類
| 修正タイプ | 説明 | 影響範囲 |
|-----------|------|---------|
| 本文修正 | 段落テキスト・数値・callout の変更 | 該当 section のみ |
| role/骨格節変更 | section の `role` 変更・骨格節の差し替え | 該当 section + 骨格順序整合 |
| 構成変更 | section 順序・追加・削除 | 全体構成（骨格順序維持） |
| ビジュアル変更 | `visual` 三択（svg/mermaid/codex-image/none）の差し替え・配置調整 | 該当 section のみ |
| AI画像図解差し替え | 明示指示時のみ `visual.kind` を `codex-image` へ変更 | 該当 section + vendor/assets/generated |
| 全体改善 | 文体・情報密度・一貫性の改善（読み物性の底上げ） | 複数 section |

## ビジネスルール

各制約に RCONST_NNN を付番し、目的（防ぐ事象）と背景（採用根拠）を併記する。slide 経路の CONST_001-012 と対を成す report 版であり、slide の CONST とは独立の番号帯を用いる。

- **RCONST_001 (report-structure.json 必須)**: 修正フローは `report-structure.json` を前提とし、存在しない・schema 不適合の場合は新規生成フロー（`run-slide-report-generate`）へ案内する。
  - 目的: 正本不在のまま `report.html` だけを直接編集し、状態が復元不能になる事態を防ぐ。
  - 背景: `report-structure.json` は report 経路の SSoT であり、`render-report.js` がここから `report.html` を決定論生成する駆動設計（slide の structure.md 駆動と対）を採用しているため。

- **RCONST_002 (report.html ⇔ report-structure.json 同期必須)**: `report.html` を修正したら必ず `report-structure.json` の該当 section も更新する。正本は `report-structure.json` 側であり、原則は「`report-structure.json` を直し `render-report.js` で `report.html` を再生成」する。
  - 目的: 両ファイルの乖離による状態不整合（次回修正時の復元不能・履歴不正確）を防ぐ。
  - 背景: `report.html` は `report-structure.json` の忠実な射影であり、乖離すると正しい状態を復元できない（RCONST_012）。

- **RCONST_003 (承認必須)**: 修正案はユーザー承認後にのみ実行する。承認前に `report.html` / `report-structure.json` を書き換えない。
  - 目的: ユーザー意図と異なる修正の既成事実化を防ぐ。
  - 背景: 修正は既存成果物の破壊リスクを伴うため、提示→承認→実行のゲートを設ける（slide CONST_003 と同方針）。

- **RCONST_004 (履歴記録必須・sidecar JSON)**: 全ての修正を追跡可能に記録する。`report-structure.json` は schema が `additionalProperties: false` のため履歴をインラインできない。したがって (1) `meta.version` を semver で bump し、(2) 同ディレクトリの sidecar `report-structure.history.json`（JSON 配列）に 1 修正 1 エントリを追記する。
  - 目的: 変更経緯を追跡可能にしつつ、`report-structure.json` を schema valid に保つ（インライン履歴で validation を割らない）。
  - 背景: slide は structure.md（markdown・schema 非拘束）の履歴セクションで記録できるが、report の構造正本は閉じた JSON schema であり、履歴は外部化する必要があるため。

- **RCONST_005 (reportType 骨格の維持)**: `reportType` の骨格（role の論理順序）を崩さない。骨格節を省略する場合は省略理由を section 冒頭の断り書き（`paragraphs`）や `callouts` に残す（無言の省略禁止）。同 role の複数使用（情報量の多い節の分割）は可。
  - 目的: 骨格の論理順序（背景→結論／課題→CTA／前提→手順／問い→まとめ）の破壊による読み物の破綻を防ぐ。
  - 背景: 論理順序は reportType を型たらしめる不変点（report-types.md §5）。順序保持は 4 型すべてで絶対であるため。

- **RCONST_006 (最小変更)**: 要求された修正のみを実施し、過剰な変更を避ける。
  - 目的: 要求外の改変による既存レポートの予期せぬ破壊を防ぐ。
  - 背景: 修正は破壊リスクが高く、変更面積が広いほど検証コストと回帰リスクが増すため（slide CONST_006 と同方針）。

- **RCONST_007 (読み物文体維持)**: report は「文章多めが正」。各 section に空でない段落（結論文＋根拠）を置き、chip 化・1 メッセージ圧縮へ退化させない。見出しだけの空節を作らない。1 段落 1 論点（段落先頭に結論文）。`meta.length`（brief/standard/deep）の段落密度目安に従う。
  - 目的: slide 規律の過剰適用による「見出しと chip の羅列」化（読み物価値=文脈・論拠・ニュアンスの喪失）を防ぐ。
  - 背景: slide は投影・一瞬読み、report は手元・通読という前提差（report-writing-rules.md §0）。緩和するのはコンテンツ意図層のみで、意匠/技術層は維持する（RCONST_010）。

- **RCONST_008 (1項目1ビジュアル維持)**: 各 section の非 `none` `visual` は最大 1。図解過多にしない。文章と `callouts` で足りる節は迷わず `none`。複数の図が欲しくなったら 1 節に詰めすぎのサインで、構成設計（構成変更）へ差し戻して section を分ける。
  - 目的: 図解過多による本文の痩せ・可読性低下を防ぐ。
  - 背景: read-through では図解過多を避けるのが原則（report-visual-strategy.md §2）。1 項目 1 ビジュアルは両モード共通の設計原則であるため。

- **RCONST_009 (退化耐性)**: コード・コマンド・設定値・精密な数値・料金・対照表など逐語が頻繁に変わる要素は画像（`codex-image`）へ焼き込まず、本文の markdown 表・コードブロックで正確に持つ。生成画像には逐語を載せない。
  - 目的: 更新時に誤りが画像として固定化する事態を防ぐ。
  - 背景: full-image-deck-method / slide CONST_007 と同一方針（report-writing-rules.md §3・report-visual-strategy.md §5）。退化耐性は両モード共通であるため。

- **RCONST_010 (意匠 SSOT 共有維持)**: 最小フォント 1.4rem・Kanagawa 配色・フォント・印刷 CSS・`theme`（kanagawa-lotus 固定）を report 独自に発明しない。意匠/技術層は slide と共有 SSOT のまま維持する。
  - 目的: 意匠 SSOT の分岐（report 独自意匠の発明）による一貫性崩壊・可読性下限割れを防ぐ。
  - 背景: 緩和対象はコンテンツ意図層（1メッセージ性・文量・chip 強制）だけで、意匠/技術層は共有維持（report-writing-rules.md §0・§3・build-contract §D）であるため。

- **RCONST_011 (三択 visual の環境可用性と AI画像の明示指示)**: `visual.kind` の確定前に描画可用性を確認する（`codex-image` は codex CLI、`mermaid` は mermaid CLI/lib を `validate-output-mode.py --preflight` 等で確認）。描画不能な種別を確定しない。`codex-image` 生成は明示指示時のみで、通常は svg/mermaid/本文で改善する。不在時は種別を現実的な代替へ寄せ `visual.rationale` に理由を残す。
  - 目的: 描画不能種別の確定による生成失敗・意図しない画像化を防ぐ。
  - 背景: 環境可用性チェックと明示指示原則（report-visual-strategy.md §4・slide CONST_011）に準拠するため。

- **RCONST_012 (構造同期の忠実射影)**: `report.html` は `report-structure.json` の忠実な射影（`render-report.js` の決定論生成）である。勝手に section を増減しない。`report.html` を直接手編集した場合も、必ず `report-structure.json` へ同じ変更を反映し、`render-report.js` の再生成結果と一致させる。
  - 目的: 手編集による `report.html` と `report-structure.json` の恒久乖離（次回修正時の上書き喪失）を防ぐ。
  - 背景: `render-report.js` が `report-structure.json` を唯一の入力として `report.html` を決定論生成するため、正本を JSON 側に一元化する（RCONST_002 の技術的根拠）。

## 修正フローパターン

修正タイプ別の部分修正手順（パース→対象特定→差分適用→非対象箇所保護→同期）。原則は「`report-structure.json` を直し `render-report.js` で `report.html` を再生成」する（RCONST_002 / RCONST_012）。

### 本文修正（軽微）
```
1. report-structure.json 読み込み（schema valid を確認）
2. 対象 section を id/heading で特定
3. paragraphs[] / callouts[] を修正（読み物文体・1段落1論点を維持・RCONST_007）
4. render-report.js で report.html を再生成（report-structure.json ⇔ report.html 同期）
5. meta.version bump + report-structure.history.json へ履歴追記
```

### ビジュアル変更（中程度）
```
1. report-structure.json 読み込み
2. 対象 section を特定
3. visual.kind を三択最適化で選び直す（内容適合・1項目1ビジュアル・環境可用性を確認・RCONST_008/011）
4. codex-image は明示指示時のみ。rationale を残す
5. render-report.js で report.html を再生成
6. meta.version bump + 履歴追記
```

### role/骨格節変更・構成変更（大規模）
```
1. report-structure.json 読み込み
2. reportType 骨格（role の論理順序）を確認
3. section の role 変更／順序・追加・削除を設計（骨格順序維持・省略は断り書き・RCONST_005）
4. 破壊リスクが高い場合はユーザー承認取得（RCONST_003）
5. report-structure-designer / visual-strategist へ委譲（構成再設計時。委譲はオーケストレータ側が dispatch）
6. render-report.js で report.html を再生成 → report-structure.json 全面同期
7. meta.version bump + 履歴追記
```

## report.html ⇔ report-structure.json 整合性維持（重要）

**原則: report.html と report-structure.json は常に同期を維持すること（RCONST_002 / RCONST_012）。正本は report-structure.json 側。**

両ファイルが整合していないと、以下の問題が発生する：
- 次回の修正時に `report-structure.json` から正しい状態を復元できない
- 修正履歴が不正確になる
- 構成変更・再生成時に手編集分が上書き喪失する

### 同期フロー
```
【本文/ビジュアルを修正する場合（推奨）】
report-structure.json 修正 → render-report.js で report.html 再生成 → 履歴追記

【report.html を直接手編集した場合】
report.html 手編集 → report-structure.json の該当 section へ同じ変更を反映
→ render-report.js の再生成結果と一致することを確認 → 履歴追記
```

### report-structure.json に反映すべき項目
| report.html / 内容の変更 | report-structure.json の更新箇所 |
|--------------------------|--------------------------------|
| 段落テキスト変更 | 該当 section の `paragraphs[]` |
| 見出し変更 | 該当 section の `heading` |
| 骨格節役割の変更 | 該当 section の `role`（骨格順序整合を確認） |
| ビジュアル差し替え | 該当 section の `visual`（kind/placement/rationale） |
| 注記・警告の変更 | 該当 section の `callouts[]` |
| section 追加/削除/順序変更 | `sections[]` 全体（骨格 role 順序を維持） |
| 長さ方針の変更 | `meta.length` |

> **同期確認チェックリスト（完了ゲート＝停止条件）は agent 本体（agents/slide-report-modifier.md）の Layer 6 が保持する**（4項目: section 数一致・見出し/keyMessage 一致・role 一致・履歴記録）。上記の同期フローと反映項目表を適用した結果を、当該ゲートで検証する。

## 履歴追記（sidecar JSON・RCONST_004）

`report-structure.json` は `additionalProperties: false`（root / `meta` / `section` すべて）のため、`revisionHistory` 等をインラインすると schema validation を割る。したがって履歴は 2 系統で残す：

1. **`meta.version`（semver）を bump** する — 修正の発生自体を構造正本に刻む（本文修正=patch、role/骨格・構成変更=minor 目安）。
2. **sidecar `report-structure.history.json`（同ディレクトリ・JSON 配列）へ 1 修正 1 エントリを追記** する。

sidecar エントリの推奨フィールド（自由拡張可・別ファイルゆえ schema 非拘束）：
```json
{
  "version": "1.0.1",
  "at": "2026-07-05T12:00:00+09:00",
  "modType": "本文修正 | role/骨格節変更 | 構成変更 | ビジュアル変更 | AI画像図解差し替え | 全体改善",
  "sections": ["sec-analysis-1"],
  "request": "ユーザー修正要求の要旨",
  "change": "現在→修正後の差分要旨",
  "reReport": "render-report.js 再生成の実施有無"
}
```

> report.html は決定論生成物ゆえ履歴を持たない（`report-structure.json` + sidecar が正本）。sidecar が無い環境（初回修正）では新規作成し、以降追記する。
