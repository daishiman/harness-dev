# Task仕様書：ファイル出力

## 1. メタ情報

| 項目     | 内容                |
| -------- | ------------------- |
| 名前     | File Output Manager |
| 専門領域 | ファイル操作        |
| Phase    | 3                   |

---

## 2. 目的

生成された投稿文をObsidianファイルとして出力し、00ネタファイルのリストを更新する。

## 3. 責務

| 責務               | 成果物               |
| ------------------ | -------------------- |
| 日付算出           | 投稿日付             |
| ファイル生成       | X長文投稿ファイル    |
| 00ネタ更新         | リスト追記           |

---

## 4. 実行仕様

### 4.1 日付算出

#### 手順

1. **00ネタファイルを読み込む**
   - パス: `${XLP_NETA_FILE}`（未設定時は `${XLP_VAULT_ROOT}` がある場合にのみ [output-config.json](../skills/run-x-longpost-create/references/output-config.json) の path template を解決）

2. **最新投稿日を特定**
   - リストの最初の日付付きエントリを検索
   - 形式: `[[X長文投稿-prompt作成 - YYYY-MM-DD_`

3. **次の投稿日を算出**
   - 最新日付 + 1日

#### 例

```
00ネタファイルの最初のエントリ:
- [ ] [[X長文投稿-prompt作成 - 2026-01-14_AI開発で...]]

次の投稿日: 2026-01-15
```

### 4.2 ファイル名生成

#### 形式

```
X長文投稿-prompt作成 - YYYY-MM-DD_[タイトル].md
```

#### ルール

| 項目 | ルール |
|------|--------|
| 日付 | YYYY-MM-DD形式 |
| タイトル | **Phase 1.5 の create-title が確定したタイトル＝見出し1（`# タイトル`）と完全に同一の文字列を使う**（言い換え・短縮・別案への差し替えは禁止） |
| 長さ | **50文字以内（絶対）。超過時に切り詰めてはならない** |
| サニタイズ | `\ / : * ? " < > \|` を除去し、空白を `_` に置換する（`generate-filename.js` の `sanitizeTitle` と同一ロジック。長さによる切り詰めはしない） |

#### 見出し1＝ファイル名の一致ルール（絶対）

正本: [references/heading-structure-rules.md §2](../skills/run-x-longpost-create/references/heading-structure-rules.md)

Phase 1.5 の create-title が確定した同一のタイトル文字列が「長文Aの見出し1」「長文Bの先頭行」「`# タイトル` セクション」「ファイル名のタイトル部」で使われる。すべてが一致していなければならない。このフェーズでタイトルを作り直さない。

**ファイル名生成は必ずスクリプト経由で行う**（手書きで組み立てない）:

```bash
node ${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/generate-filename.js --date "YYYY-MM-DD" --title "[見出し1と同一のタイトル]"
```

| 終了コード | 意味 | 次アクション |
|-----------|------|-------------|
| 0 | PASS | `filename` を scratch 内の正規 basename に、`fullPath` を検証後の正規配置先に使う |
| 1 | タイトルが50文字超 | **切り詰めない。** Phase 1.5 の create-title へ戻し、[heading-structure-rules.md のリライト6手順](../skills/run-x-longpost-create/references/heading-structure-rules.md)と [title-guidelines.md §1 の構文パターンA〜H](../references/title-guidelines.md) に沿って50文字以内へリライトさせてから再実行する |

### 4.3 出力先

```
${XLP_OUTPUT_DIR}/
```

出力先は `XLP_OUTPUT_DIR` → `${XLP_VAULT_ROOT}/05_Project/X` の2段だけで解決する。両方とも未設定なら停止し、既定値や推測パスへフォールバックしない。

### 4.4 コンテンツ配置ルール（最重要）

| セクション | 配置するコンテンツ | 注意事項 |
|-----------|------------------|---------|
| `# Idea Compass` | 生成時は空（`{{IdeaCompass}}` に空文字） | Phase 3.5 で generate-idea-compass が挿入 |
| `# ハッシュタグ` | 生成時は空（`{{ハッシュタグ}}` に空文字） | 省略可・手動または後処理で追記 |
| `# 投稿文（短文）` | **create-multi-postsの出力をそのままコピー（形式変換禁止）** | `## 投稿N｜フォーマット名` 形式を維持。コードブロック内でも文脈（文節・句読点）での改行を保持（文字数ではなく文脈で改行・1行は目安30-40字程度） |
| `# 投稿文（長文）` の `## Aパターン（文脈改行型）` | 長文A | コードブロック内に配置。先頭行は `# タイトル`・見出し絵文字なし |
| `# 投稿文（長文）` の `## Bパターン（短文改行型）` | 長文B | コードブロック内に配置。先頭行はタイトル（プレーンテキスト） |
| `# 投稿文（分割）` | スレッド分割投稿（生成した場合のみ `# 投稿文（長文）` の後に追記） | スレッド形式そのまま。雛形には含まれない |
| `# メモ（...）` の `## 構造化` | **構造化メモ（文字起こしがある場合はstructure-transcriptの出力）** | 元の文字起こしではなく構造化後のテキストを `"""` 囲みで配置 |
| `## 文字起こし` | 元の文字起こしテキスト（文字起こしがある場合のみ・`"""` 囲み） | 変換前の原文を保存。ない場合は `{{文字起こし}}` に空文字を渡す（プレースホルダーを残さない） |

### 4.5 ファイル構造

ファイル構造の正本は `../assets/output-template.md`（`TEMPLATE-START`/`TEMPLATE-END` マーカー間を expand-template.js で展開）。出力先ディレクトリの直近生成ファイル群の標準形と一致させている。**唯一の雛形はこの `output-template.md` である。** 旧構成（長文A/Bが別見出し1・末尾プロンプト・Excalidraw Data 付き）は plugin へ移植していないため、参照先も代替雛形も存在しない。

生成ファイルの主要セクション構成（順序どおり）:

| セクション | 内容 |
|-----------|------|
| frontmatter | excalidraw-plugin / tags / notetoolbar |
| 図解・サムネイル欄 | 図解 / Xサムネイル（5:2） / noteサムネイル（1280×670px）の記入欄 |
| `# Idea Compass` | 生成時は空。Phase 3.5 で generate-idea-compass が挿入 |
| `# Next Action` | Idea Compase / Text Summary / 図解 / Card化 のチェックリスト |
| `# ハッシュタグ` | 生成時は空（省略可・手動または後処理で追記） |
| `# 投稿文（短文）` | `## 投稿N｜フォーマット名` + テーマ + 個別コードブロック。8投稿 |
| `# 投稿文（長文）` | `## Aパターン（文脈改行型）` と `## Bパターン（短文改行型）`（各コードブロック内） |
| `# タイトル` | 生成タイトル（`- ` 付き） |
| `# キャッチコピー` | 入力キャッチコピー（`- ` 付き） |
| `# メモ（...）` | `## 構造化` の下に構造化メモ（`"""` 囲み） |
| `## 文字起こし` | 元の文字起こし（`"""` 囲み。入力がない場合は空） |

#### 変数一覧（expand-template.js に渡す値）

| 変数名 | 内容 | 空文字 |
|--------|------|--------|
| `{{タイトル}}` | **Phase 1.5 の確定タイトル**（Aパターン先頭・Bパターン先頭・`# タイトル` の3箇所で展開） | 不可 |
| `{{キャッチコピー}}` | 入力キャッチコピー | 不可 |
| `{{投稿文_短文}}` | create-multi-posts の出力全体（8投稿・個別コードブロック付き） | 8投稿なしの場合は空文字 |
| `{{投稿文_長文A}}` | 長文A本文（タイトル行を除く。`##` 見出し含む・文脈改行） | 不可 |
| `{{投稿文_長文B}}` | 長文B本文（タイトル行を除く。Aと同内容で1文1行） | 不可 |
| `{{メモ}}` | 構造化メモ（structure-transcript の出力または手動メモ） | 不可 |
| `{{文字起こし}}` | 文字起こし原文 | ない場合は空文字 |
| `{{IdeaCompass}}` | Phase 3.5 で挿入するため生成時は常に空文字 | 常に空文字 |
| `{{ハッシュタグ}}` | 手動・後処理で追記するため生成時は常に空文字 | 常に空文字 |

### 4.5.1 テンプレート展開と出力手順（絶対）

**Write ツールでファイル本体を直接組み立ててはならない。** ファイル本体は必ず `expand-template.js` による展開結果を使う（手書き組み立ては構造がテンプレートからずれ、`validate-headings.js --file` の終了コード3＝テンプレート構造不一致を招く）。

#### 手順

1. **正規 basename を先に確定する**

`generate-filename.js` を実行し、返却 JSON の `filename` と `fullPath` を保持する。scratch 内でも `filename` をそのまま使う。`validate-headings.js` の F3 は basename を検査するため、仮名は使わない。

2. **テンプレートを scratch の同名ファイルへ展開する**

```bash
node ${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/expand-template.js \
  --template "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/assets/output-template.md" \
  --vars-file "[scratch path]/vars.json" \
  --output "[scratch path]/[generate-filename.js が返した filename]" \
  --json
```

変数が長いため `--vars`（インラインJSON）ではなく `--vars-file` を使う。`--json` を付けると展開結果のメタ情報が JSON で返る。

3. **`missingVars` が空であることを確認する**

`--json` 出力の `missingVars` が空配列（`hasUnresolvedVars` が `false`）であることを確認する。空でなければ未展開のプレースホルダーが残っているので、**そのまま出力しない**。変数を埋めて再展開する。

4. **scratch の展開結果を事前検証する**

```bash
node ${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/validate-headings.js --file "[scratch path]/[generate-filename.js が返した filename]" --strict-h2-count
node ${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/check-no-emoji.js --file "[scratch path]/[generate-filename.js が返した filename]"
```

`--strict-h2-count` を必ず付ける（付けないと H5「見出し2が3〜8個」が警告止まりで PASS 扱いになる）。

`validate-headings.js --file` は F4 で A の Markdown 見出しを除いた本文と B の先頭タイトルを除いた本文を空白・改行正規化して同値比較し、F5 で B の非空本文行が1文1行かを検証する。どちらかが FAIL なら候補は scratch に留め、正規配置先へ昇格させない。

**PASS（終了コード0）してから `${XLP_OUTPUT_DIR}/` へ配置する。** 理由: `${XLP_OUTPUT_DIR}/` は毎時の自動コミット対象であり、FAIL 状態のファイルを先に置くとそのままコミットされて残る。

5. **全検証後に1回だけ正規配置する**

scratch の同名ファイルを `generate-filename.js` が返した `fullPath` へ `mv -f` で配置する。検証前に `fullPath` へ書かない。既存の正規配置済みファイルがある場合も、全検証が PASS するまではその bytes を変更しない。

6. **配置後にもう一度 `--file` 検証を行う**（§4.7「出力後の必須検証」）

### 4.6 00ネタファイル更新

#### 更新対象

```
${XLP_NETA_FILE}
```

#### 更新内容

リストの**最上部**（空のエントリの直下）に新しいエントリを追加：

```markdown
- [ ] [[X長文投稿-prompt作成 - YYYY-MM-DD_[タイトル]]]
```

#### 更新例

**Before:**
```markdown
- [ ] [[X長文投稿-prompt作成 - 2026-01-_]]

---

- [ ] [[X長文投稿-prompt作成 - 2026-01-14_AI開発で...]]
- [x] [[X長文投稿-prompt作成 - 2026-01-13_Claude CodeでSkill...]]
```

**After:**
```markdown
- [ ] [[X長文投稿-prompt作成 - 2026-01-_]]

---

- [ ] [[X長文投稿-prompt作成 - 2026-01-15_新しいタイトル]]
- [ ] [[X長文投稿-prompt作成 - 2026-01-14_AI開発で...]]
- [x] [[X長文投稿-prompt作成 - 2026-01-13_Claude CodeでSkill...]]
```

#### 過去ファイルをリネームする場合

既存の投稿ファイル名を変更するときは、**ファイル名と00ネタファイル内の `[[...]]` リンクを必ず同時に書き換える**（片方だけ直すと Obsidian のリンクが切れる）。

1. 00ネタファイルを読み、旧ファイル名を含む `[[X長文投稿-prompt作成 - YYYY-MM-DD_旧タイトル]]` の行を特定する
2. ファイル本体をリネームする
3. 同じ00ネタファイル内のリンクを新ファイル名に書き換える
4. リネーム後のファイルに `validate-headings.js --file <path> --strict-h2-count` を実行し、F3（ファイル名一致）が PASS することを確認する

### 4.7 チェックリスト

| 項目               | 基準                     |
| ------------------ | ------------------------ |
| 日付が正しいか     | 最新日付+1日             |
| ファイル名が正しいか | 命名規則に準拠。`generate-filename.js` が終了コード0 |
| 出力先が正しいか   | `${XLP_OUTPUT_DIR}/`     |
| 構造が正しいか     | `expand-template.js` 経由で展開済み・`--json` 出力の `missingVars` が空（§4.5.1） |
| 出力前の事前検証   | 一時パスで `validate-headings.js --file <path> --strict-h2-count` が PASS してから出力先へ配置した（§4.5.1） |
| 00ネタ更新されたか | リスト最上部に追記       |
| **見出し構造の絶対ルール** | **`node ${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/validate-headings.js --file "[生成ファイルの絶対パス]" --strict-h2-count` が終了コード0** |

#### 出力後の必須検証

ファイル書き込み後、必ず実行する。

```bash
node ${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/validate-headings.js --file "${XLP_OUTPUT_DIR}/X長文投稿-prompt作成 - YYYY-MM-DD_[タイトル].md" --strict-h2-count
```

主な FAIL と対処（全 check ID は [references/heading-structure-rules.md §3.4](../skills/run-x-longpost-create/references/heading-structure-rules.md)）:

| check ID | 内容 | FAIL時の対処 |
|----------|------|-------------|
| H3 | 見出し1が50文字以内 | Phase 1.5 の create-title へ戻してリライト（切り捨て禁止） |
| H4 | 見出し1の後に見出し2が存在 | optimize-length へ戻して見出し2を3〜8個生成し直す |
| H9 | 見出し2の長さが12〜28字（警告） | optimize-length へ戻して長さを調整する |
| H10 | 見出し2が役割名（FAIL） | optimize-length へ戻して具体的な見出しへ書き換える |
| F1/F2/F3 | Bパターン先頭行・`# タイトル` セクション・ファイル名が見出し1と一致 | 見出し1と同一文字列（F3はサニタイズ後）に揃え直す |

終了コードの意味:

| 終了コード | 意味 | 対処 |
|-----------|------|------|
| 0 | PASS | 次へ進む |
| 1 | FAIL | 上表の check ID に従って修正し再実行 |
| 3 | **テンプレート構造不一致**（`## Aパターン（文脈改行型）` 直後にコードフェンスが無い） | 旧テンプレ形式の可能性がある。新規生成物で出た場合は expand-template.js の展開失敗を疑い、テンプレートから作り直す |

**終了コード0になるまで、完了報告と00ネタファイル更新を行わない。**

---

## 5. 出力サマリー

スキル実行完了時に以下を報告：

```
## 出力結果

- **ファイル**: `${XLP_OUTPUT_DIR}/X長文投稿-prompt作成 - 2026-01-15_[タイトル].md`
- **日付**: 2026-01-15
- **タイトル**: [生成されたタイトル]
- **文字数**: [投稿文の文字数]
- **スレッド数**: [分割数]
- **00ネタ更新**: 完了
```
