# 既知未修正・検査の届き方の台帳

**目的**: 「測って把握しているが、いま直さないと決めたもの」と「検査が実は届いている／届いていないもの」を 1 箇所に置く。ここに無いものは、誰も測っていないか、測った記録が失われている。

**この台帳が要る理由**: 検査の届き方が間接だと、記録が無いかぎり何度でも再発見される。再発見した人は「配線されていない」と判断して二重に配線する。逆に、直さないと決めたものを記録しないと、次に見つけた人が直しにくる。どちらも同じ作業を 2 回やることになる。

各項目には**測定日**と**測り方**を書く。書かないと、後から読む人がその数字を再現できない。

**この台帳は検査の網の中に置いてある**（`references/**/*.md` は `lint-count-parity.py` も `lint-contract-drift.py` も読む）。網の外へ避難させないこと。ただしその副作用として、**違反の証拠として CSS を貼ると、その引用自体が違反として検出される**。実測では、K-001 の VG08 の証拠を `box-shadow` プロパティと `--shadow-subtle` を CSS の関数記法で繋いだ形で書いたところ、その行が `css-var-fallback` として 1 件検出された。**さらに、その顛末をここへ書くときに同じ記法をもう一度書いてしまい、2 度目の検出が出た。**証拠を引くときは関数記法を使わず、プロパティ名と変数名を分けて書くこと。

現在の寄与は **0 件**（2026-08-26 実測）。以前残っていた 7 件は、色相依存の例を
反転面・濃度・寸法差へ統合し、印刷表を共通トークン消費 component に変更し、未消費の
旧 stylesheet と単一 HTML snapshot を削除して解消した。現在の正本に対する
`lint-contract-drift.py` は finding 0 件である。

以下の「7件」「凍結中のaccent」「孤児3件」に関する記述は、検出器を弱めずに解消した
経緯を残す履歴であり、現在の未修正一覧ではない。

**この 7 という数字を基準線として使わないこと。**内訳が動いている。同日中に `orphan-var-definer` 3 件が別作業で足されており、残る 4 件が凍結中の accent。台帳の寄与を測り直すときは、7 との差ではなく**退避あり／なしの同時比較**で見ること。

### 逃げ道は 1 つしかない（実測・2026-08-14）

`css-var-fallback` は生のテキストへ正規表現を当てているだけで、markdown の構造を一切見ていない。**フェンスへ入れても逃げられない。**

| 書き方 | 検出 |
|---|---|
| 素の行 | 1 件 |
| インラインコード（表セル） | 1 件 |
| ` ```css ` フェンス | 1 件 |
| ` ``` ` フェンス（言語指定なし） | 1 件 |
| 引用行（`>`） | 1 件 |
| **プロパティ名と変数名を分けて書く** | **0 件** |

先にフェンスを試して時間を使わないこと。**0 件にできるのは分割記法だけ**である。

html 側は共通型（`scripts/mention_mask.py`）で閉じたが、**markdown 側は閉じていない**。構造が同じで意味が正反対のケース（`spec-registry.md` の SR-8-01 は同じインラインコードで**標準実装**を書いている）があり、構造では記録と指示を分けられないため。剥がす方向で入れると実在の指摘が黙って緑になる（.md 全体へ当てると 393 → 329 件へ 64 件減り、その中に実装の指示と凍結中の accent が含まれていた）。

したがって**上の注意書きはまだ消せない。**markdown 側が閉じたときに消すこと。**閉じる目処は現時点で無い。**「構造で分けられるかどうか」の判断基準は `scripts/mention_mask.py` の docstring が正本で、ここには写さない（写すと二重管理になる）。

文書レベルで「ここは記録専用」と宣言して黙らせる案は**却下されている**（2026-08-14）。宣言すれば黙る仕組みは埋葬地になるうえ、既存の口へ足すと**赤が消えたときにどれが吸ったのか追えなくなる**という理由。ここへ「記録専用」の類の宣言を足さないこと。

既存の口は **3 つ。ただし 2 種類**である（実測・2026-08-14）。

| 名前 | 場所 | 種類 |
|---|---|---|
| `_VAR_ROUTE_SOURCES` | `scripts/lint-contract-drift.py:243` | 除外（見なくする） |
| `_NON_ROUTE_DEFINERS` | `scripts/lint-contract-drift.py:291` | 除外（見なくする） |
| `_KNOWN_GAPS` | `tests/test_lint_contract_drift.py:157` | **ピン留め（見続ける）** |

**`_KNOWN_GAPS` を除外と同じに数えないこと。** `assert got == _KNOWN_GAPS` で集合そのものを固定しているので、**違反が 1 件増えれば落ちる**。赤を消しているのではなく、赤の集合を固定している。3 つとまとめて数えると、性質の違うこれが巻き添えで悪者になり、次に「ピン留めも減らそう」という話が出る。それは検出力を下げる方向である。

**除外 2 つのうち `_NON_ROUTE_DEFINERS` が最も危ない。** `orphan-var-definer` の**エラーメッセージ自身が「ここへ根拠を書いて置け」と案内している**ので、赤を見た人が存在を知らなくても使える。通常の直し方（経路へ載せる）より速い経路が案内付きで用意されている。実際に正しい使い方で通した例（`print-styles.css` を実測で分類し根拠を付けて登録）もあり、**正しく使える口ほど雑に使われたときに見分けが付かない**。判定材料は根拠が書いてあるかどうかだけで、根拠の質は機械では測れない。

4 つ目を足さないこと。

**この 0 件は「解決した緑」ではない。**検出が消えたのは記法を変えたからで、**直ったのではなく書き換えで消えた**。記録する人が「正確に引用する」と「検査を通す」のどちらかを選ばされる状態は残っている（追記: exec-void・2026-08-14）。

---

## K-001 出荷デッキの生成則違反 52 件 — 直さない

**対象**: `05_Project/スライド/slide-2026-08-15-AI質問会/` と `_出荷版バックアップ-2026-08-13/`

**状態**: `validate-visual-generation.py` で error 52 件 / warn 0 件（面 12）。

**直さない理由**: このデッキを**無変更のまま出荷するというユーザーの決定**による。直せるのに直していないのではなく、直さないと決まっている。**期限は付いていない。**「いつまで凍結」という条件が無いので、日付が過ぎたから直してよい、という読み方はできない。解除するならユーザーの決定が要る。

**原本には書き込まない。** 測定は読み取り専用の複製に対して行うこと。

**内訳**（測定日 2026-08-14・`validate-visual-generation.py <index.html> --json`）:

| 件数 | code | 内容 |
|------|------|------|
| 12 | VG03 | `data-role` (lead / body / label) を持つ文字要素が 0 件。E2 の隣接比を測る対象が無い |
| 12 | VG06 | 反転ブロック 0 個（規定はちょうど 1 個・地 #141412） |
| 9 | VG07 | `border-radius: 0.6vw`（許すのは 0px と図版外形の 2px のみ） |
| 7 | VG02 | I1/I2 が下限 1.60 未満 |
| 5 | VG08 | `box-shadow` に `--shadow-subtle` を指定（影は使わない） |
| 3 | VG09 | 線幅が `0.1vw`（px 以外） |
| 3 | VG10 | `font-weight: 800`（許すのは 400 / 500 / 700 の 3 段） |
| 1 | VG11 | `font-weight: 700` の文字要素が 10 箇所（上限 1） |

**劣化ではない**: 出荷版バックアップも**同じ 52 件・同じ内訳**を出す。最初からこの状態である。

**VG02 の 7 件について**（下限 1.60 を動かす検討をする人向け）:

```
1 位 3.9rem w700 I=5.460 / 2 位 2.6rem   w800 I=3.640  → 1.500（4 面）
1 位 3.9rem w700 I=5.460 / 2 位 2.444rem w800 I=3.422  → 1.596（3 面）
```

1.596 は 3.9 / 2.444 という**純粋なサイズ比**で、太さの寄与はゼロ。しかも 2 位のほうが太い（w700 対 w800）。強度の梯子が 400/500/700 までなので w800 が 700 と同じ 1.40 に丸められ、太さ軸での逆転が数値に出ていないだけである。**不足 0.004 は丸め誤差ではなく、下限 1.60 がまさに弾くために置かれた「サイズだけの差」そのもの**なので、下限を下げるとこの規則が捕まえるために作られたケースを通すことになる。下げないこと。根拠は `skills/run-slide-report-generate/references/visual-generation-rules.md` の E1 の項。

---

## K-002 pytest 経由でしか起動されない検査器 2 本 — 二重に配線しないこと

**対象**: `scripts/lint-count-parity.py` / `scripts/lint-contract-drift.py`

**この 2 本は実物に届いている。** `tests/test_lint_count_parity.py` と `tests/test_lint_contract_drift.py` がプラグイン実体（`_PLUGIN_ROOT`）を対象に走るので、入力は合成 fixture ではない。

**ただし「EVALS 経由で走っている」とは書かないこと。** `EVALS.json` の `harness.mechanical[]` を読む runner は存在しない。そこへ行を足しても実行は 1 つも増えない。届くのは**誰かが `pytest tests/` を叩いたとき**であって、EVALS に載っていることが実行の根拠にはならない。この区別を落とすと、次の人が「EVALS に載っているから走っている」と読む。

**hook や SKILL.md へ改めて配線しないこと。** 起動口を数えると「テストからしか呼ばれていない」に見えるが、**そのテストの入力が合成物ではなく実ツリー**なので、届き方が間接なだけで届いている。ここを見落として配線を足すと、同じ検査が 1 回の生成で 2 回走る。

**起動口の分類（テスト経由）と、その含意（合成入力しか見ていない）は別物である。** 分類だけ見て含意を決めない。

測定日 2026-08-14。

---

## K-003 `lint-count-parity.py` の走査対象外に、同 lint 用の宣言が置かれている

**測定日 2026-08-14。** 測り方: `_SCAN_GLOBS`（`scripts/lint-count-parity.py`）が実際に拾うファイル集合と、リポジトリ内の文書系ファイル全体を突き合わせた。

**走査対象 117 本 / 文書系 211 本 → 94 本が網の外。**

網の外にあるもののうち、**最も具合が悪いのはこれ**である。

`assets/slide-templates/README.md` に、**この lint 自身の宣言構文**が 3 箇所ある。

```
<!-- count: slideSkeleton -->22 種
```

`slideSkeleton` は lint が知っているキーで、実測器（`_m_slide_skeleton`）も持っている。同じキーの宣言は `references/resource-map.md` と `skills/run-slide-report-generate/prompts/R1-orchestrate.md` にもあり、**そちらは網の中なので実際に検査されている**。

つまり `assets/slide-templates/README.md` の 3 箇所は、**書いた人は検査されると思って書いたが、lint がそのファイルを一度も開いていない**。宣言があることが、検査されていることの証拠にならない状態である。`assets/**` が `_SCAN_GLOBS` に無いことが原因。

同じディレクトリの `registry.json` にも `107 種`（slideType）があり、これも網の外にある。

**網は今日は広げない。** 広げると新規 finding がまとまって出て、進行中の符号系の着地と混ざるため。広げるときは、上の 3 箇所が最初に赤くなるはずなので、赤くならなかったら glob の当て方を疑うこと。

**補足（前便の訂正）**: 網の外に並ぶ「30 種」は**テンプレート枚数ではなく 30 種思考法**である（`EVALS.json` ×2 / `plugin-composition.yaml` / `schemas/evaluation-report.schema.json` / `skills/run-slide-report-generate/references/resource-map.yaml` / 同 `workflow-manifest.json` ×2 の 5 ファイル）。テンプレート枚数は 22 種（ひな形）と 107 種（slideType）で、別の数である。

---

## K-004 `validate-linebreak-position.mjs` は実デッキに対象を持たない

**測定日 2026-08-14。** 生成済みデッキに `<br>` が 1 つも無く、この検査器は当てても `checked=0`（未検査）を返す。**構造的にそうなる**ので、対象を持つデッキが出てくるまで緑は何も保証しない。

出力側で `verdict` を `not-checked` / `pass` / `fail` に分けてあるので、呼び出し側は「対象 0 の緑」と「検査して違反なしの緑」を区別できる。exit code は両方 0 なので、**exit code だけで判断しないこと。**

**対象 0 件でも配線は外さないこと。** `hook-postgen-eval.py` の 1f として両 mode に配線済み（2026-08-14）。いま 0 件なのは現時点の生成物が `<br>` を出さないからで、0 件であり続ける保証はない。外すと、将来この repo に文章としての `<br>` が入ったとき誰も気付かない。

`no-target` は systemMessage にしていない。現状では毎回鳴ることになり、鳴り続ける通知は本物の赤を無視する習慣を作るため。未検査であることは additionalContext に明記して残してある。

---

## K-005 SR-0-01（V-020）は実行体が在るのに既定経路で到達しない — 凍結明けまで直さない

**対象**: `vendor/scripts/phase-gate.js:162-171`（Gate 2 = `P3->P3_5`）/ `vendor/scripts/workflow-manager.js` の `detectPhase()`

**状態**: 実行体は在る。しかし既定の phase 判定では Gate 2 が一度も選ばれない。

**測り方**（実測 2026-08-14・A / B / C の 3 本を実際に走らせた）:

- A: `detectPhase()` はファイル存在で判定し、`index.html` があれば P3_5 を返す。よって `P3->P3_5` の Gate 2 は選ばれない
- B: Gate 2 を直接呼べばインライン `<style>` / `<script>` を検出して FAIL する（実行体は生きている）
- C: 唯一の抜け道 `.workflow-state.json` は、このプラグイン内に**書き手が無い**（読むだけ）。出荷済みの実 deck にも 1 件も存在しない

**A だけなら「走っていない」、B だけなら「走れば落ちる」で終わる。両方あって初めて「排他」と言える。**
grep で「実行体が在る」まで分かった時点で「検査されている」と書きかけたが、在ることと通ることは別だった。

**これは既存 3 分類のどれでもない 4 つ目の状態である**（`report.skip()` の kind を次に触る人へ）:

| 状態 | 実行体 | 到達 | 例 |
|---|---|---|---|
| `no-checker` | 無い | — | V-030 ほか |
| `not-applicable` | 有る | 対象が無い | V-031〜038 |
| `deferred` | 有る | 材料が取れない | V-002（json 入力） |
| **（未命名）** | **有る** | **状態が排他で選ばれない** | **V-020** |

`kind` へ 4 つ目を足すかは決めていない。採番は下流の消費者に効くので、符号系の着地と混ぜない。

**直さない理由**: 配線を直すと phase 判定の挙動が変わる。8/15 本番のデッキは凍結中で、残り 24 本も出荷済み。**凍結明けにユーザー判断で。期限は付いていない**（日付が過ぎたから直してよい、とは読めない）。

**規則本文は消していない**: SR-0-01 の規則行（`references/spec-registry.md` §18）には到達条件を併記してある。**到達条件を書かずに §17 から出すと、§17 に置いてあったときより悪くなる**——§17 は「まだ無い」と正直に言うが、到達条件の無い規則行は「検査されている」と嘘をつく。**無いことが見える画面から、無いものだけが抜いてある。**§17 は「まだ無い」を数え上げる場所なので、そこから出す操作は**画面の側は変えずに母数だけ減らす**。§18 へ移した SR-0-01 は無くなったのではなく、無いことが見える場所から出ただけである。

---

## K-006 宣言の受け皿があって読み手が無い — `EVALS.json` の `harness.mechanical[]`

**測定時刻 2026-08-14 14:54〜14:57。** `EVALS.json` の mtime は 2026-08-12 06:19:25。

**対象**: `EVALS.json` → `harness.mechanical[]`。**14 本**の実行コマンドが文字列配列で宣言されている（`pytest tests/ -q` / `validate-output-mode.py` ×2 / `setup-playwright.py --check` / `validate-plugin-completeness.py` / `lint-reference-attribution.py` / harness-creator の `lint-ssot-duplication.py` / `lint-vendor-parity.py` / `npm test` / vendor の node テスト 4 本 / `verify-report-runtime.js --self-test`）。

### 探し方を先に書く（「無い」は探した範囲でしか担保できない）

- 走査ルート: harness リポジトリ全体（`/Users/dm/dev/dev/個人開発/harness`）
- glob: `**/*` から `.git/` `node_modules/` `__pycache__/` `.venv/` を除外。全文検索は 10770 ファイル、実行系に絞った 2 周目はさらに `.worktrees/` `eval-log/` `plugin-plans/` `doc/`（記録・計画・参考資料。実行されない）を除外して 1116 ファイル
- 語: `EVALS.json` / `EVALS` / `mechanical` / `harness` の 4 語
- 判定: 「読む」= そのファイルが `EVALS.json` を開いて `harness.mechanical` を参照していること

### 結果: このプラグインの `harness.mechanical[]` を読むものは 0 本

**実行するものも、書式を突き合わせるものも無い。**`.github/workflows/` にも `scripts/run-ci-checks.sh` にも `EVALS.json` の文字列は 1 度も出てこない。

**対照を取ってある**（0 本が「走査が壊れていて全部 0」でないことを示すため）。同じ走査で**読む側が実在する例が出る**:

- `plugins/plugin-dev-planner/skills/assign-plugin-plan-evaluator/tests/test_gate_parity.py:82-88` は**自プラグインの** `EVALS.json` の `harness.mechanical` を読み、全ゲートスクリプトが載っているかを assert する。**実行はしないが、宣言の欠落は落ちる**
- `plugins/harness-creator/.../aggregate-evals.py` は `EVALS.json` の `evaluations[]` を読む（`mechanical` は読まない）

つまり**同じ書式の別プラグインには突合テストが在り、こちらには無い**。「読む側が無い」はこのプラグインについての事実で、書式一般についての事実ではない。

### 書式は崩れていない。ただし守られている理由が弱い

- 14 本が指すパスは**全て実在**（dead path 0 本）。読み手が無いのに腐っていないのは、たまたま該当スクリプトが消えていないからで、消えても誰も気付かない状態は変わらない
- 記法は 2 系統。`cd <dir> && <cmd>` が 2 本（1 番の pytest と 9 番の `npm test`）、残り 12 本は repo ルート相対の直接実行。**9 番の `npm test` は cwd が要るので逸脱ではない**
- 導入時期（`git log -S`）: **14 本中 11 本が同一コミット** `4cd8faf`（2026-07-12 のプラグイン構成再編）で一度に書かれた。後から足されたのは 3 本のみ（`db7cfa0` 2026-07-24 で 2 本、`830ef76` 2026-08-11 で 1 本）で、いずれも既存の形をなぞっている
- したがって**「書式が守られている」ことは、書式が伝わっている証拠にはならない**。ほぼ全部が一度に書かれ、その後 3 本しか追加されていないだけである

### 同じ形が他にもある

- **書く側だけ在る（受け皿があって読み手が無い）**: 同じ `EVALS.json` の `surfaces_enforced_by`。読むのは plugin-dev-planner の `test_ci_integration.py` 1 本だけで、それは `PLUGIN_ROOT = parents[3]`（自プラグイン）を見る。**このファイルの中に 2 例ある。**`threshold_note` / `llm_eval_note` も読み手 0 だが、これは人間向けの注記なので同じ形とは数えない
- **読む側だけ在る（読み手があって書き手が無い）**: `.workflow-state.json`（K-005 の C）
- プラグイン内の `.json` / `.yaml` について読み書きを総当たりで数えることも試したが、**ファイル名リテラルで拾う方法では test fixture ばかり拾って結論が出なかった**。この 2 方向の全数は**測れていない**

### 直さない

**runner を書くのは別の判断である。**書いた瞬間、**今まで一度も検証されていない 14 本が一斉に走り出す**。何が落ちるか分からないうえ、8/15 本番前に入れる変更ではない。

`harness.mechanical[]` へ行を足しても実行は 1 つも増えない（K-002）。**足すこと自体は害ではないが、足したことを「検査を配線した」と書かないこと。**

---

## K-007 判定 1 ビットが exit code と report ファイルの 2 本を流れている 5 箇所 — 直さない

**測定日 2026-08-14。** 測り方: `scripts/` `tests/` `hooks/` `vendor/scripts/` の `.py` 42 本を AST で走査し、`subprocess` の戻りを受けた箇所ごとに `returncode` を読むかどうかを判定した。

**同じ 1 ビットが 2 本の経路を流れており、呼び出し側は片方しか見ていない。**いまは両者が一致するので落ちない。**片方だけ直したときに黙ってズレる。**

| # | 場所 | 2 本の経路 | どちらが正本か |
|---|---|---|---|
| 1 | `scripts/validate-output-mode.py:121` | `setup-playwright.py --check` の `exit 0/1` と、その stdout JSON の `ready` | **決まっていない。** 産出側（`setup-playwright.py` の `main`）は `exit_code = 0 if result["ready"] else 1` で両方へ同じ値を書いている。呼び出し側は JSON だけ読む |
| 2 | `tests/test_validate_structure_unchecked.py:129` | プロセスの exit code と、`--report` が書く JSON | **決まっていない**（JSON 側だけ読む） |
| 3 | 同 `:299` | 同上（`phase-gate.js`） | 同上 |
| 4 | 同 `:340` | 同上（`evaluate-deck.js`） | 同上 |
| 5 | 同 `:374` | 同上 | 同上 |

**2〜5 は fail-closed である。**プロセスが転べば report ファイルが書かれず `read_text` が `FileNotFoundError` を投げるので、テストは黙って緑になるのではなく落ちる。**この但し書きを落とさないこと。**落とすと 5 件が同じ危険度に見えるが、同じではない。1 も転べば `json.JSONDecodeError` を捕まえて `ready: False` を返すので黙りはしない。

**直さない理由**: いま両経路の値は一致しており、片方を読むよう揃えても**検出は 1 件も増えない**。増えるのは差分だけである。危険なのは 2 本あること自体で、それは呼び出し側の書き換えでは消えない（消すには産出側を 1 本にする必要があり、`--check` の CLI 契約を変えることになる）。

**消す条件**（どれか 1 つで閉じる）:

- 産出側が 1 本になったとき（`setup-playwright.py` が exit code か JSON のどちらかだけで readiness を表すようになる、等）
- 呼び出し側が両方を突き合わせるようになったとき（`vendor/scripts/evaluate-deck.js:554` が手本。「非 0 なのに FAIL 行が無い＝検査器自体が転んだ」を専用の分岐で拾っている）
- 2 本の値が食い違う事例が実際に出たとき（そのときは直す対象が確定するので、この項目ではなく個別の修正になる）

**関連（こちらは直した）**: `tests/test_slide_layout_void.py::test_low_density_kinds_are_exempt` は `returncode` を読まず `assert "[L8-void]" not in got.stderr` の 1 行だけで判定していた。検査器のパスを実在しない値へ差し替えると `rc=1` になるが stderr に `[L8-void]` は出ないので**緑のまま通っていた**（実測）。`returncode == 0` の確認と、「免除が無ければ鳴る条件が揃っている」ことの測定（`--measure` の `void_share` が下限未満）を足し、壊すと FAIL することを再実測して確認した。**`not in` だけで合否を決めている検査は他に無い**（同走査で 24 箇所中 20 箇所は exit code も読んでいた）。

---

## K-008 宣言面ごとの読み手の有無 — 全数 census（直さない）

**測定時刻 2026-08-14 15:04-15:09。** K-006 で `EVALS.json` 1 ファイルの中から 2 例（`harness.mechanical` / `surfaces_enforced_by`）出たので、**面ごとに数え直した**ものである。

### 走査

- 面の母集団: プラグイン root の `**/*` から suffix `.json` `.yaml` `.yml`、`node_modules/` `__pycache__/` 除外 = **119 ファイル**。うち構成宣言として数えたのは **20 ファイル**
- 除外したもの: `examples/` `goldens` `fixtures` `tests/` 配下の 66 件（宣言でなく**データ実例**）、`vendor/playwright-browsers/` 11 件（第三者バイナリ同梱）、`vendor/coverage/` 4 件・`vendor/package-lock.json`（**生成物**）
- 読み手の走査: harness repo root の `**/*` で suffix `.py` `.js` `.cjs` `.mjs` `.ts` `.sh`、除外 `node_modules/` `.git/` `__pycache__/` `.worktrees/` `playwright-browsers/` `vendor/coverage/` `.venv/` = **1105 ファイル**
- 手順は 2 段。(1) 面のパス片を綴っているファイルを読み手候補として確定する。(2) **候補の中だけで**キー名を探す。repo 全体でキー名を探すと `name` `version` `description` のような語が数百件当たって何も言えない

### 面と読み手

| 面（ファイル + キー） | 要素数 | 読み手 | 読み手の性質 |
|---|---|---|---|
| `plugin-composition.yaml` `capabilities[kind: script]` | 23 | 有 | 突合するだけ（`validate-plugin-completeness.py` が `scripts/` の実体と集合一致） |
| 同 `[kind: skill]` / `[kind: command]` / `[kind: hook]` | 4 / 2 / 1 | 有 | 突合するだけ（`skill-governance-lint/scripts/lint-plugin-composition.py` が kind ごとに分岐） |
| 同 `[kind: agent]` | 17 | **無** | 上記 lint に `agent` の分岐が無い（`kind == "skill"` / `"script"` / `"command"` / `"hook"` のみ） |
| 同 `contract` / `dependencies` / `eval_sinks` / `owner` / `since` / `last-audited` | 6 キー | **測れない** | 読み手候補は在るがキー単位まで追っていない |
| `EVALS.json` `harness.mechanical[]` | 14 | **無** | K-006（runner 不在） |
| 同 `harness.llm_eval[]` / `threshold` | 4 / 1 | **無** | 同上の走査で読み手 0 |
| 同 `surfaces[]` | 10 | **無** | 下記「誤りの実例」参照 |
| 同 `surfaces_enforced_by` | 10 | **無** | K-006（書く側だけ） |
| 同 `harness.threshold_note` / `llm_eval_note` | 2 | 無（人間向け注記） | 表示するだけ |
| `.claude-plugin/plugin.json` `hooks` | 1 参照 | 有 | native manifest は `hooks/hooks.json` への参照だけを持ち、Harness metadata は重複させない |
| `references/package-contract.json` `package_mode` / `entry_points` / `distribution` / `depends_on` | 4 キー | 有 | `validate-plugin-completeness.py` / repo validator / `validate-plugin-package.py` が実体・marketplace・bundle と突合 |
| 同 `pkg_checks` | 9（PKG-001〜008 / PKG-014） | 有 | PKG-001 は strict wrapper、残る8件は `assign-plugin-package-evaluator/scripts/validate-plugin-package.py` が実行し、結果を同じ契約面へ記録する |
| `assets/slide-templates/frame-contract.json` 幾何・閾値 | 13 節 | 有 | **実行する**（`build-slide-skeleton*.py` が CSS/JS/HTML を生成、`validate-slide-*.py|js` が判定） |
| 同 `fill_policy.type_area_ratio` / `fill_policy.target_canvas_whitespace_ratio` / `vertical_margin_policy.target_proximity_gap_ratio` / `canvas.unit` / `schema_version` | 5 | **無** | 前 3 つは**閾値の形をしている**（`note_*` と違い、読まれる前提で書かれた値） |
| 同 `note_*` 各種 | 37 | 無（人間向け注記） | 表示するだけ |
| `assets/slide-templates/registry.json` `skeletons` / `map` / `structural_pages` / `role_pages` | 22 / 107 / 5 / 6 | 有 | **実行する**（`validate-slide-skeleton.py` が反復して引く） |
| 同 `source_of_truth.slide_types` / `.geometry` | 2 | **測れない** | 値が「正本はどこか」を書いた文字列で、反復で読まれても検知できない |
| `schemas/visual-derivation-table.json` `rows[]` | 14 | 有 | **実行する**（`vendor/scripts/render-report.js` が `require` して `table.rows` を実行） |
| 同 `override` / `definitions` / `implementedBy` / `appliesTo` | 4 / 4 / 2 / 1 | **無** | 唯一の読み手が `rows` しか見ない。`override` は `requires` / `forbidden` を持つ**規則**である |
| `vendor/vendor-digest-manifest.json` `local_fork_managed` / `subtrees` | 17 / 5 | 有 | **実行する**（`lint-vendor-parity.py` が `manifest.get()` で読む） |
| 同 `additive_managed` | 8 ファイル | 有 | `validate_additive_runtime_manifest()` が package 2 件 + runtime 6 件の実装集合と宣言集合を双方向照合する |
| 同 `upstream_name` / `upstream_version` / `source_root` / `generated_at` / `total_pinned_files` / `hash_algorithm` / `excluded_dirs` / `purpose` / `version` | 9 | **無** | — |
| `skills/*/workflow-manifest.json` `resources[]` | 60 + 14 + 6 = 80 | **無** | 唯一の repo 側読み手 `lint-skill-completeness.py` は `is_file()` の**存在確認だけ**で、キーを 1 つも開かない |
| 同 `phases` / `schemaVersion` / `workflowId` | 9 / 3 / 3 | **無** | 同上 |
| `vendor/package.json` `dependencies` | 2 | 有 | 突合するだけ |
| 同 `scripts.postinstall` / `setup:playwright` / `test` | 3 | **測れない** | npm が読む。今回の走査（`.py`/`.js` 等）では観測できない |
| `schemas/*.schema.json` 8 本の本体 | — | 有 | **実行する**（`validate-structure.js` / `render-slide.cjs` が読み込んで検証） |
| 同 `$id` / `title` / `description` などメタ | — | **測れない** | schema 本体が読まれることと、メタが読まれることは別 |

**合計: 読み手「無」= 14 面（要素で数えると 200 超）。「測れない」= 6 面。**

### PKG-001 の実行経路は evaluator と別 — 2026-08-26 解消

旧 census は、package check 全体と sub-check evaluator の責務境界を同一視していた。

`assign-plugin-package-evaluator` が担当するのは意図どおり `PKG-002〜008 / PKG-014` の 8 sub-check である。`PKG-001` は `run-plugin-package-check/SKILL.md` から `scripts/run-plugin-validate-strict.sh` を実行する strict validation の入口であり、現行 package check で PASS する。evaluator の dispatch 表に PKG-001 が無いことは、実装欠落ではなく責務分離である。

`references/package-contract.json` の `pkg_checks` は PKG-001 の strict 結果と evaluator が記録する 8 sub-check、計9件を保持する。ただし実行責務は分離したままとし、PKG-001 を evaluator の dispatch へ重複実装しない。

### `lint-vendor-parity.py` の additive 宣言照合 — 2026-08-26 解消

旧実装は `additive_managed` の集合を読まず、コメントの主張範囲と実装範囲がずれていた。2026-08-26 に package 2 件 + runtime 6 件の実装集合と manifest 宣言集合の一致検査を追加し、このコメントずれは解消した。

**この検査器には自動経路が 1 つも無い**（pytest 0 / hook 0 / SKILL 0 / command 0、`scripts/run-ci-checks.sh` に記載なし。**測定時刻 2026-08-14 15:14:48**、走査条件は下記「上限であって下限ではない」節と同じ）。手で叩いたときだけ走る。

残る制約は自動起動経路である。検査を手で実行した場合の緑は、**「その時刻に手で叩いて緑だった」以上のことを意味しない。**

### 対照（同じ走査で読み手が出ること）

- **同一ファイル内で割れた例がある。**`visual-derivation-table.json` は `rows` が読まれて `override` が読まれない。**走査が壊れていれば同じファイルの中で有無が分かれることは起きない**
- `frame-contract.json` の `fill_policy.min_stage_fill_ratio` は `validate-slide-skeleton.py` が実際に読む。同じ節の `type_area_ratio` は読まない
- `EVALS.json` の対照は K-006 で取った（plugin-dev-planner の `test_gate_parity.py` が自プラグインの `harness.mechanical` を読んで assert する）

### 誤りの実例（この方法がどちらへ転ぶか）

素朴に語で数えた段階では、`EVALS.json` の `surfaces` に**読み手が 1 本在るように見えた**（`check-plugin-surface-audit.py`）。開くと、そのスクリプトは `surfaces = { ... }` という**自前の変数**を組み立てており、`EVALS.json` については `is_file()` しか見ていない。**この方法は「無」を「有」へ倒す向きに誤る。**逆向き（有を無へ）は、読み手がキー名を綴らず反復で回している場合に起きる（`registry.json` の `map` 107 件は個々のキー名がコードに 1 つも現れないが、実際には読まれている）。**したがって上表の「無」は、キー名を綴らない反復読みが無いことを個別に確認した面についてのみ確定である**（`EVALS.json` / `vendor-digest-manifest.json` / `visual-derivation-table.json` / `workflow-manifest.json` / `package-contract.json` は読み手を開いて確認した。`frame-contract.json` の 5 件は開いていない）。

### この節そのものが誤読された（起きた事実）

2026-08-14、この K-008 を採番し直すかの判断のなかで、**この節を書いたのが誰かが取り違えられた**。台帳を `exec-` で grep すると K-008 の中には 2 箇所しか出てこず、どちらも訂正の出所（「exec-p0 の訂正により『提示』を足す」「exec-p0 の 6-8 は上限が動かない」）であって、**書き手を名指した記述は 1 つも無い**。にもかかわらず、節の中に出てくる唯一の名前がその人だったため、その人が書いたものとして読まれた。

**訂正の出所を丁寧に書いたことが、誤読の原因になっている。**出所を書かなければこの取り違えは起きなかった。記録を増やすほど誤読の口が増える形で、`svg-kit.cjs` の「arrow-soft は置いていない」というコメントが実装 3 種の 1 つとして数えられたのと同族である（**不在を記録した行が、存在の証拠として読まれた**）。

**K-008 の主題がこの節自身に当たった形でもある。**本文から読める情報（誰の名前が出てくるか）の外に正本（誰が書いたか）があり、読み手は前者から後者を推測した。

**規則にはしない。**「書き手を明記する」を規則にすれば読み違いは消えるが、代わりに**全ての節が帰属欄を持ち、その正しさを誰も検査しない**。緑が「見ていない」を意味する行が 1 本増えるだけである。ここには起きた事実だけを置く。

### 取りこぼしの可能性

**「全数」と呼べるのは JSON / YAML の構成宣言についてだけである。**次は面として数えていない。

- `SKILL.md` / `agents/*.md` / `commands/*.md` の front matter（YAML 宣言だが `.md` なので今回の glob に入らない）
- `references/*.md` の台帳（`spec-registry.md` の SR-ID 表など）。K-002 系で個別に扱っている
- `README.md` の表
- `.claude-plugin/plugin.json` の `hooks.PostToolUse` の**中身**（matcher / command）

### 経路の種別に「提示」を足す

K-002 の census は経路を hook / pytest / SKILL・commands・agents / prompts / 他スクリプト / 手動のみ で数えたが、**exec-p0 の訂正により「提示」を足す必要がある**。`hooks/hook-postgen-eval.py` は `evaluate-deck.js` / `validate-report-visual.py` / `validate-report-layout.js` を**実行せず、コマンド文字列を `additionalContext` へ出す**（docstring 25-26 行目に設計意図として書かれている）。実行するかは LLM 次第である。K-002 はこの 3 本を「hook 経路あり」と数えたので、**あの census の「無経路 1 本」はさらに下がる方向へ訂正される**。

### 上表の「有」は上限であって下限ではない

**「読む実行体が在る」と「実際に読まれる」は別の数である。**上表の有無は前者しか測っていないので、**上限側の数**である。下限は「その読み手が自動で起動されるか」で決まる。読み手 11 本について起動経路を測った（harness root 5372 ファイル、suffix `.py .js .cjs .mjs .ts .sh .md .json .yaml .yml`、除外は上記と同じ、**2026-08-14 15:14:48**）。

- **`lint-vendor-parity.py` は自動経路が 1 つも無い。**pytest 0・hook 0・SKILL 0・command 0、`scripts/run-ci-checks.sh` にも無い。**手動でしか走らない。**したがって `vendor-digest-manifest.json` の `local_fork_managed` 17 件と `subtrees` 5 件は「読み手 有」だが、**下限は 0** である。**対照**: 同じ `grep -c` を同じ `run-ci-checks.sh` に当てて `lint-skill-completeness` は **3 件**（rc=0）、`lint-vendor-parity|lint-contract-drift|lint-count-parity` は **0 件**（rc=1）。同一ファイル・同一コマンドで割れているので、grep が壊れて 0 になったのではない。
- **`validate-slide-layout.js` は hook 内で実際に実行される**（`hook-postgen-eval.py` 436・464 行が `subprocess.run`、docstring 27 行に「例外 2: slide の実描画レイアウト契約は hook 内で実行する」と明記）。**提示ではない。**よって `frame-contract.json` の `min_stage_fill_ratio` などは下限も有。
- `validate-structure.js` / `render-slide.cjs` / `validate-slide-skeleton.py` は pytest 3-5 本ずつが到達する。**自テスト以外**が含まれるので下限 > 0。

**したがって、他者の census と数字を並べるときは「有」をそのまま足さないこと。**exec-p0 の 6-8 は「LLM が実行すれば走る」ので上限は動かず下限だけ下がる。こちらの `lint-vendor-parity.py` 系 21 件は「人が手で叩けば走る」ので、**同じく上限だけの数である**。上限どうし・下限どうしで比べる。

### 「無」は書式一般でなくこのプラグインの事実か

K-006 で `harness.mechanical` について取った切り分け（`plugin-dev-planner` が**自プラグインの**同じキーを読んで assert している ＝ 書式の問題ではなく配線の問題）を、他の面にも当てた結果。

- **このプラグイン固有**: `EVALS.json` の全キー（他プラグインに読み手の実例あり）
- **書式一般が読まれていない**: `workflow-manifest.json` の `resources[]` `phases`（repo 全体で `is_file()` しか無く、**どのプラグインでも読まれていない**）、`plugin-composition.yaml` の `kind: agent`（共通 lint に分岐が無いので**全プラグインで同時に無検査**）
- **切り分け未実施**: `frame-contract.json` `registry.json` `visual-derivation-table.json`（このプラグイン固有の書式で、比較対象になる他プラグインが無い）

**この区別で直し方が変わる。**書式一般の側は共通 lint に分岐を 1 つ足せば全プラグインが一度に対象になり、固有の側は配線を 1 本引くだけである。

### 直さない

runner も突合テストも書かない。理由は K-006 と同じで、**書いた瞬間、一度も検証されていない宣言が一斉に効き始める**。特に `workflow-manifest.json` の `resources[]` 80 件は、存在確認すらされたことが無い。

**なお `plugin-composition.yaml` の `kind: agent` 17 件と `EVALS.json` の `harness.mechanical` 14 件は、性質が違う。**前者は「repo 共通 lint に分岐が無い」ので、分岐を足せば 17 件が一度に検査対象になる。後者は「このプラグインだけ配線されていない」（K-006 の対照で確認済み）。**片方を直す手が他方に効くと考えないこと。**

---

## K-009 slide の hook は最悪ケースで plugin.json の 45s を超える — 8/15 明けまで直さない

**測定日 2026-08-14。** 測り方: `hooks/hook-postgen-eval.py` の定数と各 `subprocess.run(..., timeout=)` の値を読み、slide mode の呼び出し順に沿って最悪値を積んだ。**実時間は測っていない。**timeout 値の合計であって、観測された所要時間ではない。

**定数**（54-66 行）: `HOOK_BUDGET_SEC = 45` / `SVG_LINT_TIMEOUT_SEC = 8` / `LAYOUT_MIN_BUDGET_SEC = 12` / `HOOK_BUDGET_MARGIN_SEC = 3`。`plugin.json` の hook `timeout` も **45**。

**slide mode の呼び出し順と上限**:

| 順 | 行 | 検査 | 上限 |
|---|---|---|---|
| 1 | 512 | `run_svg_diagram_lint` | 8s（固定） |
| 2 | 513 | `run_information_lint` | 8s（固定） |
| 3 | 514 | `run_linebreak_gate` | 8s（固定） |
| 4 | 542-543 | `run_slide_layout_gate` | **残余** = 45 − 経過 − 3 |
| 5 | 544 | `run_visual_generation_gate` | 8s（固定） |

1-3 が上限まで使うと経過 24s、4 の残余は 45 − 24 − 3 = **18s**。ここまでで 42s（マージン 3s は温存されている）。ところが 5 は**残余を見ずに固定 8s** を取るので、24 + 18 + 8 = **50s** となり 45s を 5s 超える。**マージン 3s は 4 の呼び出ししか守っていない。**

**超えたときに失うのは 5 だけではない。** hook はプロセスごと打ち切られ、`additionalContext` は 1 文字も返らない。**先に終わっていた 1-4 の判定も一緒に消える。**部分結果が残らない形なので、「重いデッキほど検査が薄くなる」ではなく「重いデッキでは検査が丸ごと無かったことになる」。しかも打ち切りは静かなので、**赤が出ないことと検査が走らなかったことが画面上で区別できない**。

**これは未検出ではなく未測定である。**超過が起きる条件——重いデッキ、遅いマシン、5 本のいずれかが上限近くまで粘る状況——で観測した人はいない。実測に使った fixture は 1274 bytes の 2 面デッキで 5 本合計は 1 秒未満だが、それは**超過しない条件で観測すれば超過しないことが分かっただけ**である。**小さい入力で起きないことは、大きい入力で起きないことの根拠にならない。**この項目は「起きた」の記録ではなく「起こりうるが誰も当てていない」の記録である。

**直し方の候補 2 つ。どちらも未検証**（コードを読んだだけで、走らせて確かめていない）:

- **A: 5 を 4 の前へ移す。** 5 は固定 8s なので、順序を入れ替えれば残余計算が最後に来て収まる。ただし `additionalContext` の並び順が変わり、読み手（deck-evaluator）が順序に依存していないかを確かめていない
- **B: 5 も残余から取る。** 4 と同じく `remaining` を渡す。ただし 4 には `LAYOUT_MIN_BUDGET_SEC` に相当する下限があり、5 にはその下限値が決まっていない。**下限を決めずに残余を渡すと、残余 0.2s で起動して必ず timeout する**——それは `unknown` になるので黙りはしないが、毎回 unknown が出れば K-004 と同じく「鳴り続ける通知」になる

**直さない理由**: 8/15 本番のデッキは凍結中で、hook の実行順は生成結果ではなく**生成中の画面**に効く。本番前に変える種類の変更ではない。**8/15 明けに。**A / B のどちらを採るかも決めていない。

---

## K-010 実行指示の宛先に実行手段が無い（「第 6 の状態」）— 8/15 明けまで直さない

**形**: 規則も実行体も経路も在る。経路は「この agent がこの検査器を実行する」と書いてある。ところがその agent の frontmatter `tools:` に `Bash` が無く、**指示された相手に実行する手段が無い**。V-020 の「既定経路では通らない」（4 つ目）でも、「経路が実行でなく提示」（第 5）でもない。**経路は実行を指している。実行できる者がそこに居ない。**

**母集団と数**: `agents/*.md` **17 本**（全数）。`tools:` に `Bash` が無いのは **6 本** — `d3-diagram-designer` / `data-visualizer` / `hearing-facilitator` / `html-generator` / `report-structure-designer` / `structure-designer`。うち prompt 側（`skills/*/prompts/R*.md` **17 本**）で検査器の実行を指示されているのが **4 本**、実行指示は **18 行**、名指しされる検査器は **5 本**。

走査した prompt は 17 本。うち 16 本が `skills/run-slide-report-generate/prompts/`、2 本が `run-cross-deck-review` と `run-slide-report-modify` の配下。**最初 1 ディレクトリだけ見て 16 本と数えた**が、この 2 本の agent は `Bash` を持つので結論は変わらない。分母の取り違えとして残す。

**検査器 5 本の到達判定**（別経路で実際に走るか）:

- `precheck-layout.js` — **どこからも実行されない。** repo 全体で 3 ファイルにしか現れず、うち 1 つは**自身の usage コメント**
- `validate-d3.js` — pytest は在るが `_d3_tree(tmp_path, ...)` が合成ツリーへ `shutil.copy` するため、**生成物には届いていない**。K-002 の教訓の逆向き（分類だけで「届いている」と決めない）
- `validate-information-priority.py` — orchestrator 側から届く
- `validate-svg-diagram.py` — hook 1b から届く
- `validate-slide-skeleton.py` — 実ツリーの pytest から届く

**`precheck-layout.js` を hook 1c で代替できない理由**（これを書かないと、次に読む人が「重複だ」と消す）: precheck は `<structure-path>` を取る**生成前**の検査で、hook 1c の `validate-slide-layout.js` は**生成後の HTML** を見る。**対象物も時点も違う。**片方が在れば他方が要らない関係ではない。

**取りうる案**: A = 各 agent の `tools:` へ `Bash` を足す / B = 実行を orchestrator 側へ移す（**手本が既に repo 内に在る**。`validate-information-priority.py` はすでに orchestrator 側で走っている）/ C = prompt から実行指示を落として提示だけにする。

**自己矛盾の実例**: `agents/html-generator.md` は 7 行目 `tools: Read, Write`、47 行目「…を変更した場合のみ `Bash(python3 ".../validate-slide-skeleton.py")` を通す（0=PASS）」、53 行目 Outputs「**実行したコマンド**…を caller に返す」。同一ファイルの中で、実行手段を持たない宣言と、実行の指示と、実行報告の要求が並んでいる。

**見立て（見立てであって決定ではない）**: `precheck-layout.js` だけは B（orchestrator へ移す。手本が在るので新規発明が要らない）。残り 4 本は既に別経路で走っているので、**重複した実行指示の整理**が筋。直すのは 8/15 明けで、そのとき `R1-orchestrate.md` と `SKILL.md` を触るため合同便になる。

**対照（この形が「全部そう」ではないことの固定）**: 実行指示が **0 行**の agent が 2 本実在する（`data-visualizer` / `hearing-facilitator`）。また `prompt_ref` の実在は **17/17**。壊れているのは経路の一部で、宣言そのものではない。

---

## K-011 `SERIES_SUPPLY_NO_DASH` が SERIES 要素数と別ファイルで二重管理 — 8/15 明けに判断

`scripts/validate-svg-diagram.py:318` の `SERIES_SUPPLY_NO_DASH = 4` は、`vendor/scripts/svg-kit.cjs` の `SERIES` の要素数（実測 4）を**直値で別ファイルへ写したもの**。D27 が 2408 / 2414 行で使う。片方が動いても他方は黙っている。**管轄は count-parity ではなく drift**（count-parity へ入れると同じ事項の正本が 2 つになる）。今日は `_KNOWN_GAPS` に触らない（count=7 の基準線を失うため）。

---

## K-012 golden の glob は 2 口では閉じない

`examples/diagram-goldens/` の golden は 3 階層に分かれている。直下 **53 本**（手書き）、`builders/` **11 本**（`*-spec.json` 由来）、`production/` **2 本**（**`*-svgspec.json` 由来**）で計 **66 本**。`diagram-goldens/*.html` と `builders/*.html` の 2 口だけを書くと `production/` の 2 本が落ちる。**由来ファイルの綴りも違う**ため、再生成側で `-spec.json` を拾う書き方をしても同じ 2 本が落ちる。実際に glob 側と再生成側の両方で落ちた（2026-08-14）。**階層が原因なので、次に書く人も同じ 2 本を落とす。**

---

## K-013 5 系列が要求された日に何を選ぶかは未決

`SERIES`（`svg-kit.cjs`）と `COLOR_PALETTE`（`svg-builder.cjs`）はどちらも 4 枠。**5 系列を要する図は作れない。**これは制約であって欠陥ではないが、5 系列が要求された日に何を選ぶか（区分を畳む／別の符号軸を足す／意匠を 4 色から増やす）は決まっていない。**決めずに放置すると、その日に一番安いもの（供給表に 1 枠足す）が選ばれる。**なお過去 2 回とも、足された 5 枠目は 1 枠目と同じ値だった。
