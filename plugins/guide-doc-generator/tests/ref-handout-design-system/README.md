# ref-handout-design-system (C04) 受入テスト — 赤で固定した契約

対象 build_target: `plugins/guide-doc-generator/skills/ref-handout-design-system/` (P05 で実装)

```bash
python3 -m unittest discover -s plugins/guide-doc-generator/tests/ref-handout-design-system -p 'test_*.py'
```

Python 3.10+ 標準ライブラリのみ (`unittest`)。PyYAML は使わず、SKILL.md の
frontmatter は `contract_lib.py` の YAML 部分集合パーサで読む。

## 何を検査しているか

C04 は `kind: ref` の skill component なので、テストは skill の実行そのものでは
なく **SKILL.md の宣言的契約**を機械検査する。検査の軸は 5 つ。

1. identity と権限 (frontmatter / `allowed-tools` が Read のみ / ref kind が実行系宣言を持たないこと)
2. `output_contract` の 4 面が見出しとして存在すること
3. **語彙を複製していないこと** — 部品 id / 用途語彙 / `section_kind` を本文へ列挙せず、正本ファイルとその owner を指すこと (P03 Y-05 / Y-06 / Y-08)
4. デザイン言語の規範 (アクセント 1 色 + 明度 4 段階 / CSS 変数駆動 / `palt` / `tabular-nums` / rise-in スタガー / アイコン様式 / 絵文字禁止)
5. **自己完結** — ユーザーグローバル資産と絶対パスを参照せず、vendoring 実体が skill 配下に実在すること (R10)

## ファイル構成

| ファイル | 役割 | 実装前の状態 |
|---|---|---|
| `contract_lib.py` | 契約チェッカ本体 (判定器)。`check_skill(skill_dir) -> [Violation]` | — |
| `fixtures_lib.py` | 受入例 (契約を満たす SKILL.md + vendoring 実体) を tempdir へ materialize | — |
| `reject_cases.py` | 非受入例 33 件。受入例へ 1 箇所だけ違反を注入する | — |
| `test_contract_checker.py` | 判定器が受入例を通し非受入例を落とすことを固定 | **緑** (実装に依存しない) |
| `test_ref_handout_design_system.py` | 実 build_target への契約テスト (契約 id ごとに 1 メソッド) | **赤** |

`test_contract_checker.py` が緑であるのは意図どおりで、
「`test_ref_handout_design_system.py` が使う判定器が、何も検出しない空ゲートでは
ないこと」を先に固定するためにある。実装が存在しないうちに判定器の判定力を
検証できる唯一の手段がこの受入例 / 非受入例のペアである。

受入例を checked-in の fixture ツリーにせず tempdir へ書き出しているのは、
AC-C04-23 が「skill ディレクトリ配下に vendoring 実体があるか」を実ファイルで
見る契約であり、`tests/` 配下に本物そっくりの skill ツリーが常駐すると実装の
有無を取り違える読み手が出るためである。

## 契約 id と出典の対応表

正本は `plugin-plans/guide-doc-generator/briefs/skill-brief-C04.json`。
ブリーフ側に `AC-C04-*` の採番が存在しなかったため、本テストで採番した
(`gaps` 参照)。ブリーフが薄い項目 (デザイン言語の中身) は goal-spec の
R08 / R10 criterion と、同じ規範を実装する C11 / C15 のブリーフから起こした。

| 契約 id | 内容 | 出典 |
|---|---|---|
| AC-C04-1 | build_target に SKILL.md が実在する | task-spec `P04-C04-01.md` acceptance_criterion / inventory `C04.build_target` |
| AC-C04-2 | `name=ref-handout-design-system` / `prefix=ref` / `kind=ref` / `hierarchy_level=L1` | brief `skill_name` / `prefix` / `kind` / `hierarchy_level` |
| AC-C04-3 | description が trigger 語彙 3 件 (部品カタログ / トークン / アイコン) を持ち「〜とき」の発火条件形 | brief `trigger_conditions` + repo の ref 系 SKILL.md 慣行 |
| AC-C04-4 | `output_language: ja` | brief `output_language` |
| AC-C04-5 | `source` が `component-inventory.json#C04` を指す | repo の SKILL.md 慣行 (追跡性) |
| AC-C04-6 | `allowed-tools` は `[Read]` のみ。Write / Edit / Bash を持たない | brief `boundary` (出力=規範の引用) + `cli_tools: []` |
| AC-C04-7 | `goal_seek` / `deterministic_checks` / `cli_tools` / `mcp_tools` / `external_systems` / `combinators` / `feedback_contract` を宣言しない | inventory `C04` (いずれも空・`feedback_contract.skip_reason`) |
| AC-C04-8 | `## Purpose & Output Contract` がある | repo の SKILL.md 骨格 |
| AC-C04-8a | 面 1「部品カタログの構成データ表現」の見出し | brief `output_contract` |
| AC-C04-8b | 面 2「CSS 変数トークン一覧」の見出し | brief `output_contract` |
| AC-C04-8c | 面 3「アイコン規約」の見出し | brief `output_contract` |
| AC-C04-8d | 面 4「文章設計の型」の見出し | brief `output_contract` |
| AC-C04-9 | 責務境界の見出しがあり、HTML の生成をしない / 検証をしない と明記し C11 と C16 を名指しする | brief `boundary` |
| AC-C04-10 | 部品 id (`B\d{2}`) を本文へ列挙せず、`config/handout-parts.json` (owner C11) を**読んで答える**と書く | **P03 Y-05** / brief `output_contract` / `boundary` |
| AC-C04-11 | 用途語彙を 1 行に 2 語以上並べず、`config/handout-purposes.json` (owner C23) を指す | **P03 Y-06** / brief `boundary` |
| AC-C04-12 | `section_kind` 値を 1 行に 2 語以上並べず、`config/handout-sections.json` (writer C12) を指す | **P03 Y-08** / brief `boundary` |
| AC-C04-13 | アクセント 1 色 + 明度 4 段階を `--pop-primary` / `-pastel` / `-soft` / `-deep` の語彙で示す | goal-spec R10 / `script-brief-C11.json` algorithm 11 |
| AC-C04-14 | アクセント実値が現れるのは `:root` ブロックだけ。以降は `var(--pop-*)` 参照 | goal-spec R10 (「アクセント定義箇所のみが変わる」) / C11 algorithm 11 |
| AC-C04-15 | 値の正本は `assets/tokens/<theme>.json`。テーマ差し替え可能と明記し、散文に hex 実値を書かない | goal-spec R10 / `script-brief-C11.json` `theme_token_schema_ownership` |
| AC-C04-16 | `text_limits.block_body_max_chars` (既定 400) に言及し、スキーマ owner が C11・折り畳み規則が C12 `CR-TEXT-FOLD` であると明記する (自分で決めない) | **RESOLUTION-R21 C52** |
| AC-C04-17 | `font-feature-settings: "palt"` と数値の `tabular-nums` | goal-spec R10 / C11 algorithm 12 |
| AC-C04-18 | `rise-in` / `--stagger` インライン変数 / JS 非依存 / `prefers-reduced-motion` | goal-spec R10 / C11 algorithm 18 |
| AC-C04-19 | `viewBox="0 0 24 24"` / `stroke="currentColor"` / `fill="none"` / `stroke-linecap="round"` の 4 点 | **goal-spec R08** / `script-brief-C15.json` `purpose` |
| AC-C04-20 | `<symbol>` 定義 + `<use>` 参照、未使用 symbol 0 件、sprite 生成と id 採番は C15 | **goal-spec R08** / C15 `single_writer` |
| AC-C04-21 | 絵文字を使わない規範を持ち、SKILL.md 自身が絵文字を含まない | goal-spec R08 / C16 `CR-EMOJI` |
| AC-C04-22 | `~/.claude` などユーザーグローバル資産と絶対パスへの参照が 0 件 (否定文脈での言及は可) | **goal-spec R10** |
| AC-C04-23 | jp-web-design モードB「Pop・親しみ」を出所として明記し、skill 配下 `assets/` または `references/` に vendoring 実体があり SKILL.md がそれを参照する | **goal-spec R10** / P04 leaf の指示 |

### 絵文字判定について

規則の単一正本は `script-brief-C16.json` の `canonical_rules.emoji_rule`
(**CR-EMOJI**) であり、本テストはその**層 1 の部分集合**を SKILL.md というテキスト
1 面にだけ適用する。ブロック丸ごとの denylist は CR-EMOJI が明示的に禁じている
ので使わず、★ ✔ © などの記号は通す (`test_contract_checker.EmojiRuleTest` が
回帰として固定)。層 2 (VS16 を伴うときだけ違反) は U+FE0F 自体を層 1 が捕える
ので、部分集合でも取りこぼさない。

## 非受入例 (reject fixture) と落ちるべき契約 id

`reject_cases.py` の 33 件 + `test_contract_checker.py` 内の 2 件
(SKILL.md 欠落 / frontmatter 欠落)。責務境界と SSOT に関する主なもの:

| ケース | 注入する違反 | 落ちる契約 |
|---|---|---|
| `allowed-tools-write` | ref skill に Write / Bash を与える | AC-C04-6 |
| `html-generation-claimed` | 問い合わせに HTML 断片を生成して返すと書く | AC-C04-9 |
| `verification-claimed` | 自己完結性を自分で検査して合否を返すと書く | AC-C04-9 |
| `part-ids-enumerated` | 部品 id を本文に並べる | AC-C04-10 |
| `purpose-vocab-enumerated` | 用途語彙を列挙する | AC-C04-11 |
| `section-kind-enumerated` | `section_kind` 値を列挙する | AC-C04-12 |
| `var-reference-rule-missing` | アクセント実値を `:root` 外に直書きする | AC-C04-14 |
| `accent-value-in-prose` | 散文に既定アクセントの hex を書く | AC-C04-15 |
| `text-limit-owner-claimed` | 文字数上限と折り畳み規則を C04 が決めると書く | AC-C04-16 |
| `stagger-needs-js` | スタガーを JavaScript で付与すると書く | AC-C04-18 |
| `icon-viewbox-free` | viewBox を 24x24 以外にする | AC-C04-19 |
| `sprite-owner-claimed` | sprite 生成を C04 が行うと書く | AC-C04-20 |
| `emoji-used` | SKILL.md 自身に絵文字を入れる | AC-C04-21 |
| `user-global-asset-referenced` | `~/.claude/skills/jp-web-design/assets/` から読むと書く | AC-C04-22 |
| `vendored-file-absent` | vendoring 実体を置かない | AC-C04-23 |

## gaps (P05 / P03 へ持ち帰る判断)

| what | why |
|---|---|
| `skill-brief-C04.json` に `AC-C04-*` の採番が無い | C01 と同様、skill brief は inventory からの決定論射影で受入検査 id を持たない。本テストで採番したため、ブリーフ側に採番が入るときは README の対応表を正本と突き合わせること |
| デザイン言語の中身 (アクセント 4 段階 / palt / tabular-nums / rise-in / アイコン様式) が C04 のブリーフに書かれていない | ブリーフの `output_contract` は「CSS 変数トークン一覧 / アイコン規約」という**面の名前**までしか持たない。中身の正本は goal-spec R08 / R10 と、それを実装する C11 algorithm 11-18 / C15 にある。本テストはそこから起こしたので、C04 と C11 の記述が食い違うと C11 側が正本 (C04 は参照回答なので描画の実装に従う) |
| vendoring 先が skill 配下 (`skills/ref-handout-design-system/assets/`) か plugin root (`plugins/guide-doc-generator/assets/`) か未確定 | R10 は「plugin の `assets/` へ vendoring」としか書かず、C11 は plugin root の `assets/tokens/*.json` を実体解決で読む。テーマトークンの**値**の正本を二重化しないため、本テストは「C04 配下にあるのはモードB の**規範記述**であり、トークン値の正本は plugin root 側 (owner C11)」という切り分けで固定した。P03 で別の裁定が出た場合は AC-C04-23 の探索先を直す |
| `text_limits.block_body_max_chars` の既定 400 を C04 が引用してよいか | 数値の正本はテーマトークンファイル (スキーマ owner C11) なので、本来 C04 は値を持つべきでない。ただし「参照回答」の skill が既定値を答えられないと trigger「デザイントークンの値を引く」に応えられない。本テストは「既定値の引用は可・上限を決める主体は自分でないと明記すること」で固定した (AC-C04-16) |
| 絵文字判定の実行主体 | CR-EMOJI の実装は C16 が公開する `scan_emoji` だが、それは P05 の成果物であり P04 時点では import できない。本テストは層 1 の部分集合を自前で持つ。P06 で C16 実装と同一 fixture を突き合わせる余地がある |

## P05 実装者への注意

- テストを緑にするために `contract_lib.py` / `reject_cases.py` / `fixtures_lib.py`
  を書き換えないこと。契約を変えたい場合は先にブリーフ (正本) を変える。
- `fixtures_lib.ACCEPT_SKILL_MD` は契約を満たす形の**例示**であり実装ではない。
  文面をそのまま流用しても契約は満たすが、デザイン言語の中身 (モードB の配色
  思想・部品ごとの版面規範・文章設計の型) は別途書く必要がある。
