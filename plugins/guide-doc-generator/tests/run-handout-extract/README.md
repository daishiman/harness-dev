# run-handout-extract (C02) 受入テスト — 赤で固定した契約

対象 build_target: `plugins/guide-doc-generator/skills/run-handout-extract/` (P05 で実装)

```bash
python3 -m unittest discover -s plugins/guide-doc-generator/tests/run-handout-extract -p 'test_*.py'
```

Python 3.10+ 標準ライブラリのみ (`unittest`)。PyYAML は使わず、SKILL.md の
frontmatter は `contract_lib.py` の YAML 部分集合パーサで読む。

## 何を検査しているか

C02 は skill component なので、テストは skill の実行そのものではなく
**SKILL.md の宣言的契約**を機械検査する。C02 の核心は**ラウンドトリップ性**
(構成データ → HTML → 逆抽出 → 構成データ が意味的に一致すること) であり、
その粒度・不変条件・境界を SKILL.md の宣言として固定した。

- frontmatter (identity / responsibilities / combinators / goal_seek / feedback_contract / depends_on / allowed-tools)
- 本文の必須セクション骨格
- 参照する決定論 script 4 本のパスが実在すること
- **逆抽出の入出力契約** — R1-scan の委譲先と起動引数、R2-complete の補完規律
  (推測しない / 3 点セット報告 / fidelity 区別)、R3-roundtrip の等価粒度と差分提示
- 責務境界 (資料内容を書き換えない / 生成は C07 / HTML の parse は C20)

## ファイル構成

| ファイル | 役割 | 実装前の状態 |
|---|---|---|
| `contract_lib.py` | 契約チェッカ本体 (判定器)。`check_skill(skill_dir) -> [Violation]` | — |
| `reject_cases.py` | 非受入例の定義 (受入例へ 1 箇所だけ違反を注入する固定入力 31 件) | — |
| `fixtures/accept/` | 受入例。契約を満たす SKILL.md + prompts 3 件 + script 実体 4 件 | — |
| `test_contract_checker.py` | 判定器が受入例を通し非受入例を落とすことを固定 (15 件) | **緑** (実装に依存しない) |
| `test_run_handout_extract_skill.py` | 実 build_target への契約テスト (契約 id ごとに 1 メソッド、31 件) | **赤** |

`test_contract_checker.py` が緑であるのは意図どおりで、
「`test_run_handout_extract_skill.py` が使う判定器が、何も検出しない空ゲートでは
ないこと」を先に固定するためにある。加えて
`TestContractsAreDerivedFromBriefs` が、テスト側の契約定数 (責務 id / script 4 本 /
checklist / goal_seek / criteria / depends_on / build_target) を
`skill-brief-C02.json` と `component-inventory.json#C02` に突き合わせている。
テストが正本から乖離した独自基準を持つことを、これで機械的に防いでいる。

## 契約 id と出典の対応表

`skill-brief-C02.json` に `AC-C02-*` の採番は存在しないため、本テストで採番した
(`gaps` 参照)。「出典」欄のファイルはすべて `plugin-plans/guide-doc-generator/` 配下。

| 契約 id | 内容 | 出典 |
|---|---|---|
| AC-C02-1 | build_target に SKILL.md が実在する | task-spec `P04-C02-01.md` acceptance_criterion / inventory `C02.build_target` |
| AC-C02-2 | `name=run-handout-extract` / `prefix=run` / `kind=run` / `hierarchy=L1` | brief `skill_name` / `prefix` / `kind` / `hierarchy_level` |
| AC-C02-3 | description が「〜したいときに使う」形で、逆抽出 / HTML / 構成データ の語彙を持つ | brief `trigger_conditions` + repo の run 系 SKILL.md 慣行 |
| AC-C02-4 | responsibilities が R1-scan / R2-complete / R3-roundtrip の 3 件ちょうど、全て `prompt_required: true` | brief `responsibilities` |
| AC-C02-5 | `responsibility_refs` が `prompts/<R-id>.md` を指し実在する | inventory `goal_seek.engine=inline` の配線 (repo 慣行) |
| AC-C02-6 | combinators = with-goal-seek / with-feedback-contract、goal_seek = inline / subagent / 5 | inventory `C02.combinators` / brief `goal_seek` |
| AC-C02-7 | feedback_contract に IN1 (inner/script) と OUT1 (outer/test) が**過不足なく** | inventory `C02.feedback_contract.criteria` |
| AC-C02-8 | 必須セクション: Purpose & Output Contract / ゴールシーク実行 (6 サブ節) / Criteria acceptance / Gotchas | repo の run 系 SKILL.md 骨格 (C01 テストと同一) |
| AC-C02-9 | `## Criteria acceptance` が IN1 / OUT1 に言及 | 同上 + inventory criteria |
| AC-C02-10 | `deterministic_checks` の 4 script が `script_refs` にあり参照パスが実在する | brief `deterministic_checks` |
| AC-C02-11 | HTML の走査は C20 が唯一の実装。skill は自前で parse しない (`html.parser` / `BeautifulSoup` 等の記述を持たない) | `script-brief-C20.json` `single_writer`「C02 skill も C11 も自前で HTML を parse しない」 |
| AC-C02-12 | round-trip は**正規化後の構成データ等価**で判定。比較対象射影は provenance を除いた残り。HTML のバイト一致は課さない | C20 `roundtrip_granularity.verdict` / `comparable_projection` / `command-brief-C08.json` behavior 3 |
| AC-C02-13 | `lead_line` / `judgment_axis` / section goal / `reader` / `prior_knowledge_level` / `essential_problem` / `doc_type` はマーカーが無い限り推測せず null で残す | C20 `heuristic_fallback.never_guessed` (7 項目そのまま) |
| AC-C02-14 | 復元不能箇所を キーパス / 理由 / 補完方針 の 3 点セットで列挙。補完方針は 推測値の充填 / 空のまま残置 / 利用者への確認 の 3 択。黙って欠落させない | C08 behavior 5 / failure_modes「復元不能な意味情報がある」 |
| AC-C02-15 | 推測で埋めた値と実読み取り値を fidelity (`exact` / `heuristic`) で区別。`W-EXTRACT-HEURISTIC` へ言及 | C20 `report_shape` / `heuristic_fallback.reporting` / C08 behavior 5 |
| AC-C02-16 | Purpose & Output Contract に構成データ JSON と逆抽出レポート 3 要素 (復元した部品一覧 / 復元不能箇所と採った補完 / round-trip 差分) | brief `output_contract` |
| AC-C02-17 | 資料内容の書き換え・改善提案をしない | brief `boundary` / C08 `boundary` |
| AC-C02-18 | 生成は C07 の責務。構成データを出すところで止まり `/handout-build` を案内する | C08 behavior 8 / `boundary` |
| AC-C02-19 | `validate-handout-config.py` に FAIL したとき値を捏造せず、欠落キーパスを提示し、空 / 穴つきの構成データを成功として返さない | C08 behavior 6 / failure_modes / C20 `fail_semantics.downstream` |
| AC-C02-20 | 差分は `E-ROUNDTRIP-DIFF` + JSON Pointer + expected + actual で全件提示。差分ありを等価と読める要約にしない | C20 `stderr` / `compare_procedure` 5 / C08 behavior 7 |
| AC-C02-21 | `depends_on` に C11 / C12 / C16 / C20 | inventory `C02.depends_on` |
| AC-C02-22 | allowed-tools が Read / Write / Bash を含む | brief `deterministic_checks` (Bash 起動) + 出力 2 ファイル (Write) からの導出 |
| AC-C02-23 | `output_language: ja` | brief `output_language` |
| AC-C02-24 | `source` が `component-inventory.json#C02` を指す | repo の SKILL.md 慣行 (追跡性) |
| AC-C02-25 | `extract-handout-config.py` を `--html` / `--out` / `--report` で起動する宣言 | C20 `argv` / `dependencies.invoked_by`「C02 (R1-scan / R3-roundtrip)」 |
| AC-C02-26 | R3-roundtrip が `render-handout.py` (C11) で再レンダリングし `verify-handout-selfcontained.py` (C16) を通す | brief `goal` / `deterministic_checks` / inventory `C02.depends_on` |
| AC-C02-27 | 完了チェックリストが brief `checklist` の 4 項目を覆う | brief `checklist` |

## 非受入例 (reject fixture) と落ちるべき契約 id

`reject_cases.py` の 31 件 + `test_contract_checker.py` 内の 3 件 (SKILL.md 欠落 /
prompt ファイル欠落 / 参照 script 実体欠落)。`test_every_contract_id_has_a_reject_case`
が「AC-C02-1〜27 のすべてに非受入例が 1 件以上ある」ことを機械的に固定している。

ラウンドトリップ性に関わる主な非受入例:

| ケース | 注入する違反 | 落ちる契約 |
|---|---|---|
| `html-parsed-by-skill` | skill が `html.parser` で自前走査すると書く | AC-C02-11 |
| `roundtrip-judged-by-byte-equality` | round-trip を HTML のバイト一致で判定すると書く | AC-C02-12 |
| `provenance-included-in-projection` | 比較対象射影に provenance を含める | AC-C02-12 |
| `never-guessed-relaxed` | マーカーが無い意味情報を本文の位置から推測して埋めると書く | AC-C02-13 |
| `completion-policy-narrowed` | 補完方針の 3 択を「推測値の充填」だけにする | AC-C02-14 |
| `unrecoverable-silently-dropped` | 復元不能箇所を件数が多ければレポートから省くと書く | AC-C02-14 |
| `fidelity-distinction-dropped` | 推測値と実読み取り値をまとめて記載すると書く | AC-C02-15 |
| `diff-summarized-as-equivalent` | 軽微な差分を等価として要約すると書く | AC-C02-20 |
| `empty-config-returned-as-success` | 部品 0 件でも成功として返すと書く | AC-C02-19 |
| `values-fabricated-to-pass-validation` | C12 を通すため不足値を既定で補うと書く | AC-C02-19 |
| `improvement-suggestion-added` | 改善提案を添えると書く (boundary 逸脱) | AC-C02-17 |
| `generation-boundary-crossed` | 続けて資料生成まで行うと書く | AC-C02-18 |
| `rerender-path-dropped` | 再レンダリングせず目視で見比べると書く | AC-C02-26 |
| `extra-responsibility-added` | 自作の改善責務 R4 を足す | AC-C02-4 |
| `c20-dependency-dropped` | depends_on から C20 を外す | AC-C02-21 |

## P05 実装者への注意

- テストを緑にするために `contract_lib.py` / `reject_cases.py` / `fixtures/` を
  書き換えないこと。契約を変えたい場合は先にブリーフ (正本) を変える。
- `fixtures/accept/skills/run-handout-extract/SKILL.md` は契約を満たす形の
  **例示**であり実装ではない。文面をそのまま流用しても契約は満たすが、
  逆抽出の中身 (手順・prompts) は別途書く必要がある。
- `BuildTargetLayoutTest.test_extractor_script_exists` は C20
  (`plugins/guide-doc-generator/scripts/extract-handout-config.py`) の実体も要求する。
  C02 は C20 無しでは契約を満たせないため、意図的に依存を赤で残している。

## 本テストで検査していないもの (P04-C02-01 の gaps)

以下はブリーフに記述が無いため、推測で検査を起こさず未検査のままにした。
詳細は leaf の報告 `gaps` を参照。

1. **R21 の新フィールドの逆抽出**
   (`presentation_order` / `focus_theme` / `must_remember` / `no_need_to_remember` /
   `target_tasks` / `attainment_level` / `section.ties_to`)。
   `script-brief-C20.json` の `roundtrip_granularity.preserved_exact` /
   `preserved_only_with_markers` / `renderer_marker_requirements` のいずれにも
   これらのフィールドが現れない (`section.duration` のみ `sections[].duration` として
   記載あり)。`RESOLUTION-R21.md` も C20 / C02 を変更対象に挙げていない。
   すなわち「R21 フィールドを逆抽出できるか」は plan 上まだ決まっていない。
2. **round-trip 比較の実行主体** — C20 の `--compare` で行うか skill が
   再レンダリング比較で行うかは `command-brief-C08.json` の `open_questions` で
   未決とされている。本テストは「再レンダリング経路を宣言していること」
   (AC-C02-26) までを課し、`--compare` の使用有無は課していない。
3. **skill の実行時挙動** — 実際の HTML を食わせた逆抽出精度は C20 (script) の
   受入検査 `AC-C20-01`〜`15` の担当であり、skill 側テストの射程外。
