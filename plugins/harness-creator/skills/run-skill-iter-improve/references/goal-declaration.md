# GOAL DECLARATION (iter 0) 手順

`run-skill-iter-improve` のループ開始前に必ず実施する。これを飛ばした改善ループは
INVARIANT 3 (goal ≠ proxy) 違反であり、score がいくら上がっても失敗として扱う。

goal アンカーの正本は `goal-spec.json` の `goal` / `original_goal` 単一系
(`../../run-goal-elicit/schemas/goal-spec.schema.json`)。CLI の `--goal` は
この正本への**正規化書込 / 読取エイリアス**にすぎず、別系の goal 宣言を持たない
(二重宣言禁止。正本: `../../run-build-skill/references/goal-seek-paradigm.md`
「達成判定 (GOAL VERIFICATION)」節)。

## 手順 (3 ステップ)

### 1. goal 正本の読取 / 正規化

- `eval-log/goal-spec.json` が既にあれば `goal` を読み取る。`--goal` 引数と両方ある
  場合は goal-spec 側を正とし、差分があれば呼び元に矛盾として報告する (上書きしない)。
- goal-spec が無ければ、`--goal` の 1 文を `goal` に、改善対象と経緯を
  `purpose` / `background` に、収束条件を `checklist` に落として goal-spec を生成する
  (`run-goal-elicit` 相当の推定。追加質問はしない)。
- goal は「score X 点以上」のような proxy 文ではなく、「人が見て / 使って何が達成
  されればこの skill は成功か」を観測可能な完了形 1 文で書く。

### 2. proxy 妥当性審問 (Yes | No + 根拠)

「evaluator の score はこの goal の良い代理か?」を **Yes | No + 1 行根拠**で記録する。

- **Yes** → そのままループへ。
- **No** (score が goal の一部しか見ていない) → このループは score を上げても goal に
  届かない。target を当該 evaluator skill に切り替え rubric を goal に寄せて直すのが先。
- **Partial** → goal 達成度の別立て採点 (fan-out agent の報告項目) と収束前の
  GOAL VERIFICATION を必ず有効化する (既定で必須だが、Partial ではスキップ検討自体を禁止)。

### 3. 緩め禁止リスト宣言 → goal-spec 拡張 field 格納

この target で「これをやったら PASS 詐欺」になる操作を列挙し、goal-spec の
`forbidden_loosening[]` (拡張 field、schema 正本は
`../../run-goal-elicit/schemas/goal-spec.schema.json`) へ格納する。

- **一般形はここに再掲しない**: 「evaluator 緩和で score を通す」「score 急上昇を独立
  判定なしで採用する」等の一般形は `../../run-elegant-review/references/convergence-policy.json`
  の `anti_patterns` が正本。`forbidden_loosening[]` には **target 固有の具体形**のみ書く
  (例: 「採点 mode を lenient に固定する」「採点対象 section から X を外す」
  「実走評価を SKILL.md 静的レビューに置換する」)。
- **境界定義**: 手段が target ファイル編集 / spec・入力編集 / 引数 / 環境変数 /
  評価手順そのものの差し替えかを問わず、「採点 mode・threshold・採点対象範囲・評価方法を
  易化して score を通す」効果を持つ操作は全て緩め禁止操作。
- 毎 iter の diagnose でこのリストと照合し、結果を審問ログ
  (`schemas/interrogation-log.schema.json` の `forbidden_loosening_check`) に記録する。

## 記録先

| 成果物 | 置き場所 |
|---|---|
| goal / forbidden_loosening | `eval-log/goal-spec.json` (`goal-spec.schema.json` 準拠) |
| proxy 妥当性審問 (Yes/No+根拠) | run dir (`eval-log/<plugin>/<skill>/iter-improve/<run-id>/`) の iter summary |
| 毎 iter の照合結果 | 同 run dir の `interrogation-log.jsonl` (1 iter 1 行) |
