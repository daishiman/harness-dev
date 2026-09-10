# ワークフロー図詳細

> 読み込み条件: ワークフローの全体像・フロー差分を確認する時
> 責務: ワークフロー図の実体を保管する唯一の正本。SKILL.md 側は Phase の並びを文で述べるだけで、図を持たない

---

## 文字起こしがある場合（メモ自動生成 → 長文投稿・フル図）

```
[入力] キャッチコピー + 文字起こしテキスト
         │
         ▼
Phase 0: 文字起こし構造化（自動）
└─ LLM: x-longpost-structure-transcript   フィラー除去 + 書き言葉変換 + 構造化メモ生成
         │
         ▼
[自動生成] 構造化メモ（= 従来「# メモ」に手動で貼り付けていた内容）
         │
         ▼  ← ここから parse-input へ渡す（キャッチコピー + 構造化メモ）
┌─────────────────────────────┐
│ Script: calculate-next-date │ ← 日付計算（決定論的）
└─────────────────────────────┘
         │
         ▼
Phase 1: 入力解析
├─ LLM: x-longpost-parse-input            構成要素抽出 + 軸決定
│       ※軸が2つ以上→ユーザーに確認
└─ LLM: x-longpost-resolve-contradictions 矛盾解決（軸を最優先基準）
         │
         ▼
Phase 1.5: タイトル作成（以後この文字列が唯一のタイトル）
└─ LLM: x-longpost-create-title   ネタ性質判定→欲求翻訳→3案生成→validate-title.js→推奨1案を確定
         │
         ▼
Phase 2: 文章生成
├─ LLM: x-longpost-apply-style-genome  スタイルゲノム8レベル適用 + 4原則①②主担当 + AI臭①②③主担当
│                                      ※見出しは出力しない
└─ LLM: x-longpost-optimize-length     2パターン（A/B）生成 + 見出し2作成 + 4原則③④主担当 + AI臭④⑤⑥主担当
                                       ※タイトルは作らない。Phase 1.5 の確定タイトルを一字一句そのまま見出し1に置く
         │
         ▼
┌─────────────────────────────┐
│ Script: count-chars          │ ← 文字数検証（1800〜2200・空白除く・決定論的）
└─────────────────────────────┘
         │
         ▼
Phase 3: 出力整形
├─ LLM: x-longpost-split-thread          スレッド分割
├─ LLM: x-longpost-short-post-optimizer  短文投稿生成（オプション・長文フロー内モード）
└─ LLM: x-longpost-output-file           ファイル出力
         │
         ▼
┌─────────────────────────────┐
│ Script: generate-filename    │ ← ファイル名生成
│ Script: expand-template      │ ← テンプレート展開
│ Script: update-neta-file     │ ← 00ネタ更新
└─────────────────────────────┘
         │
         ▼
Phase 3.5: アイデアコンパス
└─ LLM: x-longpost-generate-idea-compass  00ネタからN/S/W/E×5ノート選定
         │
         ▼
[出力] 投稿ファイル + Idea Compass + 00ネタ更新
```

**メモが既にある場合（従来通り）**: 上記フローの Phase 0 をスキップし、手動メモを parse-input へ渡す。以降は完全に同一（次節にフル図がある）。

---

## 文字起こし → 長文投稿 + 8投稿（同時・分岐図）

```
[入力] キャッチコピー + 文字起こしテキスト + 「8投稿も作成して」指示
         │
         ▼
Phase 0: 文字起こし構造化（自動）
└─ LLM: x-longpost-structure-transcript
         │
         ├──────────────────────────────────────────────────┐
         ▼                                                    ▼
長文投稿フロー（上記フローへ）                        8投稿フロー
Phase 1〜3: parse-input → create-title          Phase 1: create-multi-posts
→ apply-style-genome → optimize-length          → 投稿1〜8出力（各200文字・空白除く）
→ output-file                                   ※長文投稿と同じ構造化メモを使用
         │                                                    │
         └──────────────────────┬───────────────────────────┘
                                  ▼
Phase 3.4: 投稿9｜要約型（必須・MP-C07）
└─ LLM: x-longpost-create-multi-posts §5.3.5  長文パターンAを400〜499文字（空白除く）で要約
                                  ▼
Phase 3.5: アイデアコンパス
└─ LLM: x-longpost-generate-idea-compass
                                  ▼
          [出力] 長文投稿ファイル + Idea Compass + 投稿1〜8 + 投稿9（要約型）
```

8投稿フロー単独の仕様は `run-x-multipost-create`、短文1投稿の最適化は `run-x-shortpost-optimize` を参照する。

---

## メモが既にある場合（従来フロー・フル図）

SKILL.md の「文字起こしがある場合」との違いは Phase 0（文字起こし構造化）がない点のみ。
Script: calculate-next-date 以降は完全に同一。

```
[入力] キャッチコピー + メモ（手動で用意した構造化済みのもの）
         │
         ▼
┌─────────────────────────────┐
│ Script: calculate-next-date │ ← 日付計算（決定論的）
└─────────────────────────────┘
         │
         ▼
Phase 1: 入力解析
├─ LLM: parse-input            構成要素抽出 + 軸決定 + 読者の普遍的欲求
│       ※軸が2つ以上→ユーザーに確認
└─ LLM: resolve-contradictions 矛盾解決（軸を最優先基準）
         │
         ▼
Phase 1.5: タイトル作成
└─ LLM: create-title           ネタ性質判定→欲求翻訳→3パターン生成→最適選定
                               ※以後この文字列が唯一のタイトル（4箇所に同一文字列）
         │
         ▼
Phase 2: 文章生成
├─ LLM: apply-style-genome     スタイルゲノム8レベル適用 + 4原則①②主担当 + AI臭①②③主担当
│                              ※見出しは出力しない
└─ LLM: optimize-length        2パターン（A/B）生成 + 4原則③④主担当 + AI臭④⑤⑥主担当
                               ※タイトルは作らない。確定タイトルをそのまま見出し1に置く
         │
         ▼
┌─────────────────────────────┐
│ Script: count-chars          │ ← 文字数検証（決定論的）
└─────────────────────────────┘
         │
         ▼
Phase 3: 出力整形
├─ LLM: split-thread           スレッド分割
├─ LLM: create-short-post      短文投稿生成（オプション）
└─ LLM: output-file            ファイル出力
         │
         ▼
┌─────────────────────────────┐
│ Script: generate-filename    │ ← ファイル名生成
│ Script: expand-template      │ ← テンプレート展開
│ Script: update-neta-file     │ ← 00ネタ更新
└─────────────────────────────┘
         │
         ▼
Phase 3.5: アイデアコンパス
└─ LLM: generate-idea-compass  00ネタからN/S/W/E×5ノート選定
         │
         ▼
[出力] 投稿ファイル + Idea Compass + 00ネタ更新
```

---

## フロー間の対応表

| フロー | Phase 0 | Phase 1 | Phase 1.5 | Phase 2 | Phase 3 | Phase 3.5 | 掲載場所 |
|--------|---------|---------|-----------|---------|---------|-----------|----------|
| 文字起こし → 長文投稿 | structure-transcript | あり | あり | あり | あり | あり | 本ファイル（フル図） |
| メモ既存 → 長文投稿 | なし（スキップ） | あり | あり | あり | あり | あり | 本ファイル（フル図） |
| 文字起こし → 8投稿のみ | structure-transcript | create-multi-posts のみ | なし | なし | なし | なし | 本ファイル（フル図） |
| 文字起こし → 長文 + 8投稿 | structure-transcript（共有） | 両フロー並行 | 長文のみ | 長文のみ | 長文のみ | 共通 | 本ファイル（分岐図） |
| 短文投稿最適化（1投稿） | なし | short-post-optimizer 4フェーズ | - | - | - | - | 本ファイル（フル図） |
