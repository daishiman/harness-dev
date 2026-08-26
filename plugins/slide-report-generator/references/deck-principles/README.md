# 資料作成の大原則（deck-principles）

**責務**: slide / report / doc / diagram / chart / delivery が共有する「考え方」層の 177 原則を単一正本として保持し、**その時必要な分だけ**を機械的に抽出できるようにする。

原則本文・閾値の正本は `principles.json` の 1 ファイルのみ。ここにも agent prompt にも SKILL.md にも規範文と数値を写さない（写した瞬間に正本が 2 つになり、片方が必ず腐る）。

---

## なぜ JSON なのか

177 原則を散文 md で持つと、5 件だけ必要な場面でも 177 件を読ませることになる。context を食い潰すだけでなく、agent が「どれが今の判断に効くのか」を毎回自力で選ぶことになり、選択が揺れる。

そこで 1 原則 = 1 レコードとし、2 軸で機械的に絞り込む。

| 軸 | 意味 | 値 |
|---|---|---|
| `applies_to` | どの成果物に効くか | slide / report / doc / diagram / chart / delivery / meta |
| `phase` | 作成のどの局面で効くか | purpose / story / research / skeleton / rule / write / diagram / chart / flow / deliver / review / env / ai |

抽出は `scripts/extract-deck-principles.py` が行う。agent は「全部読んで選ぶ」のではなく「絞り込まれたものを適用する」。

---

## ツール中立性

`rule` は特定のスライドツールに依存しない表現だけで書く。原本の操作手順に相当する内容は、各原則の `tool_intent`（その操作で**何を達成したいのか**）へ畳んである。

これは本 plugin の実際の出力経路が HTML（slide deck / report / handout）だからで、操作手順をそのまま持ち込んでも適用先がない。逆に `rule` の側はツールが変わっても意味が通るので、PowerPoint や Google Slides で作る場面が来ても同じ規範がそのまま使える。

---

## 正本の分担

| 対象 | 正本 |
|---|---|
| 原則本文・閾値・章立て・チェックリスト | `principles.json` |
| 原則 → 本 plugin の受け皿（agent / 検査器 / reference）の写像 | `binding.json` |
| JSON の構造契約 | `../../schemas/deck-principles.schema.json` |
| consumer 写像の構造契約 | `../../schemas/deck-principles-binding.schema.json` |
| 抽出手続き | `../../scripts/extract-deck-principles.py` |
| 整合ゲート | `../../scripts/validate-deck-principles.py` |
| PowerPoint / Google Slides / HTML への薄い投影 | `tool-adapters.json`（原則本文は持たない） |
| guide-doc-generator vendor parity | `vendor-manifest.json`（binding は plugin-local overlay のため対象外） |
| 単位・寸法の実値（pt / px / 余白） | `../unit-system.md`（`thresholds` の pt は投影・印刷の参照値であって HTML の実値ではない） |
| 配色の実値 | `vendor/scripts/style-builder.cjs` の `SPEC.colors` |

`principles.json` の `thresholds` に pt 値が現れる箇所（DP-060 / DP-088）は、いずれも `note` で「HTML 経路の実値は unit-system.md が正本」と明示してある。これを守らないと、原則側と描画側で 2 つの寸法体系ができる。

---

## 使い方

```bash
# report の構成を設計する局面で効く原則だけを引く
python3 scripts/extract-deck-principles.py --applies-to report --phase story

# 図解を 1 枚描く直前
python3 scripts/extract-deck-principles.py --applies-to diagram --phase diagram

# 出力直前の点検（チェックリスト 20 項目 + 根拠原則）
python3 scripts/extract-deck-principles.py --checklist

# 特定 id を直接引く（他の原則から参照されたとき）
python3 scripts/extract-deck-principles.py --id DP-034 --id DP-108

# 同じ rule を PowerPoint / Google Slides / HTML の実行 brief へ薄く投影
python3 scripts/extract-deck-principles.py --consumer structure-designer --tool powerpoint
python3 scripts/extract-deck-principles.py --consumer structure-designer --tool google-slides
python3 scripts/extract-deck-principles.py --consumer html-generator --tool html
```

既定は agent の context へそのまま貼れる markdown。`--format json` は `selection` envelope
（consumer / catalog digest / selected IDs / xref IDs / tool adapter / budgets）と実レコードを返す。
`--limit` は基本選択だけの予算で、相互参照は `--xref-limit` の別予算（既定 8）。相互参照が
予算を超えた場合は依存原則を黙って落とさず exit 2 とする。

`binding.json` は全原則を `mapped_by_filter` / `already_enforced` / `out_of_scope` の
排他的な3集合へ分類する。さらに `consumer_scope` が対象 owner skill の agent を
`consumers` / 理由と実在 evidence を持つ `excluded_agents` の排他的な2集合へ分類する。
件数は固定せず、validator がカタログと agent 実体との閉包を毎回計算する。

---

## 検証

```bash
python3 plugins/slide-report-generator/scripts/validate-deck-principles.py
```

- schema 適合
- `no` が 1〜177 で欠番・重複なし（原本の通し番号との対応が崩れていないこと）
- `id` と `no` の整合（DP-034 ⇔ 34）
- 全 principle の `group` が `groups` に、全 group の `chapter` が `chapters` に存在
- `chapters[].principles` の範囲と実際の所属が一致
- `checklist.items[].refs` の参照先が全て実在
- `rule` 内で言及される `DP-xxx` が全て実在（相互参照の切れ検出）
- `applies_to` / `phase` / `enforcement` が `axes` の値域内
- binding の versioned schema 適合と、全原則分類の排他的閉包
- owner skill 配下 agent の consumer / 理由付き除外への排他的閉包
- guide の plugin-local binding overlay の schema・原則分類・consumer delivery
- `vendor-manifest.json` 全 entry の sha256 一致（通常実行で常時検査）

---

## 出典

章立てと原則の粒度は『PowerPoint資料作成 プロフェッショナルの大原則』（株式会社Rubato / 技術評論社）の目次構成を出典とする。`rule` 本文は逐語引用ではなく、本 plugin の生成契約へ適用できる規範として書き直したもの。
