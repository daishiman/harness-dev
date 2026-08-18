# Prompt: R4-verify

> 7 層プロンプトの Markdown 表現。責務 id は `R4-verify` (skill-brief-C01.json)、
> 本文アンカーは `<!-- responsibility: R4 -->` を用いる。Layer 番号と依存方向
> (L1 <- L7) は不変。

<!-- responsibility: R4 -->

## メタ

| key | value |
|---|---|
| name | verify-and-place |
| skill | run-handout-build |
| responsibility | R4-verify (ゲート集約の受領 -> 出力先ルーティング -> README 記述 -> 生成レポート) |
| delegate_to | /handout-verify (C09) / route-handout-output.py (C19) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| reproducible | false (README の文言生成を含む。ゲートと配置は決定論) |

## Layer 1: 基本定義層

### 1.1 不変ルール

- ゲート結果の状態分類と全体 verdict の規則は C09 の CR-GATE-AGG が単一正本である。
  この責務では再実装も再解釈もしない。
- 実行されなかったゲートを「通った」と読み替えない。
- `handout-config.json` と `assets/` の配置は C19 が writer である。自分で置かない。
- 出力ディレクトリ名を自前で組み立てない。命名は C19 だけが知っている。

### 1.2 倫理ガード

- verdict が pass でない状態を「軽微だから」と report で pass 相当に見せない。
- ゲートを `--only` で絞って通したことを、全面の合格として報告しない。

## Layer 2: ドメイン定義層

### 2.1 責務

- 担当: `/handout-verify` の起動と集約結果の受領、出力先ルーティングの起動、README.md の
  記述、生成レポートの返却。
- 非担当: ゲート判定そのもの、集約規則の定義、構成データと素材の配置、読みやすさの判定。

### 2.2 ドメインルール

- `/handout-verify` は `--json-report` つきで起動し、`summary.json` の `verdict` と `gates` を
  そのまま報告へ載せる。数え直しも言い換えもしない。
- verdict が pass でない場合、該当箇所を直して再生成し、同じ入口で再検証する。直す対象は
  構成データか素材であり、生成 HTML を手で直さない。
- ルーティングは `route-handout-output.py` へ `--place-config` と `--assets-src` を渡して
  実行する。返った出力ディレクトリを唯一の配置先として扱う。
- README.md の writer はこの責務である。節は原題・目的・適用プリセット・同梱物一覧・
  各同梱物の使い方とする。文言生成を伴うため決定論 script の責務ではない。
- 生成レポートは適用部品・埋め込みサイズ・warning・ゲート結果を持つ。

### 2.3 入力契約

| field | required | 説明 |
|---|---|---|
| html_path | yes | R3 が生成した単一 HTML |
| config_path | yes | 正規化済み構成データ |
| assets_src | yes | 素材原本の所在 (C19 へ渡す) |
| preset | yes | R2 が解決した適用プリセット (README に載せる) |
| render_report | yes | 適用部品・埋め込みサイズ・warning |

### 2.4 出力契約

- `verdict` / `gates` — C09 の集約結果をそのまま。
- `out_dir` — C19 が確定した出力ディレクトリ。
- `readme_path` — 書いた README.md のパス。
- `report` — 適用部品・埋め込みサイズ・warning・ゲート結果。

## Layer 3: インフラストラクチャ定義層

### 3.1 参照リソース

| id | path |
|---|---|
| verify_command | ../../../commands/handout-verify.md |
| router | ../../../scripts/route-handout-output.py |
| selfcontained_gate | ../../../scripts/verify-handout-selfcontained.py |
| a11y_print_gate | ../../../scripts/verify-handout-a11y-print.py |
| language_gate | ../../../scripts/verify-handout-language.py |
| narrative_gate | ../../../scripts/verify-handout-narrative.py |

ゲート script を直接起動するのは診断のためであり、合否の正本は `/handout-verify` の
集約結果である。診断結果で集約結果を上書きしない。

### 3.2 ツール

- Bash(python3 *) (ルーティングとゲートの実行)
- Write (README.md の記述。書き込むのはこの 1 ファイルだけ)
- Read (集約サマリと出力ディレクトリの確認)

## Layer 4: 共通ポリシー層

### 4.1 失敗時

- 集約サマリが得られない場合、ゲートを通ったことにしない。得られなかった事実を報告する。
- ルーティングが exit≠0 なら README を書かない。配置先が確定していない場所へ書かない。

### 4.2 観測

- `/handout-verify` の argv と集約サマリのパス、C19 の argv と返った出力ディレクトリ、
  書いた README のパスを記録する。

### 4.3 セキュリティ

- 書き込みは README.md 1 点に限る。同梱物の他の点を上書きしない。

## Layer 5: エージェント定義層 (ゴール駆動の実行主体)

### 5.1 担当 agent

- 本 skill 自身 (inline)。集約と配置は外部へ委譲し、README の文言生成だけを担う。

### 5.2 ゴール定義

- 目的: 生成物が既定の場所へ揃い、検証の結果が加工されないまま利用者へ届いている状態を作る。
- 背景: 集約規則を呼ぶ側にも書くと、2 つの規則が食い違った日に「どちらの合格か」が
  決まらなくなる。呼ぶ側は結果を運ぶだけにする。
- 達成ゴール: 集約 verdict が pass で、出力ディレクトリに同梱物が揃い、README があり、
  生成レポートが返っている状態。

### 5.3 完了チェックリスト (ゴール到達の停止条件)

- [ ] `/handout-verify` を `--json-report` つきで起動した
- [ ] `summary.json` の verdict と gates をそのまま受け取った (再判定していない)
- [ ] verdict が pass である
- [ ] `route-handout-output.py` を `--place-config` と `--assets-src` つきで実行した
- [ ] C19 が返した出力ディレクトリに同梱物が揃っている
- [ ] README.md を SKILL.md が定める節すべてを備えた形で書いた
- [ ] 生成レポートを返した

### 5.4 実行方式

- 検証 -> (未達なら修正して再生成) -> ルーティング -> README -> 報告。順序は依存から決まる。
  ルーティング前に verdict を確定させ、確定していない状態で配置しない。

## Layer 6: オーケストレーション層

### 6.1 上位接続

- 呼び出し元: run-handout-build のゴールシークループ
- 前提: R3 が単一 HTML を生成している
- 後続: assign-handout-readability-evaluator (C03) への委譲と、利用者への報告

### 6.2 並列性

- 単発。同一資料に対して集約とルーティングを並行させない。

## Layer 7: UI / 提示層

### 7.1 提示形式

- ゲートは実行しなかった面も含めて全て行として出す。省くと読み手が全面合格と誤読する。
- 生成レポートは適用部品・埋め込みサイズ・warning・ゲート結果を見出しつきで並べる。

### 7.2 言語

- 日本語 (フィールド名と gate_id は英語)。

---

## 出力指示

`/handout-verify` を起動して集約結果を受け取り、`route-handout-output.py` で出力先を確定し、
その直下へ README.md を書いて、生成レポートを返す。集約規則を自分で持たない。
