# handout-content-architect (C05) 受入テスト

`P04-C05-01` で **実装前に赤で固定した**受入判定。実装 (P05) が判定基準を
自作の基準へ差し替えられないよう、契約はすべて plan 側のブリーフから起こしてある。

- 検査対象 (build_target): `plugins/guide-doc-generator/agents/handout-content-architect.md`
- 契約の正本: `plugin-plans/guide-doc-generator/briefs/agent-brief-C05.json`
- 併読: `component-inventory.json#C05` / `briefs/RESOLUTION-P03.md` (Y-05 / Y-06 / Y-09) /
  `briefs/RESOLUTION-R21.md` (C46-C59)

## 実行

```bash
python3 -m unittest discover -s plugins/guide-doc-generator/tests/handout-content-architect -p 'test_*.py'
```

Python 3.10+ の標準ライブラリのみ (PyYAML を使わない)。

## ファイル構成

| ファイル | 役割 |
| --- | --- |
| `contract_lib.py` | 判定器。`check_agent(path) -> list[Violation]`。契約定数はすべてブリーフ由来 |
| `test_handout_content_architect_agent.py` | 契約 id ごとに 1 テスト。**実装が無い間は 26 件すべて failure** |
| `test_contract_checker.py` | 判定器自身の検査。受入例が通り、非受入例が対応 id で落ちることを固定。実装に依存せず常に緑 |
| `fixtures/accept/agents/handout-content-architect.md` | 受入例 fixture。**実装ではない** — 判定器が空ゲートでないことを示すためだけの入力 |
| `reject_cases.py` | 非受入例。受入例へ違反を 1 箇所注入し、落ちるべき契約 id を明示する |

sub-agent は実行そのものを機械検査できないため、検査対象は agent 定義 Markdown の
**宣言的契約** (frontmatter / 必須セクション / 責務境界の明記 / 入出力スキーマの宣言) である。
生成された構成データ JSON そのものの合否判定 (brief AC6) は C12
`validate-handout-config.py` の責務で、実行時検査 P06 の担当。ここでは扱わない。

## 契約 id と出典の対応表

| 契約 id | 内容 | 出典 |
| --- | --- | --- |
| AC-C05-1 | build_target の agent 定義が実在する | task-spec `P04-C05-01` acceptance_criterion |
| AC-C05-2 | frontmatter 13 キーの存在と identity (`name` / `kind: agent` / `isolation: fork` / `owner_skill` / `prompt_layer: 7layer`) | brief AC1 / `frontmatter_fields.fields` |
| AC-C05-3 | `tools` が Read, Write ちょうど。Bash / Edit を持たない | brief AC1 / `tools_rationale` / inventory C05.tools |
| AC-C05-4 | `description` が正本文言と一致し「〜したいときに使う」で終わる | brief AC1 / `description` |
| AC-C05-5 | `prompt_ref` が `prompts/R*-design-config.md` を指す | brief `prompt_ref` / AC1 |
| AC-C05-6 | 必須セクション 8 件と ANCHOR_RE 互換の責務アンカー | brief `body_sections` / `lint-agent-prompt-section.py` ANCHOR_RE |
| AC-C05-7 | Prompt Templates が自動起動マーカーか `> ` 引用行を持ち、Self-Evaluation が 5 観点の 1 つ以上に言及 | brief AC2 |
| AC-C05-8 | HTML / CSS / SVG を書かず出力が構成データ JSON 1 個。写像は C11 | brief AC3 / `boundary` |
| AC-C05-9 | `must_not_assume` 5 項目が禁止として明記 | brief AC4 / `input_contract.must_not_assume` |
| AC-C05-10 | 親会話の前提 (参照 HTML の文面・開発計画の文脈) が本文へ混入していない | task-spec acceptance_criterion「親会話の前提を持ち込んだ場合に落ちる検査」/ brief `isolation_rationale` |
| AC-C05-11 | `lead_line` と section `goal` は別フィールドで両方必須、`decision_line` も別 | brief AC5 / procedure 7-8 / C40 |
| AC-C05-12 | date が入力に無ければ日付フィールドを出さず、既定充填は C12 `--normalize` | brief AC7 / procedure 12 / C33-C35 |
| AC-C05-13 | `presentation_order` を自分で導出せず、導出表 (prior_knowledge → order) を複製しない | RESOLUTION-R21 C49 / CR-PRESENTATION-ORDER / brief procedure 2 末尾 |
| AC-C05-14 | `focus_theme` 1-2 件 / `ties_to` / logistics を appendix へ隔離 | R21 C47 C48 / brief procedure 2(a)(b) |
| AC-C05-15 | 冒頭 `flow-overview` は手順の詳細を書かず、件数上限は `config/handout-sections.json` に従う | R21 C46 / brief procedure 2(c) |
| AC-C05-16 | `capability-explainer` の `parts[].slot` を outcome → breakdown → feature、lead_line を機能名から始めない | R21 C51 / brief procedure 2(d) |
| AC-C05-17 | `attainment_level` の範囲 / `dialogue` / `handson` (B17) / `anticipated-qa` / `duration` | R21 C53 C54 C59 / brief procedure 2(e)(f) |
| AC-C05-18 | `must_remember` と `no_need_to_remember` は対。片方だけの入力は blocked | R21 C57 / brief procedure 1 |
| AC-C05-19 | `## Inputs` に hearing_result 14 項目。質問を返さず `blocked_reason` で差し戻す | brief `input_contract.receives` / `boundary` |
| AC-C05-20 | `## Outputs` に戻り値 11 キーと `out_config_path` 1 ファイルのみの宣言 | brief `output_contract` |
| AC-C05-21 | `validate-handout-config.py` / `route-handout-output.py` を自分で実行しない (Bash 非保持) | brief `tools_rationale` / `boundary` (proposer=approver の回避) |
| AC-C05-22 | 部品 id 語彙 (`config/handout-parts.json`) / 用途語彙 / schema を正本から引き、散文へ列挙しない | RESOLUTION-P03 Y-05 Y-06 / brief procedure 3-5 |
| AC-C05-23 | SVG 座標 = C14 / symbol 抽出 = C15 / data URI 化 = C13 の委譲明記 | brief `boundary` |
| AC-C05-24 | 本文に絵文字が無く、構成データへ絵文字を書かない旨がある | brief procedure 11 / C10 |
| AC-C05-25 | `glossary[]` の `{term, plain}` 宣言と本文初出の括弧書き併記、別の専門用語で言い換えない | brief procedure 9 / C16 |
| AC-C05-26 | プリセットを合成せず、セクション追加の判断を `decision_log` へ残す | brief procedure 4 / `failure_modes` |

### brief の acceptance_checks との対応

| brief | 本テスト |
| --- | --- |
| AC1 | AC-C05-2 / AC-C05-3 / AC-C05-4 / AC-C05-5 |
| AC2 | AC-C05-6 / AC-C05-7 |
| AC3 | AC-C05-8 |
| AC4 | AC-C05-9 |
| AC5 | AC-C05-11 |
| AC6 | **本テストの対象外** (生成された構成データ JSON への C12 実行時検査。P06) |
| AC7 | AC-C05-12 |

## 赤の記録 (実装前)

```
Ran 31 tests
FAILED (failures=26)
```

- 26 failures = `test_handout_content_architect_agent.py` の全契約テスト。
  agent 定義が未実装のため `AC-C05-1` はファイル不在で、他 25 件は
  `assertContract` の未実装ガードで落ちる。**errors は 0 件** (import 例外や
  setUpClass 例外で落ちる空テストではない)。
- 5 passes = `test_contract_checker.py`。判定器が受入例を通し、非受入例 28 件を
  それぞれ対応する契約 id で落とすことを固定している。実装の有無に依存しない。

## gaps (P05 で確定が要る点・判断が割れる点)

| id | what | why |
| --- | --- | --- |
| G1 | `description` の正本文言が brief と inventory で 1 箇所ずれている (inventory 側だけ「・R21 の型フィールド」を含む) | AC1 は「brief の description と一致」を要求するが、inventory も同格の正本として参照されている。テストは**どちらか一方に一致すれば受入**とした。P05 でどちらへ寄せるかを決め、片方へ揃えたら `CANONICAL_DESCRIPTIONS` を 1 件へ縮めること |
| G2 | 責務アンカーの id (`R1` か `R-design-config` か) と prompt ファイル名 | brief `open_questions[0]`。`lint-agent-prompt-section.py` の ANCHOR_RE は `R<数字>` しか受け付けないため、テストは ANCHOR_RE 互換であることのみ要求し、id の綴りは固定していない |
| G3 | `prompt_ref` の基準ディレクトリ (owner skill 配下 / plugin 直下 `prompts/`) と実ファイルの存在 | brief `open_questions[1]`。prompt 本体は C01 の build_target 側にあり、この leaf から存在検査すると別 leaf の完成順に依存する。テストはパス形と basename だけを検査する |
| G4 | `model` の値 (`sonnet` 固定 / `inherit`) | brief `open_questions[2]` で未確定。テストは `model` キーの存在のみ要求し値を固定していない |
| G5 | 部品 id を散文へ何件まで書いてよいか | P03 Y-05 は「id 列挙を持たない」とするが件数の閾値を定めていない。テストは **1 行あたり相異なる部品 id 3 件以上を列挙したら違反** (`PART_ID_LINE_MAX = 2`) とした。B17 のような単発の指名は許す |
| G6 | 絵文字判定の正本は C16 `CR-EMOJI` の二層規則だが、本テストは粗い範囲判定 (U+1F000-1FAFF と VS16) を使う | agent 定義 Markdown 自体への簡易検査であり、構成データ生成物に対する判定ではない。★ や ✔ は通る点で CR-EMOJI と方向は一致するが、同一実装ではない |
| G7 | 本文の宣言は正規表現で検出しているため、同義の別表現で書かれると偽陰性になりうる | 宣言的契約を機械検査する以上避けられない。P05 は本 README の対応表にある語彙で書くこと。表現を変えたい場合は先に `contract_lib.py` の該当パターンを更新し、その変更を review 対象にする |
