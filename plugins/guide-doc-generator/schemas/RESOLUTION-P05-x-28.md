# P05-x-28 裁定: assets / attachments の data URI 保持契約 (PAT-7)

- leaf: `P05-x-28` (write_scope: `plugins/guide-doc-generator`)
- 起票時の見立て: 「AC-C20-06 と ROUNDTRIP-CONTRACT の 2 者が矛盾している」
- **実測後の見立て: 当事者の数え違いだった。矛盾しているのは ROUNDTRIP-CONTRACT の 1 者だけである。**

## 0. 裁定

**ROUNDTRIP-CONTRACT.md の `/assets/*/data_uri` エントリが誤っている。これを改める。
schema・抽出実装・テスト・AC-C20-06 は変更しない。**

これは「実装が動いているから正しい」ではない。下記 §1 の機械的事実が、
ROUNDTRIP-CONTRACT が根拠として挙げた前提そのものを反証している。

## 1. 反証: `data_uri` は抽出器の発明ではない

ROUNDTRIP-CONTRACT の rationale はこう書いていた。

> そもそも schema には data_uri というフィールドが無く、免除の宣言先が存在しない。
> …これは抽出器が schema に無いキーを発明したことによる E-KEY-UNKNOWN であり、
> schema を緩めて data_uri を受け入れるのは基準を弱める側に当たる。

しかし `scripts/embed-assets.py` (C13) は素材 1 件ごとに以下を entry へ書き込む。

| C13 が entry へ足すキー | schema の `$defs.asset` / `$defs.attachment` に在るか |
| --- | --- |
| `data_uri` | **無い** |
| `embed_status` | **無い** |
| `embed_source_path` | **無い** |
| `embed_skip_reason` | **無い** |
| `encoded_chars` | **無い** |
| `source_bytes` | **無い** |
| (top-level) `asset_embedding` | **無い** |

`$defs.asset` の properties は `id / kind / src / alt / caption / role` の 6 個で
`additionalProperties: false`、`$defs.attachment` は `id / filename / mime / src / fallback_hint` の
5 個で同じく `additionalProperties: false`。

したがって:

1. **`data_uri` は C20 が発明したのではなく、C13 が書いたものを C20 が復元している。**
   発明の主体を取り違えたまま「抽出器がキーを発明した」と裁定していた。
2. **`data_uri` を E-KEY-UNKNOWN と呼ぶなら、残り 5 キーと `asset_embedding` も同罪になる。**
   1 つだけを咎める根拠が無い。論拠が対象を選べていない時点で、その論拠は成立していない。
3. よって争点は「round-trip の可否」でも「キーの発明」でもなく、
   **schema が記述している文書型が C13 前の著者構成データだけで、C13 後の埋め込み済み
   構成データに名前が与えられていないこと**である。

## 2. 二つの文書型

| | 著者構成データ (C13 前) | 埋め込み済み構成データ (C13 後) |
| --- | --- | --- |
| 正本 | `handout-config.schema.json` | **これまで正本が無かった** (本裁定で明文化) |
| `src` | 原本相対パス (または直書き data URI) | 原本相対パス |
| ペイロード | `src` が data URI ならそこ | `data_uri` |
| 生成者 | 著者 / C01 系 | C13 `embed-assets.py` |
| 消費者 | C12 validate / C13 | C11 render |
| C20 の復元先 | — | **こちら** |

C11 は `_project_asset()` でこの 2 方言を吸収している (著者が `src` へ直書きした data URI を
`data_uri` へ移し `src` を空にする) ので、描画器から見れば入力は常に後者の形である。

`Renderer` は `("data-hb-src", asset.get("src", ""))` を出す。よって:

- **C13 経路** — `src` = 原本相対パス → `data-hb-src` = 原本相対パス。
  C20 は `src` に原本パスを戻し、`<img src>` の data URI を `data_uri` へ入れる。
- **著者直書き経路** — `_project_asset` が `src` を空にする → `data-hb-src` = 空。
  C20 の `gap()` 分岐が発火し `src` へ data URI を入れる (`$defs.local_source` の `^data:` に適合)。

**両分岐とも既に正しく実装されている。** 失われる情報は無い。

## 3. 旧裁定を採ると何が壊れるか

旧 `original_path_field` は「data-hb-src が非空ならその値を src に戻し、**data URI は捨てる**
(再埋め込みは C13 の責務)」だった。これを実行すると:

- R14 (受け取った HTML からの逆抽出) では、**原本の `assets/` ディレクトリが手元に無い**のが
  普通である。HTML 中の data URI が唯一の実体コピーであり、これを捨てると
  「再埋め込みは C13 の責務」が実行不能になる。抽出した構成データは再描画できない。
- つまり旧裁定は、round-trip の無損失性を守るつもりで**逆に値を消失させる**。
  これは `/notes_enabled` のエントリが「P1 (再生成可能) ではなく値の消失である」として
  免除を退けたのと同じ基準に、自分自身が抵触している。

## 4. テストを弱めていない

`tests/extract-handout-config.py/test_marker_extraction.py` の 3 件は変更しない。

| テスト | fixture の `data-hb-src` | 旧裁定下 | 本裁定下 |
| --- | --- | --- | --- |
| `test_image_asset_is_restored_with_data_uri` | 有 | **赤になる** (data URI が捨てられる) | 緑 |
| `test_attachment_is_restored_with_data_uri` | 有 | **赤になる** | 緑 |
| `test_large_data_uri_is_kept_verbatim` | 無 | 緑 (`src` が data URI を持つ) | 緑 |

前 2 件は「`src` が原本パスに戻る」と「data URI がエントリのどこかに残る」を**同時に**要求する。
旧裁定はこの 2 件を赤にする。**テストの側が正しい要件を書いており、裁定の側が間違っていた。**

キー名を固定せず「エントリのいずれかの値として原文の data URI が保持される」で書く方針は
`tests/extract-handout-config.py/README.md` の G4 に記録済みの意図的な緩和であり、本裁定で
キー名が `data_uri` に確定した後もそのまま置く (キー名は C13 側の都合で動きうるため、
テストが固定すると第 2 の名簿になる)。

## 5. AC-C20-06 は変更不要

AC-C20-06 の文言は「attachments / assets の filename / mime / alt / fallback_hint と
**data URI 本体が復元される**」であり、本裁定と一致している。矛盾していたのは
ROUNDTRIP-CONTRACT の側だけだった。

**この事実は重要である**: AC-C20-06 の本文は `plugin-plans/guide-doc-generator/briefs/script-brief-C20.json`
にあり、本 leaf の `write_scope: plugins/guide-doc-generator` の外にある。もし裁定が逆向き
(AC を改める) だったなら、本 leaf では書けず受け皿の割れ (PAT-4) を作るところだった。
裁定が write_scope 内で閉じたのは結果であって、設計されていたわけではない。§7-3 に残す。

## 6. 変更したもの

1. `schemas/ROUNDTRIP-CONTRACT.md` の `/assets/*/data_uri` エントリ —
   `decision` を `marker` から `dialect` へ改め、rationale を §1 の反証で置換。
   `payload_field` / `original_path_field` / `residual_work` を実装と一致させた。
   **`residual_work` は空になる** (残作業は無い。実装が既に正しい)。
2. `schemas/handout-config.schema.json` の `assets` / `attachments` の `description` —
   「本 schema が記述するのは C13 前の著者構成データである」「C13 後は entry へ 6 キー、
   文書へ `asset_embedding` が加わり本 schema では検証できない」を明記。
   **properties / required / additionalProperties は 1 文字も変えていない。**

## 7. 未解決事項

1. **C13 の出力を検証する正本が無い。** 埋め込み済み構成データは schema で検証できず
   (`additionalProperties: false` に必ず抵触する)、専用の schema も無い。現状は C11 が
   読めるかどうかが唯一の検査になっている。C13 出力用 schema の追加は本 leaf の
   acceptance_criterion (3 者の言明を揃える) の外なので起票候補として残す。
2. **C12 validate は E-KEY-UNKNOWN を実際に出す。今それが露見していないのは経路が無いからで、
   契約が守られているからではない。** `validate-handout-config.py:490-493` は
   `additionalProperties is False` のノードで未知キーごとに `unknown_key` (= `E-KEY-UNKNOWN`) を
   emit する。一方 build skill の工程順は R2 (design) で validate → R3 (render) で
   embed-assets → render であり (`prompts/R2-design.md:76` / `prompts/R3-render.md:74`)、
   **C13 の出力が validate を通る経路は存在しない**。
   ただし **C20 の出力には経路がある**: R14 の「逆抽出 → 再編集 → 再描画」を回すなら、
   抽出した構成データを R2 の validate へ入れるのが自然な流れであり、そこは
   `/assets/0/data_uri` で落ちる。`test_round_trip_equivalence` は `sections` しか
   比較しないためこれを検出しない。**本裁定は「どちらが正本か」を確定したが、
   「抽出結果を validate へ通せるか」は未解決のまま残る。**
   解き方は 2 つあり本 leaf では選ばない — (a) C13 後の文書型に専用 schema を与えて
   validate に文書型の切替を持たせる、(b) C20 に「著者構成データとして出す」モードを足し
   `data_uri` を `src` へ畳んで出す。(b) は旧裁定の内容だが、**選択肢としてなら成立する**
   (常にそうせよという強制でなければ値は消失しない)。
3. **裁定文書と実装を結ぶ検査が無い。** `ROUNDTRIP-CONTRACT.md` を読むテストは 0 件
   (機械照合で確認)。本裁定も含め、実装が変わっても裁定文書は黙って古くなる。
   P05-x-25 §6-2 / P05-x-27 の同種の未解決事項と同じ根に当たる。
