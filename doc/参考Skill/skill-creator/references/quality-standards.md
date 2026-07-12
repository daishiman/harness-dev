# 品質基準（§8）

> 18-skills.md §8 の要約
> **相対パス**: `references/quality-standards.md`
> **原典**: `docs/00-requirements/18-skills.md` §8

---

## 8.1 スキル作成時のチェックリスト

| チェック項目                                      | 検証方法                                         |
| ------------------------------------------------- | ------------------------------------------------ |
| SKILL.md が 500 行以内                            | `wc -l SKILL.md`                                 |
| YAML frontmatter が有効                           | quick_validate.js                                |
| name がハイフンケース（最大64文字）               | 正規表現で検証                                   |
| description が 1024 文字以内                      | 文字数カウント                                   |
| description に Anchors と Trigger が含まれる      | 文字列検索                                       |
| 不要な補助ドキュメントがない                      | README.md 等の不在確認                           |
| references/ のファイルが SKILL.md からリンク      | grep で検証                                      |
| agents/\*.md が「仕様書」になっている             | 役割/入力/出力/制約/参照が揃っているか           |
| agents に知識本文が埋め込まれていない             | 大段落がある場合 references へ移動               |
| references/ は SKILL.md から直リンク              | grep で検証                                      |
| 制約がある場合は検証スクリプトが存在              | scripts/ で自動検証できるか                      |
| Task名が目的に合致している                        | analyze/design/validate の固定名に依存していない |
| agents/scripts/references/assets が責務単位で分離 | 複数責務が混在していないか                       |
| 動的に変わる数値がハードコードされていない        | リソース数・タイプ数等は「全」「定義済み」で表現 |

---

## 8.2 ベストプラクティス要約

| カテゴリ               | ベストプラクティス                                            |
| ---------------------- | ------------------------------------------------------------- |
| 簡潔さ                 | 説明より例を優先、Claude が既に知っていることは書かない       |
| 知識圧縮アンカー       | 目標達成に必要十分な著名書籍/ドキュメントで知識体系を圧縮参照 |
| 自由度                 | タスクの脆弱性に応じて具体性を調整                            |
| Progressive Disclosure | SKILL.md を軽量に、詳細は references/ に                      |
| 重複回避               | 情報は SKILL.md か references/ のどちらか一方のみ             |
| スクリプト             | 繰り返し書くコードはスクリプト化、必ずテスト                  |
| 発動条件               | description に明確に記述（本文ではなく）                      |
| 相対パス               | references/ へのリンクは相対パスで記述                        |
| 責務分離               | agents/scripts/references/assets は単一責務で分割             |
| **動的数値の回避**     | リソース数・タイプ数等の具体的数値をハードコードしない        |

---

## 8.3 検証コマンド

### 構造検証

```bash
node scripts/quick_validate.js .claude/skills/<skill-name>
```

### 詳細検証（verbose モード）

```bash
node scripts/quick_validate.js .claude/skills/<skill-name> --verbose
```

---

## 8.4 quick_validate.js の検証項目

| 検証項目                     | エラー/警告 | 説明                                       |
| ---------------------------- | ----------- | ------------------------------------------ |
| SKILL.md の存在              | エラー      | 必須ファイルが存在しない                   |
| 行数制限（500行）            | エラー      | SKILL.md が長すぎる                        |
| YAML frontmatter の存在      | エラー      | frontmatter が見つからない                 |
| name フィールドの存在        | エラー      | 必須フィールドが欠落                       |
| name のハイフンケース        | エラー      | 命名規則違反                               |
| name とディレクトリ名の一致  | 警告        | 不一致の場合は要確認                       |
| description フィールドの存在 | エラー      | 必須フィールドが欠落                       |
| description の文字数（1024） | エラー      | 長すぎる                                   |
| description の角括弧         | エラー      | `<` `>` が含まれている                     |
| Anchors の存在               | 警告        | 知識圧縮アンカーが含まれていない可能性     |
| Trigger の存在               | 警告        | 発動条件が含まれていない可能性             |
| 禁止ファイルの不在           | エラー      | README.md 等が存在する                     |
| references/ のリンク         | 警告        | ファイルが SKILL.md からリンクされていない |
| agents/\*.md のテンプレ準拠  | 警告        | 5セクション構造が不足                      |

---

## 8.5 終了コード

| コード | 意味         | 説明                     |
| ------ | ------------ | ------------------------ |
| 0      | 成功         | すべての検証をパス       |
| 1      | 一般エラー   | スクリプト実行時エラー   |
| 2      | 引数エラー   | パスが指定されていない等 |
| 3      | ファイル不在 | 指定パスが存在しない     |
| 4      | 検証失敗     | 1つ以上のエラーがある    |

---

## 8.6 検証結果の解釈

### すべてパスした場合

```
スキルを検証中: .claude/skills/my-skill
結果: ✓ 検証成功 (10項目パス, 0エラー, 0警告)
```

→ 品質基準を満たしている。実際のタスクでテスト可能。

### エラーがある場合

```
スキルを検証中: .claude/skills/my-skill

✗ エラー:
  - SKILL.md が 500 行を超えています (650行)
  - name がハイフンケースではありません: MySkill

結果: ✗ 検証失敗 (8項目パス, 2エラー, 1警告)
```

→ エラーを修正してから再検証が必要。

### 警告のみの場合

```
スキルを検証中: .claude/skills/my-skill

⚠ 警告:
  - description に Anchors が含まれていない可能性があります

結果: ✓ 検証成功 (9項目パス, 0エラー, 1警告)
```

→ 警告は推奨事項。必須ではないが、対応を検討する。

---

## 8.7 テストカバレッジ exemption ルール

### P41 Exemption（v8 Function Coverage）

Vitest の v8 カバレッジプロバイダ使用時、インライン arrow function がカウント対象となり Function Coverage が実態と乖離する場合がある。

| 条件 | 対応 |
| --- | --- |
| v8 プロバイダ + インラインコールバック | Function Coverage 0% でも自動 FAIL としない |
| 記録必須 | Phase 7 成果物に「P41 exemption 適用」を明記 |
| handler-scope 推奨 | 複数ハンドラ集約ファイルはハンドラ単位でカバレッジ判定 |

> **正本**: `task-specification-creator/references/coverage-standards.md` の P41 Exemption セクション

---

## 関連リソース

- **作成プロセス**: See [creation-process.md](creation-process.md) / [update-process.md](update-process.md)
- **フィードバック**: See [feedback-loop.md](feedback-loop.md) - §7
- **命名規則**: See [naming-conventions.md](naming-conventions.md) - §9-10
