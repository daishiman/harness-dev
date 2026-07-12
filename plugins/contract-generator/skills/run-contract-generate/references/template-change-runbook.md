# ひな形変更時の対応 Runbook

ひな形(.docx)は法務課によって随時更新されうる。本スキルは**ハードコードを避け、変更を検知して知らせる**設計。
ひな形が変わったとき/変わったか不安なときは以下を実施する。

## 仕組み(なぜ壊れにくいか)

| 層 | 機構 | 効果 |
|---|---|---|
| 取得 | `render.fetch_template` が名前パターンで**毎回最新版**を取得 | ファイル更新・rename に追従 |
| 差込 | `docx_fill` が固定座標でなく **anchor(安定テキスト)+黄色run** で位置特定 | 文言の微変更に追従 |
| 検知 | `scan_template.py` が黄色run実体と `template-mapping.json` を**差分照合** | 構造変更を検出して停止・報告 |
| 生成後 | `docx_fill.detect_drift` が**未置換マーカー残存**を検出 | 取りこぼしを後段で再検知 |

## 手順

### 1. 変更の有無を診断

```bash
python3 ../../../lib/scan_template.py --type individual
python3 ../../../lib/scan_template.py --type corporate
```

出力の見方:
- **MISSING anchor**: `template-mapping.json` の差込位置がひな形側に見つからない=条文・文言が変わった。
- **UNMAPPED marker**: ひな形に新しいプレースホルダ(`●`/`XXXX`等)が増えた=新しい差込項目。

### 2. ドリフトを解消

| 検出 | 対応 |
|---|---|
| MISSING anchor | `template-mapping.json` の該当 field の `anchor` を新しい安定テキストに更新 |
| UNMAPPED marker(新項目) | (a)台帳に対応列を追加 → (b)`template-mapping.json` に field 追加 → (c)`ledger.py` の HEADERS に列追加 |
| 条項の追加/削除 | `conditionals` に `remove_paragraph_anchors` / `anchor_select` を追加・修正 |

`template-mapping.json` は plugins 内の**データファイル**なので、編集してもスキル再ビルド不要。
`_last_synced_template` を更新し、`_version` を上げておく。

### 3. 再診断 → 試験生成

```bash
python3 ../../../lib/scan_template.py --type individual   # exit 0 になることを確認
python3 ../../../lib/engine.py --phase draft --type individual --row <試験行> --dry-run
```

`--dry-run` は Drive 保存・台帳書込をせず、差込結果と drift レポートのみ返す。

### 4. 列を増やした場合

`ensure_schema` は既存シートに**欠落ヘッダを末尾追記(非破壊)**する。次回 `lib/engine.py --phase draft` 実行時に自動反映される。
既存サンプル行は保持される。

## 注意

- `read_file_content`(MCP)ではハイライト属性が取れない。黄色runの確認は必ず `scan_template.py`(標準ライブラリ `docx_lib`)で行う。
- ひな形の構造を大きく変えた場合(章立て変更等)は、`anchor` だけでなく `conditionals` の見直しも必要。
- **甲側 field を追加する場合は `{{party_a.*}}` 参照で書く** (値直書き禁止)。正本は `references/party_a-readme.md` (4 層フォールバック) と `references/README-setup.md` (Detailed Setup SSOT)。
- Drive ID / SA メール / Keychain 命名規約はすべて `references/README-setup.md` を参照(本書では複製しない)。
