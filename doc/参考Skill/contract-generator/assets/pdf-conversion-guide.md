# 契約書変換ガイド（クライアント提出用）

## 概要

契約書の変換フローを定義します。クライアント提出に最適化された3段階フローを採用。

```
Markdown → DOCX → PDF
（原本）   （調整）  （提出）
```

| 段階 | 形式 | 用途 |
|------|------|------|
| **原本** | Markdown | Git管理、Obsidian連携、バージョン管理 |
| **中間** | DOCX | レイアウト調整、クライアント編集可、確認用 |
| **最終** | PDF | 署名・押印・保存・提出用 |

---

## 必要ツール

### pandoc（必須）

```bash
# macOS
brew install pandoc

# Windows
winget install pandoc

# Ubuntu/Debian
sudo apt install pandoc
```

### リファレンスDOCX（必須）

`reference.docx` をカスタマイズして使用。スタイル定義のみを参照。

---

## 変換コマンド

### 基本変換（Markdown → DOCX）

```bash
pandoc contract.md \
  -o contract.docx \
  --reference-doc=reference.docx
```

### 詳細オプション付き

```bash
pandoc contract.md \
  -o contract.docx \
  --reference-doc=reference.docx \
  --toc=false \
  --standalone \
  -V lang=ja
```

### DOCX → PDF

Microsoft Word または LibreOffice で開き、PDF出力：

```bash
# LibreOffice CLI（自動化用）
libreoffice --headless --convert-to pdf contract.docx

# macOS（Wordインストール済み）
open contract.docx  # Word で開いてPDF出力
```

---

## リファレンスDOCX仕様

### 作成手順

1. **空のDOCXを作成**
   ```bash
   pandoc --print-default-data-file reference.docx > reference.docx
   ```

2. **Word/LibreOfficeでスタイル編集**
   - ファイルを開く
   - スタイルパネルで以下を設定

3. **スタイル定義を保存**
   - 上書き保存

### 必須スタイル設定

| スタイル名 | 設定 |
|-----------|------|
| **Normal** | 游明朝 11pt、行間1.5倍、両端揃え |
| **Heading 1** | 游明朝 16pt Bold、中央揃え、下線、前後30pt |
| **Heading 2** | 游明朝 14pt Bold、左揃え、前20pt/後10pt |
| **Heading 3** | 游明朝 12pt Bold、左揃え、前15pt/後8pt |
| **Table** | 游明朝 10pt、罫線1pt黒 |
| **Footer** | 游明朝 9pt、中央揃え、ページ番号 |

### ページ設定

| 項目 | 値 |
|------|-----|
| **用紙** | A4縦（210mm × 297mm） |
| **余白** | 上下左右 25mm |
| **ヘッダー** | 15mm |
| **フッター** | 15mm |

### フォント優先順位

```
1. 游明朝 Medium（推奨）
2. MS 明朝
3. ヒラギノ明朝 ProN
```

---

## ディレクトリ構造

```
contract-generator/
├── assets/
│   ├── pdf-conversion-guide.md  # このガイド
│   └── reference.docx           # リファレンスDOCX
├── output/
│   ├── contract.md              # 生成されたMarkdown（原本）
│   ├── contract.docx            # 変換されたDOCX（確認用）
│   └── contract.pdf             # 最終PDF（提出用）
```

---

## 変換スクリプト（自動化）

### convert-to-docx.mjs

```javascript
#!/usr/bin/env node
/**
 * Markdown → DOCX 変換スクリプト
 * Usage: node convert-to-docx.mjs <input.md> [output.docx]
 */
import { execSync } from 'child_process';
import { existsSync } from 'fs';
import { basename, dirname, join } from 'path';

const input = process.argv[2];
const output = process.argv[3] || input.replace('.md', '.docx');
const referenceDoc = join(dirname(input), '../assets/reference.docx');

if (!input) {
  console.error('Usage: node convert-to-docx.mjs <input.md> [output.docx]');
  process.exit(1);
}

if (!existsSync(input)) {
  console.error(`Error: Input file not found: ${input}`);
  process.exit(1);
}

const cmd = [
  'pandoc',
  `"${input}"`,
  '-o', `"${output}"`,
  existsSync(referenceDoc) ? `--reference-doc="${referenceDoc}"` : '',
  '--standalone',
  '-V', 'lang=ja'
].filter(Boolean).join(' ');

console.log(`Converting: ${basename(input)} → ${basename(output)}`);
execSync(cmd, { stdio: 'inherit' });
console.log(`✓ Output: ${output}`);
```

---

## チェックリスト

### 変換前確認

- [ ] 契約当事者名が正しく入力されている
- [ ] 契約日付が入力されている
- [ ] プレースホルダー（【　】）がすべて埋められている
- [ ] 条文番号が連番になっている
- [ ] 署名欄のスペースが確保されている
- [ ] 別紙の取引条件が記入されている

### DOCX確認

- [ ] フォントが正しく表示されている
- [ ] 表のレイアウトが崩れていない
- [ ] ページ区切りが適切な位置にある
- [ ] ヘッダー・フッターが表示されている
- [ ] 署名欄が1ページに収まっている

### PDF確認

- [ ] フォントが埋め込まれている
- [ ] 印刷プレビューで問題がない
- [ ] ファイルサイズが適切（通常100KB〜1MB）

---

## レイアウト崩れ防止

DOCX/PDF変換時のレイアウト崩れを防ぐための対策。

### 事前検証スクリプト

変換前に `validate-layout.mjs` を実行して問題を検出：

```bash
# 基本検証
node scripts/validate-layout.mjs contract.md

# 警告もエラーとして扱う（厳格モード）
node scripts/validate-layout.mjs contract.md --strict
```

### 検証項目

| カテゴリ | チェック内容 | 推奨対処 |
|----------|-------------|----------|
| **文字数** | 会社名40文字、住所60文字以内 | 改行または略称使用 |
| **表セル** | セル内容50文字以内 | セル分割または改行 |
| **特殊文字** | 機種依存文字、丸数字 | 標準文字に置換 |
| **プレースホルダー** | 【　】、○○等の残存 | 必要情報を入力 |
| **署名欄** | 甲・乙・印・住所・氏名 | 必須要素を確認 |
| **ページ区切り** | 見出しと本文の分離 | 改ページ位置を調整 |

### 推奨文字数制限

| 項目 | 最大文字数（半角換算） | 理由 |
|------|----------------------|------|
| 会社名 | 40 | 表のセル幅に収める |
| 住所 | 60 | 1行に収める |
| 人名 | 20 | 署名欄に収める |
| 表セル | 50 | セル内で折り返さない |
| 1行 | 80 | A4横幅に収める |

### 改ページ制御

署名欄が2ページに分割されないよう、直前に改ページを挿入：

**Markdown記法:**
```markdown
---

<div style="page-break-before: always;"></div>

## 署名欄
```

**pandoc拡張記法:**
```markdown
\newpage

## 署名欄
```

### 表の崩れ防止

**原則:**
- 1つの表は10行以内
- セル内の改行は避ける
- 列数は5列以内

**長い表の分割例:**
```markdown
### 業務内容（1/2）

| No | 業務名 | 内容 |
|----|--------|------|
| 1  | ...    | ...  |

### 業務内容（2/2）

| No | 業務名 | 内容 |
|----|--------|------|
| 6  | ...    | ...  |
```

### 署名欄の固定サイズ

署名欄は十分な余白を確保：

```markdown
## 署名欄

本契約の成立を証するため、本書2通を作成し、甲乙記名押印の上、各1通を保有する。

令和　　年　　月　　日

**甲（発注者）**

住所：

名称：

代表者：　　　　　　　　　　　　　　　　　　　　　㊞


**乙（受注者）**

住所：

氏名：　　　　　　　　　　　　　　　　　　　　　　㊞
```

### 機種依存文字の回避

| 使用禁止 | 代替文字 |
|----------|----------|
| ①②③ | (1)(2)(3) または 1. 2. 3. |
| Ⅰ Ⅱ Ⅲ | 第1 第2 第3 |
| ㈱ ㈲ | 株式会社 有限会社 |
| ～ (波ダッシュ) | 〜 (全角チルダ) |
| − (全角マイナス) | ー (長音) |

---

## トラブルシューティング

### フォントが表示されない

**原因**: リファレンスDOCXのフォントがインストールされていない

**対処**:
```bash
# フォント確認（macOS）
fc-list | grep -i "游明朝\|mincho"

# 代替フォントに変更
# reference.docx のスタイルを MS 明朝に変更
```

### 表がはみ出る

**原因**: 列幅の自動調整が効いていない

**対処**:
1. DOCXをWordで開く
2. 表を選択 → レイアウト → 自動調整 → ウィンドウに合わせる

### ページ区切りが不自然

**原因**: 段落設定が引き継がれていない

**対処**:
1. reference.docx の Heading 2 スタイルを編集
2. 「段落」→「改ページと改行」→「段落前で改ページ」をオフ

### 日本語が文字化けする

**原因**: pandocのロケール設定

**対処**:
```bash
# 環境変数設定
export LANG=ja_JP.UTF-8
pandoc contract.md -o contract.docx --reference-doc=reference.docx
```

---

## ベストプラクティス

### 原本管理（Markdown）

- Git でバージョン管理
- 変更履歴をコミットメッセージに記録
- ファイル名に日付・バージョンを含める
  - 例: `取引基本契約書_日工株式会社_v1.0_2026-01-20.md`

### 確認用（DOCX）

- クライアント確認用に送付可能
- 編集トラッキング機能で変更管理
- コメント機能でフィードバック収集

### 提出用（PDF）

- 署名・押印後にスキャン → PDF/A形式で保存
- ファイル名: `取引基本契約書_甲乙_締結日.pdf`
- 電子署名対応の場合は PDF 1.7 以上

---

## 関連ファイル

| ファイル | 説明 |
|----------|------|
| `assets/reference.docx` | スタイル定義用リファレンスDOCX |
| `assets/contract-template-variables.md` | 変数一覧とMustache構文 |
| `schemas/contract-input.json` | 入力スキーマ定義 |
| `scripts/validate-layout.mjs` | レイアウト崩れ事前検証 |
| `scripts/convert-to-docx.mjs` | Markdown→DOCX変換 |
| `output/` | 生成ファイル出力先 |

---

*このガイドは契約書生成スキル v3.3.0 の一部です。*
