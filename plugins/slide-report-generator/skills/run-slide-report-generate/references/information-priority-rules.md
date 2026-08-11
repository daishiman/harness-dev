# 情報優先度設計規約（slide/report 共通・生成前ゲート）

> **正本の所在**: 情報設計の**原理そのもの**は本ファイルに書かない。正本は
> `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/../system-spec-harness/skills/ref-system-design-knowledge/references/information-design.md`
> (deep knowledge card `information-design`)。本ファイルは **SRG 固有の写像**、すなわち
> 「その原理を slide/report のどの成果物・どの工程・どの既存規約へ対応させるか」だけの逐語正本である。
> 原理を再掲すると二重定義になり、片側だけ更新されて乖離する。

**責務**: `structure-designer` (slide) / `report-structure-designer` (report) が構成設計に入る**前**に確定させる
情報優先度宣言 (information priority map) の SRG 写像・適用点・決定論ゲートの定義。

## なぜ生成前なのか

SRG の品質検査は S1〜S26 (ui-quality-reviewer)・RQ1〜RQ37 (report-quality-reviewer)・deck-evaluator D5 と
**すべて生成後**に集中している。生成後検査は「作ったものが崩れていないか」は測れるが、
「そもそも何を大きく出すべきだったか」は測れない。優先順位付けを飛ばしたまま slideType を選び、
生成後に D5 (読者フック) で落ちると手戻りが最長になる。本ゲートはその手戻りを構成設計の前へ移す。

## 対応表 (原理 → SRG の具体形)

| information-design の概念 | slide での具体形 | report での具体形 | 既存規約との関係 |
|---|---|---|---|
| 文脈先行 (context of use) | 聴衆・発表時間・会場 (投影/手元) | 読者・読了想定時間・閲覧環境 (wide/narrow/print) | `hearing-facilitator` の読者価値ブリーフを `context_of_use` へ写す |
| 情報の棚卸し (inventory) | ヒアリングで得た素材 (主張・数値・引用・図の種) | 同左 | 素材は slideType/reportType を決める**前**に列挙する |
| グループ化 (groups) | スライドの束 (章) | `sections[]` | report の `sections[].role` は group.label に対応 |
| 優先順位 (rank + rationale) | 束の提示順と紙面配分 | 節の順と分量配分 | rank は「読者 task の頻度 × 失敗コスト」で説明する。`reportType` の骨格順を無条件に採らない |
| 削減 (drop + reason) | 1スライド1メッセージ (CONST_001) で落とす素材 | 節へ入れない素材 | **落とした素材は reason 付きで map に残す**。消えた素材と検討していない素材を区別する |
| 加工 (transform) | 生値→聴衆語 (絶対日時→相対、率→対比) | 同左 | 加工には「どの読者 task を助けるか」を書く |
| 形式の比較選定 (form_selection) | slideType の選定 | reportType / 節形式の選定 | `slide-type-decision-tree.md` は**選定器であって免罪符ではない**。候補 2 件以上と不採用理由を残す |
| 強弱 (emphasis) | フォント階層・配置・60-30-10 配色 | 見出し階層・余白・図の配置 | S16 (アクセント面積) / S10 は emphasis の写像先であって代替ではない |
| 意味的装飾 (styling) | バッジ・枠・アイコン | 同左 | `semantic_intent` に無い装飾 (「寂しいから色を足す」) は宣言できない |
| 色単独依存の禁止 | — | — | 既存の WCAG 2.1 AA 基準と同方向。`accessibility.color_not_sole_channel` で明示する |

## 成果物と決定論ゲート

- **成果物**: `information-priority-map.json` (1 deck / 1 report につき 1 件)。
  schema = `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/../system-spec-harness/schemas/information-priority-map.schema.json`。
  `artifact_kind` は slide なら `"slide-deck"`、report なら `"report"`。
- **ゲート** (構成承認より前・fail-closed):

```bash
python3 ${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/../system-spec-harness/scripts/validate-information-priority.py \
  <出力先>/information-priority-map.json
```

  exit 0=OK / 1=違反 / 2=usage error。違反時は構成設計へ進まない。

- **このゲートが機械検出するもの**: 順位が確定する前に装飾を宣言していないか / 順位が連番の
  真の順位になっているか / 削除・加工に理由があるか / 形式を 2 件以上比較したか /
  装飾が意味を運んでいるか / 色だけに意味を担わせていないか。
- **このゲートが検出しないもの**: その順位が読者にとって本当に正しいか。これは
  `deck-evaluator` D5 (slide) / `report-quality-reviewer` (report) と人間の未閉塞責務のまま。
  本ゲートは「順位付けを**やったこと**」を保証するのであって「順位が**正しいこと**」は保証しない。

## 非適用 (exemption)

熟練者が高頻度・大量に走査する一覧主体の成果物など、`information-design` の非適用条件に当たる場合は
map の `exemption` に `reason` と `approved_by` を書いて宣言する。黙って原則を外した状態と、
意図して外した状態を区別できるようにするための受け皿であり、宣言すれば順位付け自体は免除されない。
