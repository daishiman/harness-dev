# 21. Source Traceability

## 正本パス

実在する正本ディレクトリ:

```text
xl-skills/doc/【コード共有有】Agent Skill大全 数百本のSkillをり続けた実践知から導いたオーケストレーション設計の概念体系Byまさおさん/
```

実在する元記事 Markdown:

```text
xl-skills/doc/【コード共有有】Agent Skill大全 数百本のSkillをり続けた実践知から導いたオーケストレーション設計の概念体系Byまさおさん/【コード共有有】Agent Skill大全 数百本のSkillをり続けた実践知から導いたオーケストレーション設計の概念体系Byまさおさん.md
```

注記:

- 正規タイトルは元記事本文 8 行目の `Agent Skill大全 数百本のSkillを作り続けた実践知から導いたオーケストレーション設計の概念体系`。
- ユーザー指定文には `Skillり続けた` が含まれていた。
- 実在パスは `Skillをり続けた` で、正規タイトルの `作` が欠落している。
- 設計書では実在パスを正本として扱う。

| 種類 | 表記 | 扱い |
|---|---|---|
| 正規タイトル | `Skillを作り続けた` | 表示名・説明文で優先 |
| 実在パス | `Skillをり続けた` | ファイル参照で優先 |
| ユーザー指定 | `Skillり続けた` | 入力揺れとして記録 |

現時点の source tier:

| tier | 状態 |
|---|---|
| `article-text` | 元記事 Markdown を確認済み |
| `image-derived` | 55 参照 / 53 ユニークを `12` に対応済み |
| `code-unavailable` | 記事中の `skills.zip` / Notion 同梱コードは、このリポジトリ内に現物なし |
| `code-verified` | 未取得のため該当なし |
| `internal` | 本リポジトリ内製の設計書・規約・lint・hook 由来 |
| `external-spec` | 外部公式仕様 URL 由来 |

`source-tier` は互換性維持のため単一フィールドとして扱うが、意味的には「出典種別」と「検証状態」が混在する。量産フローでは必要に応じて `source_kind` / `verification_state` に分解してよい。ただし SKILL.md frontmatter と lint の正本語彙は上記 tier 集合に固定する。

## 画像数

元記事 Markdown の Obsidian 画像参照は 55 点。`12-image-extraction-map.md` に全対応を記録している。

### ユーザー指示「58枚」と実数55の差分

- ユーザー指示: 「58枚」
- 実ファイル数: 55 枚 (= 元記事中の画像参照数)
- ユニーク画像 (バイト/内容ベース): 53 種
- 差分の内訳: 重複画像が 2 ペア存在し、別キャプションで二重計上されていた
  - ペアA: `Obsidian 2026-05-17 15.14.31.png` ↔ `Obsidian 2026-05-17 15.14.41.png` (バイト完全一致 1,659,063 bytes)
  - ペアB: `Pasted image 20260517153432.png` ↔ `Pasted image 20260517153442.png` (内容100%同一の手描き図)
- 真実: 実体 55 ファイル / ユニーク 53 種。「58枚」の根拠は不明で、現物との照合では再現できない。設計書は「実体 55 ファイル・ユニーク 53 種」を正とする。

## 公式情報の追跡

| 公式 URL | 反映先 |
|---|---|
| https://code.claude.com/docs/en/skills | `03`, `04`, `07`, `14`, `16` |
| https://code.claude.com/docs/en/sub-agents | `10`, `15` |
| https://code.claude.com/docs/en/hooks | `10`, `13`, `15` |
| https://code.claude.com/docs/en/settings | `04`, `15` |
| https://code.claude.com/docs/en/permissions | `04`, `13`, `15` |
| https://code.claude.com/docs/en/agent-teams | `05`, `10`, `17` |
| https://code.claude.com/docs/llms.txt | 公式更新確認の起点 |

## 再監査ルール

1. 元記事 Markdown の画像参照数を数える。
2. `12-image-extraction-map.md` の行数と照合する。
3. 公式 docs の該当ページを再取得する。
4. 差分を `fact-change` / `design-impact` / `template-impact` / `runbook-impact` / `breaking-change` に分類する。
5. `16` と `17` を先に更新する。
6. 中核設計ファイルに反映する。
7. `code-unavailable` だった実コードを取得した場合、記事説明由来の判断を `code-verified` へ昇格できるか再監査する。
8. `13-checklists.md` の4条件を再判定する。
