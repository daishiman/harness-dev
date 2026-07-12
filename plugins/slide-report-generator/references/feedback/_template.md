---
date: YYYY-MM-DD
deck: slide-YYYY-MM-DD-<deck-name>
type: feedback
sr_count_reflected: 0
escalations: []
---

# フィードバックログ — <デッキ名>

> **運用テンプレ** (SR-15, 2026-05-09 整備)
> 1 デッキ 1 ファイル原則。発見した問題と反映先を集約する。

## §1 発見した問題

問題 ID は `SR-NN`（スキル反映）/ `L-NN`（このデッキ限り）/ `E-NN`（大規模変更エスカレーション）で採番する。

| ID | 種別 | 発見 | 出典 |
|---|---|---|---|
| SR-01 | スキル反映 | （例: スライド検出ロジックのバグ） | 04-02 F-01 |
| L-01  | デッキ限り | （例: 特定スライドの誤字） | review log |
| E-01  | エスカレーション | （例: 章構成の全面再設計） | 04-09 |

## §2 分類（P0 / P1 / P2 / Esc）

- **P0**（即反映）: バグ・前提を壊す問題
- **P1**（順次反映）: 次回再発リスクあり、テンプレ・ガイド更新で防止
- **P2**（フォローアップ）: 議論を要する変更、記述のみ反映
- **Esc**（エスカレーション）: アーキテクチャ・章構成等の大規模変更（別プロンプト責務）

## §3 反映先

| ID | 反映先ファイル | 追加箇所 |
|---|---|---|
| SR-NN | scripts/xxx.js | 関数 fooBar の正規表現修正 |
| SR-NN | references/yyy.md | 末尾「§N 新セクション」追加 |

## §4 適用内容サマリ（差分概要）

- ファイル名: 行数差 / 趣旨
- 例: `scripts/check-consistency.js` +40 行 / SVG viewBox 16:9 検査追加

## §5 大規模変更エスカレーション

スキル運用責務外の変更を別プロンプトに引き継ぐ。

| ID | 内容 | 引き継ぎ先 | 理由 |
|---|---|---|---|
| E-NN | （例: outline 再設計） | 02-08 outline 再生成プロンプト | 構成全体の影響評価が必要 |

## §6 resource-map drift 確認結果

- 実ファイル一覧 vs `references/resource-map.md` の差分:
  - 追加ファイル: なし / N 件
  - 削除ファイル: なし / N 件
  - 名称変更: なし / N 件
- ドリフトがあれば `references/resource-map.md` を別プロンプトで更新する。

---

## 使用方法

新規 deck のフィードバックを書く際は本ファイルを `cp` してリネームする:

```bash
cp .claude/skills/presentation-slide-generator/feedback/_template.md \
   .claude/skills/presentation-slide-generator/feedback/YYYY-MM-DD-<deck-name>-feedback.md
```

frontmatter の `date` / `deck` / `sr_count_reflected` / `escalations` を埋める。
