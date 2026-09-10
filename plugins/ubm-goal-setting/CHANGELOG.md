# Changelog

## 0.3.43 - 2026-09-10

PR #74（`feat/ubm-yt-ingest-20260720`）が持っていた 45 件のナレッジを、現行 main の採番へ載せ替えて取り込んだ。総 entry 937 → 982。取り込み元は 2026-07-22 の熱海リトリート（14 件）、2025-09-07 の YouTube（8 件）、2025-08-31 の YouTube（6 件）、および既取込 3 本への追加分（17 件）。

**なぜ rebase ではなく載せ替えだったか。** entry ID `<PREFIX>-<NNN>` はカテゴリ内の共有連番であり、採番は「取り込んだ順序」に依存する。PR #74 は merge-base（386 entry）の上で 386→431 と採番したが、その後 main が独立に 937 entry まで伸びたため、**45 件すべてが既存 ID と衝突していた**。これは「198 コミット遅れている」ことの症状ではなく、ID の生成規則そのものが分岐に耐えない設計であることの帰結で、rebase では解けない。中身は変えず ID だけを main の続きへ振り直し、`related` の相互参照も同じ対応表で張り替えた（解決不能な参照 0 件）。

**既存ファイルは 1 行も書き換えていない。** knowledge JSON の整形はファイル間で（indent 1 空白 / 2 空白）も、同一ファイル内の entry 間で（`tags` の inline / block）も揺れており、再直列化では 119 ファイル中 99 ファイルしか原文を再現できない。よってファイル全体の書き出しは行わず、`entries` 配列末尾への**テキスト挿入だけ**で追記した。過去の取込が sync-log の `warnings` に残した「既存整形に合わせて書き出し、差分を追加分に限定した」と同じ扱いである。

**500 行ゲート（`check-knowledge-split.py`、`test_vendored_knowledge_passes` で CI 強制）に触れる 6 ファイルは、追記せず新規サブトピックへ逃がした。** 分割は行数合わせではなく主題で切っている。

- `action-guides-thinking-day.json` — 考える日を予定としてロックする
- `principles-business-execution-alignment.json` — 決定後は反対しない鉄の規定・外交を業績へ紐付ける
- `principles-business-growth-structure-shift.json` — 収益構造の段階移行・挑戦しやすさを設計目標に置く
- `principles-relationship-money-for-others.json` — 責任の肩代わりとしてのお金・余剰資金は広告でなく人へ
- `principles-relationship-interest-in-people.json` — 人への興味が指導の前提・照準は会社でなく個人
- `mindset-strength-from-people-and-context.json` — 事業を支えるのは自分の実力・数字・影響力ではなく人との関わりと文脈

最後の 1 件は 4 entry が別々の主題に見えて、実際は同一の軸（成果と支えの**帰属先**の置き直し）の 4 つの現れだったため 1 ファイルにまとめた。ほかに PR #74 由来の新規ファイルが 6 件（組織変革・地域との関わり・救済・顧客維持・権限委譲・社会貢献）。

`router.json` の `entry_count` / `subcategory_counts` / `total_entries` はディスク実測から再計算し、PR #74 が既存ファイルへ足していたタグは merge-base と突き合わせて**増分だけ**合流させた。`quick_lookup` の参照は分割後の実ファイル名へ写している。

## 0.3.42 - 2026-09-10

`skills/run-skill-feedback/SKILL.md` へ加えかけた変更（`combinators` 宣言と `OUT3` 基準）を撤回した。

このファイルは 21 プラグインに配置されている**共有スキルで、全コピーがバイト単位で同一に保たれている**（`scripts/lint-plugin-lint-coverage.py` の「symlink 共有 (run-skill-feedback 等)」がその前提）。harness-creator 側の `eval-log/.../elegance-verdict.json` は対象を `skill_md_sha256` で pin しており、1 つの verdict が全コピーを射程に持つ設計になっている。ubm-goal-setting の 1 コピーだけを書き換えたことでハッシュが `1b957a02…` → `8c987925…` へ乖離し、その verdict の射程から外れて `OUT1`/`OUT2`/`OUT3` が検証不能になっていた。

`combinators` 宣言の欠落（PKG-014）は 21 コピーすべてに共通する指摘であり、ubm-goal-setting 単独で直す対象ではない（PKG-003 と同じ構造）。1 箇所だけ直すと共有の不変則が壊れる。**したがって解決は「verdict を作る」ことではなく、共有ファイルの同一性を回復すること**だった。

- ubm-goal-setting 固有の 4 スキル（`run-ubm-goal-setting` / `run-ubm-journal` / `run-ubm-knowledge-sync` / `run-ubm-youtube-ingest`）への `combinators` 追加は、共有ファイルではないため維持している。

## 0.3.41 - 2026-09-10

「売上に直結する成果目標」と「直感的に読める出力」の2点を、記法そのものを変えることで構造的に担保した。指摘は「この行動をすれば売上が上がるのかが直接見えない」「文章が羅列していて読みにくい」の2つ。どちらも書き手の努力目標ではなく、書式が許していた抜け道だった。

### 成果目標を1項目=2行にし、貢献額を式で書かせた

- 旧: `- Aさん：月額顧問の成約1件　期日7/2　→ 売上貢献：150000`（横に長く、金額が読み飛ばされる）
- 新:
  ```
  - Aさん：月額顧問の成約1件（初月分）　期日7/2
    → 売上貢献：50000 × 1 = 50000
  ```
- **貢献額には「検算できる根拠」の随伴を必須にした**（C1）。式 `<単価> × <件数> = <貢献額>`、または括弧の根拠 `<貢献額>（値引き後の一括見積）` のいずれか。`150000` とだけ書かれた裸の数字は、それが正しいかを後から誰も検算できないので FAIL。
  - 当初は「式を必須・裸の数字は禁止」としたが、検算（C1c）が式のときだけ走るため、**式で書いた者だけが FAIL のリスクを負う**逆インセンティブになっていた（`50000 × 3 = 200000` は FAIL、`200000` は PASS）。上位概念「根拠の随伴」へ持ち上げて解消した。
  - 同時に、貢献額 0 のときだけ括弧を要求していた **C1b を C1 へ吸収して廃止**。金額的に重要度の低い側にだけ厳しい歪みだった。検査は1つ減り、守備範囲は広がっている。
- **検査 C1c（式の検算）を新設**。`50000 × 2 = 150000` のような計算違いを FAIL にする。式を書かせる意味は、検算されて初めて生まれる。
- **検査 C1e（計上期間）を新設**。件数に期間単位（`ヶ月`／`ヵ月`／`か月`／`年`）を掛けた式を FAIL にする。計上するのは対象期間に実際に売上として立つ分だけで、月額顧問なら今週は初月分だけ。`50000 × 3ヶ月` は「今週の売上目標」を3ヶ月分で水増しする書き方だった。
- **検査 C4b（見出しの金額照合）を新設**。行動グループ見出しの `（{金額}円）` が、参照先の成果目標の貢献額と一致しない場合に FAIL。見出しは参照名の左辺しか照合していなかったため、`（9999999円）` が素通りしていた。
- **検査 C1d（貢献 0 の偏り）を新設**（WARN）。貢献 0 が成果目標の過半を占めると、売上から逆算したはずの期間が実際は次期の仕込みだけになる。成果目標が1件しかない期間は母数が小さすぎるため判定しない。FAIL にしないのは、通すために嘘の金額を書く誘因を作らないため。

### 行動目標を成果目標ごとにグループ化し、優先度A/B/C を廃止した

- 旧: 行動ごとに `  → 支える成果目標：XXX` を1行ずつ添え、別軸で `### 優先度A/B/C` に分類していた。同じ成果を支える行動が優先度をまたいで散らばり、「この成果のために何をするのか」を読むには全体を走査する必要があった。
- 新: `### → Aさん：月額顧問の成約（50000円）` の見出しでまとめ、その配下に `- [ ]` を並べる。**優先順位は貢献額の大きいグループを上に置くことで表す**（優先度という別軸を持たない）。
- 見出しが無い場合は旧記法の行内注記へフォールバックするため、既存ファイルは読める（C4）。
- `## 【今週の行動目標（行動管理・優先順位付き）】` の**セクション名は変更していない**（Daily.md の embed が参照するため）。中身の組み方だけを変えた。

### 売上直結性のヒアリングを深掘りした

- R3 のターン 3C-3 で **単価と件数を分けて聞く**ようにした。
- **ターン 3C-3b を新設**（成果1件につき必ず1回）。挙がった成果が売上に直結しない3類型（入金が期間外／もう一段の判断が要る／単価が未確定）を提示し、2つめに当たる場合は成果を「後ろの判断」へ置き直す。ユーザーの回答を受け取らずに成果目標を書き起こすことを禁止した。

### その他

- **架空の人名（田所さん・佐久間さん・久保田さん）を `Aさん`〜`Fさん` のプレースホルダへ置換**。実在しそうな人名を手本に置くと、LLM が書式ではなく名前まで模倣し、読み手も「これは自分のどの案件か」と照合を強いられる。ユーザーから出所を問われたこと自体が、可読性の問題として現れていた。
- 追随したファイル: `output-formats.md`（正本）、`data-contract.md`（#13・C1〜C5）、`validate-goal-output.py`、`golden-sample-weekly.md`、`R3`／`R4`／`R5`、`output-formatter.md`、`action-goals-best-practices.md`、`interview-quick-templates.md`、`SKILL.md`、`RUNBOOK.md`。1週間・1ヶ月・3ヶ月の全種別で共通（期報は月報テンプレートの読み替え）。
- **手本が新しい規則を破っていた3箇所を是正**。`golden-sample-weekly.md`・`output-formats.md` の一貫例・`output-formatter.md` の OK 例がいずれも `50000 × 3 = 150000`（月額顧問3ヶ月分を今週に計上）で、C1e の計上期間規則に反していた。**規則を導入した同じ変更セットの中で、3つの手本が同時にその規則を破っていた**。初月分 `50000 × 1 = 50000` へ組み直し、連動する売上目標・合計・グループ見出しの金額・振り返り項目を再計算した。
- **「機械検査される規約」と「あえて検査しない規約」を分離**。`output-formats.md` の「表記仕様（機械検査対象・厳守）」という見出しの下に、実際には検査していない規約（グループの並び順など）が混在していた。表記仕様を「貢献額の統一規則」「計上期間の規則」「売上目標との突合」（以上、機械検査対象）と「読み手向けの推奨（機械検査しない）」の4ブロックへ分け、非検査の判断は理由付きでコードのコメントにも残した。実装漏れと意図的な非検査を区別できるようにするため。
- テスト: 旧記法に依存していた9件を新記法へ移し、C1・C1c・C1d・C1e・C4b の検査に計21件を新規追加。
- **記法の劣化を CI で捕まえる検査を新設**（`tests/test_notation_consistency.py`、24件）。今回「規則を変えたのに手本3箇所が旧記法のまま残った」ことが、コミット直前まで誰にも観測されなかった。原因は構造的で、`golden-sample-weekly.md` だけが validator に実際にかけられており、**正本・契約・対話プロンプト・agent 定義に埋め込まれた例はどこからも実行されない**。しかも旧記法は FAIL せず PASS するので、劣化は静かに保存され続ける。
  - 記法を持つ12ファイルを台帳としてテスト内に列挙し、各ファイルの `→ 売上貢献：…` 行を C1（根拠の随伴）・C1c（検算）・C1e（計上期間）にかける。廃止した `### 優先度A/B/C` の残存も検査する。
  - 規則は `validate-goal-output.py` から `importlib` で読み込み、**正規表現をテスト側へ複製しない**。複製すると、規則を変えたときに「validator は新しい規則・テストは古い規則」でテストだけが緑になり、今回と同じ盲点をもう一段深い場所に作る。
  - 違反例をわざと書いている行（`✗` `FAIL` `NG` などの印がある行、および直前のラベル行の直後1行）は免除する。**免除には行に明示的な印があることを要求する**。印を不要にすると免除範囲が本文の書きぶり次第で伸縮し、検査が空洞化する。印を要求すれば「反例には印を付ける」規律が本文側に課され、人間の読み手にも「どれが手本でどれが反例か」が一目で分かる。
  - 検査対象は貢献行75行中63行（免除12行）。5種の違反（裸の数字／計算違い／期間単位／廃止記法／台帳ファイルの消失）を注入して、いずれも検出されることを確認済み。
- 合計 `392 passed`。

### 前回（0.3.40）の実装バグ修正（CHANGELOG 未記載分）

- **F-07**: `_current_outcome_items()` が箇条書き行だけを拾い、注記行を落としていた。
- **F-6 / F-09 / F-11 / F-12**: 参照名の空白正規化、`→` より前を項目名とする切り出し、期間語の取り違え、dangling 判定の取りこぼしを修正した。

## 0.3.40 - 2026-09-10

0.3.39 で入れた逆算契約を全体に行き渡らせ、**重複・矛盾・暗黙のスコープ**を解消した。多角的レビュー（reset-observer / logic / meta / system の4系統）の指摘に基づく整合作業で、契約そのものは変えていない。

修正した矛盾:

- **月報・期報のテンプレートに `→ 支える成果目標：` の指示が無いのに、検査 C4/C5 は全種別で走っていた**（0.3.39 で作り込んだリグレッション）。テンプレートに忠実な月報は必ず FAIL する状態だったため、`output-formats.md` の月報テンプレートに指示と記述例を追加した（期報は月報の読み替えのため同時に解消）。
- **実行完了型 NG 動詞リストが4版に分岐していた**（validator=10語／output-formatter=10語／output-formats=9語／data-contract・R3=7語／R5=「等」）。追加のたびに検査層だけが更新され、宣言層・対話層へ伝播していなかった。`output-formats.md`「成果目標と行動目標の区別」の10語を**唯一の正本**と宣言し、他ファイルはリストを複写せず参照する形に統一した。
- **`action-goals-best-practices.md` の実例が同ファイル18行下の NG 規定と S2（`・` 禁止）の両方に違反していた**（`森田さん：単価合意1件・業務委託開始1件`）。「短縮せず2件に割る」の実演として2行へ分割した。
- **ゴールデンサンプル自身が正本違反を含んでいた**。実績セクションの抽象的状態表現（`（達成・売上150000）`）を件数＋完了日へ、差分セクションの理由文を差分数値へ、【現在事業パートナー数】の `3社（月額顧問1社・協業2社）` を半角数字 `3` へ修正。LLM が参照する品質基準が禁止形を再生産していた。
- **`output-formatter.md` が存在しない見出しを正本として参照していた**（「プロジェクト別タスクと習慣目標の適用範囲」はプラグイン全体で0ヒット）。実在する `data-contract.md` 契約表 項目18/19 へ差し替えた。
- **同じ例が別数値で複製されていた**（勉強会の参加者 5名 と 3名）。5名に統一。

明示した暗黙のスコープ:

- **「やらないこと」の独立セクション廃止は週報のみの措置**だった。月報・期報では `## 【今月/今期やらないこと（明確に排除するもの）】` が validator の必須見出しに入っており必須のまま。この種別依存がどこにも書かれておらず、9か所の「3項目以上」要求と週報の廃止宣言が矛盾して見えていた。`output-formats.md` の廃止宣言に **【適用範囲: 週報のみ】** を明記し、`data-contract.md` #16・§4.4・§4.5、`output-formatter.md`、`phase3-coordinator.md`、`SKILL.md`、`README.md`、`RUNBOOK.md` の記述を種別依存へ揃えた。あわせて §4.5 の weekly 必須セクション一覧から誤って載っていた「やらないこと」を削除し、実装（`validate-goal-output.py` の週報必須リスト）と一致させた。
- **突合の 5% 許容が宣言層に存在しなかった**。実装（`judge_sales_coverage()`）と CHANGELOG にしか無く、ドキュメント13か所は「合計が売上目標に届くこと」としか書いていなかった。`output-formats.md` の逆算章に判定の三段（OK / 5%以内 WARN / 5%超 FAIL / 目標0は INFO）を明記した。
- **`execution-prompts.md` の Step 番号衝突**（Phase 1-2 の収集タスク番号と Phase 3 の対話段階が同じ「Step N」）に読み方の注記を追加した。

解消した重複:

- **`assets/interview-quick-templates.md` が R3/R4 とは別系統の対話フローを丸ごと保持し、しかも旧設計（行動目標ありき）のままだった**。週報ターン3は最重要数字から入り、`売上貢献` は全370行で0ヒット、月報・期報は「成果目標＋行動目標」を1ターンで一括して聞いていた。このファイルは Phase 3 開始時に並列 Read されるため、旧順序での質問を誘発していた。冒頭に **「ターン構成・設計順序・完了条件の正本は R1〜R5 であり本ファイルではない。ターン番号は 1:1 対応しない」** と位置づけを宣言したうえで、週報・月報・期報の該当ターンを売上 → 成果 → 行動の逆算順へ書き換えた（成果ターンに売上貢献の割り付け、行動ターンに `→ 支える成果目標：` を追加）。あわせてプロジェクト別タスクの週報既定省略と、やらないことの週報出力先を注記した。

追記した仕様:

- `data-contract.md` §4.4 の validator 仕様表が13項目のままで、0.3.39 で新設した検査が1行も載っていなかった。**逆算チェーン検査 C1〜C6** と**シンプルさ検査 S1〜S3** の表を追加し、各 ID の判定区分・閾値・正本の所在を明記した。

更新したファイル: `references/output-formats.md`／`references/data-contract.md`／`assets/interview-quick-templates.md`／`assets/golden-sample-weekly.md`／`assets/action-goals-best-practices.md`／`assets/execution-prompts.md`／`prompts/R3-step3-goal-setting.md`／`agents/output-formatter.md`／`agents/phase3-coordinator.md`／`SKILL.md`／`README.md`／`RUNBOOK.md`。

検証: `tests/` 全348件 PASS。`golden-sample-weekly.md` は修正後も `validate-goal-output.py --type weekly` で エラー0件・警告0件。

## 0.3.39 - 2026-09-10

目標設定を **売上 → 成果 → 行動** の逆算へ作り直した。週報・月報・期報の3層共通。従来の記述は削除して置き換えており、新旧は併存しない。

修正した問題:

- ドキュメント（`output-formats.md` / R3 / R4）には「売上→成果→行動で逆算する」と書かれていたが、`validate-goal-output.py` が連鎖を一切検査していなかった。検査されないルールは実質存在せず、生成物は行動ありきに戻り続けていた。
- 同梱の `golden-sample-weekly.md` 自身が「体験診断セッションを3件実施する」という**実行完了型**を成果目標に置いていた。LLM が参照する品質基準そのものが、指摘された型を再生産していた。
- 成果目標と売上目標を結ぶ数値が存在しなかった（`売上貢献` はリポジトリ全体で0ヒット）。「この成果を達成したら売上がここまで動く」という線が引けていなかった。

契約の変更:

- **成果目標に `→ 売上貢献：<半角数字>` を必須化**。その期間の売上に直接乗らないものは `→ 売上貢献：0（理由）`。欠落は FAIL。
- **成果目標に実行完了型を禁止**（実施する/開催する/参加する/送付する/作成する/提出する/共有する/告知する/打診する/連絡する）。「勉強会を月4回開催する」型は FAIL。行動目標側へ移す。
- **行動目標に `→ 支える成果目標：XXX` を必須化**し、XXX が成果目標セクションに実在するかを検査（dangling は FAIL）。習慣・土台のみ `（土台）`／`（関係維持）` を免除。
- **支える行動が0件の成果目標を WARN** で報告（成果側から見た抜けの検出）。
- **売上貢献の合計と売上目標を突合**（`judge_sales_coverage`）。完全一致は求めず `合計 >= 売上目標` で PASS（超過は取りこぼし前提の積み増しでありうる）。未達が売上目標の5%以内は WARN、それを超える未達は FAIL で保存を止める。売上目標0の期間は判定せず INFO。メッセージには合計・売上目標・不足額の実数を必ず出す。
- **対話を往復化**: R3 に 3C-2（相手の列挙）／3C-3（相手ごとに先方判断・期日・売上貢献を1件ずつ）／3C-4（実行完了型の組み替え）／3C-5（合計と売上目標の突合）を追加。R4 に 4A-1（準備→資料作成→実施→フォロー）／4A-2（当たり前の土台へ逃がす）／4F（網羅性の双方向確認）を追加。まとめて書かせず、必ずユーザーとの往復で降ろす。
- **シンプルさの上限を追加**（複雑な目標は自分で自分を複雑にし、実行されなくなるため）。成果目標は5件・1項目50字（`→ 売上貢献` の前まで）・`・` による複数成果の詰め込み禁止。行動目標は8件・1項目60字（1行目・期日込み）。いずれも超過は FAIL。上限は逸脱の検出線であり、狙う長さではない（手本は成果 21〜28字・行動 25〜30字）。
- **シンプルさの対話ターンを追加**: R3 に 3C-6（成果目標の件数・長さ・1項目1成果の点検）、R4 に 4G（行動目標の件数・長さ・1項目1動作の点検）。どちらも必須で、「短くする」のではなく **2件に割る／注記行へ移す** よう促す。R5 の基本チェック2 も「済/未済の二値性とシンプルさ」へ拡張。
- **バグ修正**: 種別ごとの期間語を `KIND_PERIOD_WORD` で固定。`今(週|月|期)` の緩いマッチだと、週報で期アンカー【今期の売上目標】（3ヶ月分）を今週の売上目標として掴んでしまい、突合が壊れていた。

更新したファイル: `references/output-formats.md`（逆算章を全面置換）／`references/data-contract.md`（#13 と Step3→Step4 ゲート）／`prompts/R3-step3-goal-setting.md`／`prompts/R4-step4-action-plan.md`／`prompts/R5-step5-final-check.md`／`assets/golden-sample-weekly.md`（新記法へ全面書き換え）／`assets/action-goals-best-practices.md`／`agents/output-formatter.md`（品質チェック9項）／`SKILL.md`（Key Rules）／`scripts/validate-goal-output.py`／`tests/test_validate_goal_output.py`。

不変（この修正で変えていないもの）:

- 統一ハイブリッド構造21項目・ゾーンA/Bの分割・ロールアップ契約・見出し名。
- プロジェクト別タスクの種別方針（週報=任意／月報=必須／期報=禁止）・習慣目標・やらないこと3項目以上・NG精神論・期日トークン。

## 0.3.32 - 2026-09-03

`validate-goal-output.py` に **`--type` と本文タイトル見出しの不一致検出**、**`--peer` 層間整合チェック**、**`--help` の rc 修正** を追加。種別の取り違えと層をまたいだ値ズレが素通りしていた穴を塞いだ。

修正した問題:

- 同一の3ヶ月期報が `--type quarterly` でも `--type bimonthly` でも rc=0 で PASS していた。`TYPE_MAP` が両者を分岐キー `period` へ潰しており、以降の判定が元の `--type` を参照できず、タイトル見出しの検査が「3ヶ月の目標」「2ヶ月の目標」の両ラベルを無条件に受理していたため。
- `--help` が rc=2 を返していた。argparse が `--help` / `--version` で投げる `SystemExit(0)` を、例外ハンドラが一律 `return 2` に潰していたため。

契約の変更:

- **不一致は error（rc=1）**: `--type` に対応するタイトル見出しラベル（`weekly`=【1週間の目標】／`monthly`=【1ヶ月の目標】／`quarterly`=【3ヶ月の目標】／`bimonthly`=【2ヶ月の目標】）が本文と食い違う場合に FAIL する。エラー文は「引数側が旧種別」「ファイル側が旧種別」を書き分ける。
- **`--peer PATH`（任意・複数可）を新設**: 指定したときだけ他層のファイルを開き、期アンカー（今期の売上目標／今期の累計売上実績など）の3値を層間で突き合わせて **WARN** で報告する。`--peer` 未指定時のコードパスは従来と完全に同一で、既存の rc も変わらない。週報に存在しない期アンカーは `WEEKLY_EXEMPT_ANCHORS` で免除する。
- **`--help` は rc=0**: `SystemExit` ハンドラを `return 0 if e.code == 0 else 2` へ変更。不正な `--type` の rc=2 は不変。
- **読みの後方互換は維持**: 旧2ヶ月期報を `--type bimonthly` で再検証する経路は rc=0 のまま。`TYPE_MAP` のキー集合（argparse の `choices` の生成元）は不変。
- **内部整理**: `check_require_prefix` を `check_title_matches_type` へ統合。`Validator` は元の `--type` 値を `type_name` として保持する（第4引数・省略時は `kind` から逆引き）。script version 0.1.0 → 0.2.3。
- **テスト**: `tests/test_validate_goal_output.py` に期報の4パターン（quarterly×3ヶ月=PASS／bimonthly×2ヶ月=PASS／quarterly×2ヶ月=FAIL／bimonthly×3ヶ月=FAIL）、週報のラベル不一致、`--peer` の層間整合を追加。

不変（この修正で変えていないもの）:

- 種別別の必須見出し集合・NG表現・やらないこと3項目以上・プロジェクト別タスク方針。
- 不正な `--type` の rc=2。`--peer` 未指定時の検査内容と rc。

## 0.3.31 - 2026-09-03

期報を **2ヶ月目標から3ヶ月目標へ改定**。目標設定側（`run-ubm-goal-setting` / `info-collector` / `output-formatter` / `phase3-coordinator` / `/ubm-goal-setting`）の契約とドキュメントを3ヶ月へ統一した。

破壊的でない変更（後方互換あり）:

- **種別キーの改名**: `bimonthly` → `quarterly`。新規は `quarterly` を正とする。`bimonthly` は後方互換の別名として受理し続ける（`/ubm-goal-setting` の引数解釈・`validate-goal-output.py --type`・`workflow-manifest.json` の Phase0 gate・各 agent の入力契約）。`validate-goal-output.py` の `TYPE_MAP` は `quarterly` と `bimonthly` の両方を同一の分岐キー `period` へ写す。
- **ファイル命名**: 新規は `UBM - 3-月報（３ヶ月） - YYYY-MM-DD〜YYYY-MM-DD.md`。旧名 `UBM - 3-月報（２ヶ月） - …` と `UBM - 3-期報 - …` は読み取り・過去参照で受理を継続する（validator のファイル名チェックは `UBM - {1,2,3}-` プレフィックスと日付パターンのみを見るため旧名を弾かない）。

契約の変更:

- **期報の期間**: UBM の目標期間は月の最終月曜日起点。期報は対象3ヶ月分の月報期間の連結で、開始日=1ヶ月目の月報開始日／終了日=3ヶ月目の月報終了日（例: 7月・8月・9月分 → `2026-06-29〜2026-09-27`）。
- **ロールアップ元**: 月報2件 → **月報3件**。`info-collector` の quarterly 取得スコープを「直近3ヶ月の全週報 + 全月報（3件）+ 前回期報」へ変更。
- **validator**: 期報のサマリー見出しの必須判定を `## 【2ヶ月の目標】…` → `## 【3ヶ月の目標】…` へ変更。全角数字チェックの許容に `３ヶ月` を追加（`２ヶ月` は旧期報の後方互換で許容を継続）。なお本 branch で `validate-goal-output.py` に入った変更は 0.3.31 と 0.3.32 を合わせて 1 回の commit で、script version は `0.1.0 → 0.2.3` へ直行している（0.2.0 / 0.2.1 という中間状態は tree のどの commit にも存在しない。版数は 0.3.32 側にまとめて記録する）。
- **表示名**: 「期報（2ヶ月目標）」「2ヶ月目標」「２ヶ月」を3ヶ月へ統一。見出し名 `【今期の売上目標】` `【今期の累計売上実績】` 等は不変で、「今期」は3ヶ月を指す。

不変（この改定で変えていないもの）:

- 統一ハイブリッド21項目の構造・公式セクション順・採用案 A1（期報はヘッダーの `【今期の売上目標】` を出力しない）。
- プロジェクト別タスクの適用範囲（週報=任意／月報=必須／期報=禁止）。
- `weekly` / `monthly` の見出し集合・必須セクション・検証結果。

## 0.2.0 - 2026-07-11

北原さん YouTube 全量/自動同期と相談 capability、根拠付き knowledge / harness artifact graph consult を **非後退（additive）** で追加。既存 capability A（21 項目目標設定）/ B（6 カテゴリ同期）の契約は不変。

新設 9 component:

- **skills** (2): `run-ubm-youtube-ingest`（URL 単発 / 厳格全量 / scheduler 無人差分の 3 モード・2-source registry・caption→承認済み ASR fallback・冪等 one-shot）/ `run-ubm-consult`（具体解を処方しないコーチング型・考え方フレーム提示・read-only グラフ consult）。
- **command** (1): `/ubm-youtube-ingest`（skill の薄い運用アダプタ。3 モード相互排他検証 + `--source` / `--dry-run` 透過。手動 sync は scheduler one-shot と同一 cursor / idempotency key を共有し別状態を作らない）。
- **agents** (2): `youtube-transcript-normalizer`（C01・provenance 5 要素を保った正規化）/ `knowledge-relation-extractor`（C08・根拠付き有方向辺の抽出）。
- **scripts** (4): `check-youtube-backfill-completeness.py`（C03・content/accountability 被覆分離の完全性ゲート）/ `index-harness-artifact-graph.py`（C05・計画×実成果物 read-only 突合 index）/ `validate-knowledge-graph.py`（C06・依存グラフ決定論再生成+検証）/ `consult-harness-artifact-graph.py`（C07・デュアルグラフ read-only consult）。

配線（非後退 additive）:

- `.claude-plugin/plugin.json` の `entry_points` に 2 skill / 2 agent / 1 command を追加。version 0.1.0→0.2.0。
- `knowledge/youtube-registry.json` / `knowledge-graph.json` / `harness-artifact-graph.json` は build では作らず、one-shot 初回実行・各 script 実行時に運用生成（`--dry-run` は初期化も含め書込 0）。
- pytest に youtube one-shot 冪等（OUT1）・backfill 完全性・graph 検証・harness index/consult のテストを追加。既存テストは不変。

学び (lessons):

- **全量性の分母は authoritative snapshot 起点で固定する**: registry 側の除外（`terminal_unavailable` / `waived`）で分母を縮められないようにし、「取得不能を除外して緑に見せる」握り潰しを完全性ゲート（C03）で封じた。`waived` はユーザー承認参照（`waiver_ref`）必須。
- **手動入口と自動 scheduler は同一 one-shot を共有する**: 別系統の状態（cursor / registry）を作らないことで、手動確認・障害リカバリと無人同期の冪等性が同じ機構で保証される。手動 `--sync` と scheduler は同じ `video_id` を idempotency key とする。
- **計画グラフと実成果物グラフを分けて突合する**: task-graph（これから作る計画）を実成果物と誤同定しないよう、C05 が provenance / freshness 付きで正規化 index を作り、C07 はそれを read-only で引くだけに徹する。
- **相談は非処方スタンスを不変条件として機械的に自己検証する**: 「具体解を出さない」「各ターン引き出し質問 ≥1」等を `feedback_contract`（IN1/OUT1）で検証し、逸脱時は該当 phase を再実行する。
- **transcript は untrusted data として封じる**: 文字起こし本文中の命令 / URL を実行対象にせず、provenance のみを制御領域（frontmatter）に置く。

marketplace: 本 plugin は `distributable:false` を維持し、`.claude-plugin/marketplace.json` / `bundles.json` に **未登録**（個人利用前提の非公開）。

## Unreleased - 2026-07-05

elegant-review (harness-creator 仕様準拠監査) による改善 (version 0.1.0 据置・dev 未リリース):

- F1: plugin-composition.yaml の責務プロンプト tier を schema enum 非含の `supporting` から `ref` へ是正 (C08-C12)。
- F2: run-ubm-knowledge-sync の劣化重複 `prompts/R1-knowledge-extract.md` を削除。抽出責務の 7層正本は agents/knowledge-extractor.md が単独所有し completeness_exempt 宣言と実体を一致化。
- F3: references/package-contract.json の pkg_checks に PKG-009〜015 を実走 ground truth で追記し false-green を解消。
- F4: 両 SKILL.md に knowledge_loop 記述子 (pattern=router-registry) を追加し自己記述を補完。
- F5: 両 workflow-manifest.json の宙吊り `gate_order` (G1/G2/G3 は phase gate に非存在) を削除。
- F6: router 非参照かつ entries=0 の空 tombstone 7 件 (principles/consultation/phase-advice/action-guides/mindset/case-studies/principles-business.json) を掃除。

## 0.1.0 - 2026-07-04

- Ported UBM goal-setting and review dialogue into one plugin with two run skills.
- Added UBM knowledge sync with registry-based MD5 detection and six-category extraction guidance.
- Added 10 agent prompts, 2 slash commands, 3 stdlib Python scripts, and the vault write-path guard hook.
- Seeded L1 curated knowledge JSON, shared schema/router, registry, and empty sync log.
- Added pytest coverage for deterministic scripts and write-path guard behavior.
