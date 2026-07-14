# field-impact-map

`C09` (`scripts/map-field-impact.py`) が diff hunk を **artifact kind/path** と
**name / type / required / enum / semantics** の 5 軸へ写像するための **決定論写像表**。

## なぜ code でなく reference なのか

写像規則を C09 の Python に hardcode すると、harness-creator 側の rubric/schema/template
規約が変わるたびに guardian 自身が drift 源になる。規則を data (この JSON) に外出しし、
C09 は「表を読んで適用するだけ」に留めることで、写像の更新をコード変更なしに行えるようにする。

## 契約

- `field-impact-map.json` が唯一の SSOT。C09 は `--map` でこのファイルを受け取り、
  既定は script 位置からの self-relative (`../references/field-impact-map/field-impact-map.json`)。
- `artifact_kinds.<kind>.path_globs` で対象ファイルの kind を判定し、
  `rules[].match_any` (Python `re` 構文) を unified diff の `+`/`-` 行本文へ照合して axis を決める。
- 最初に一致した規則の `axis` を採用する (規則順が優先度)。
- `other` は分類外 artifact のフォールバックで、常に `semantics` 影響としてレビューへ委ねる。

## 更新手順

harness-creator の rubric/schema/template 規約が変わったら、対応する `match_any` regex を
この JSON に追記する。C09 のコードは変更しない。
