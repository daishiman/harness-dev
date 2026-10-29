# spec-state.json 契約 (plugin 共有データ契約 / SSOT)

`run-system-spec-elicit` が生成・更新するヒアリング状態ファイル。C01/C03/C11/C12 が同一形状を前提にする。**状態書込は `scripts/apply-spec-transition.py` の一経路のみ**が行う (単一 transition writer)。

## 正本位置 (canonical location・SSOT)

`spec-state.json` の正本は **`$CLAUDE_PROJECT_DIR/system-spec/spec-state.json`** の 1 経路のみ。commands (C05/C06)・writer (`apply-spec-transition.py`)・consumer (C03/C11/C13) はこの単一の正本パスを読み書きする。取得資料の記録ファイル `fetched-references.json` も同ディレクトリ配下 **`$CLAUDE_PROJECT_DIR/system-spec/fetched-references.json`** に置く。生成物 (章 Markdown・index) も同じ `system-spec/` に集約するため、`plugin.json` の `permissions.filesystem: $CLAUDE_PROJECT_DIR/system-spec/**` が正本・生成物・記録の全てを被覆する (F4: 追加 permission 不要)。

- **暗黙前提の禁止**: 「cwd 直下」「repo root 直下」「配下を rglob で探索」などの位置前提を各 component が独自に持ってはならない。位置は本節の正本パスに一意固定する。
- **判定ソースの一意性**: C11 保護 hook (`guard-confirmed-chapter-overwrite.py`) は判定ソースとしてこの正本パスのみを読む。配下 rglob フォールバックは持たない。これにより同梱 fixture (`skills/run-system-spec-compile/fixtures/spec-state.json` など、別の確定セルを含むテストデータ) を判定ソースへ誤って拾う交差汚染が構造的に発生しない。
- **正本の書換防御**: 正本 `spec-state.json` への直接書換 (Write/Edit/Bash) は hook が遮断し、変更は単一 writer 経由 (根拠付き R4-reopen) のみ許す。別位置に存在する同名 `spec-state.json` (fixture 等) は正本でないため保護対象外 (遮断しない)。

## 形状

```json
{
  "schema_version": "1.0",
  "categories": [{"id": "database", "label": "データベース"}],
  "platforms": ["web", "mobile", "tablet", "desktop-windows", "desktop-linux", "desktop-macos"],
  "matrix": {
    "<category_id>": {
      "<platform_id>": {"state": "確定", "qa_ref": "qa-001", "serves_goals": ["G1"]},
      "<platform_id>": {"state": "対象外", "reason": "..."},
      "<platform_id>": {"state": "対象外", "approval_ref": "appr-001"},
      "<platform_id>": {"state": "未収集"}
    }
  },
  "qa_log": [{"id": "qa-001", "question": "...", "answer": "...", "provenance": "AskUserQuestion / 選択肢提示あり", "answered_at": "2026-09-04T21:20:00Z", "source": {"kind": "user-dialogue"}}],
  "approval_log": [{"id": "appr-001", "note": "..."}],
  "reopen_log": [{"category": "database", "platform": "web", "reason": "...", "from": "確定", "reopened_at": "2026-09-05T00:31:44Z", "discarded": {"qa_ref": "qa-001", "serves_goals": ["G1"]}}],
  "category_aggregate": {"<category_id>": "確定|収集中|未着手|対象外"},
  "targets": [{"target_id": "react"}],
  "requirements_foundation": {
    "essential_purpose": "", "background": "",
    "goals": [{"id": "G1", "text": "..."}],
    "objectives": [{"id": "O1", "text": "...", "measure": "..."}],
    "success_criteria": [], "stakeholders": [],
    "scope": {"in": [], "out": []}, "constraints": [],
    "concrete_intents": [{"id": "I1", "text": "...", "serves": ["G1"]}],
    "effective_source_refs": {},
    "confirmed": false
  },
  "decisions": [],
  "knowledge_candidates": [],
  "hearing_progress": {"loop_count": 0, "next_question": null, "complete": false, "max_loops": 5}
}
```

`schema_version` の既定は `"1.0"` で、`bootstrap` / `init` に `--schema-version 1.1` を明示した state だけが
`"schema_version": "1.1"` と `"design_application_contract_version": "1.0"` を併せ持つ。1.1 は確定セルの根拠 qa に
qa 単位の `design_applications` (後述「design_applications（回答原文と設計解釈の分離）」) を、確定 foundation に
`effective_source_refs` を課す opt-in の契約であり、1.1 から 1.0 へは戻せない。

`max_loops` は `chunk` 実行後だけ存在する任意 field で、直近 invocation に実際に指定された上限を保持する。`bootstrap` / `init` 直後には存在しない。

## canonical platform id (6・必須行)

`web` / `mobile` / `tablet` / `desktop-windows` / `desktop-linux` / `desktop-macos`。全カテゴリ行にこの6 platform が全存在する (対象外は理由付き)。別名 platform id を作らない。

## cell state (loop 中は3値)

| state | 付帯 | 意味 |
|---|---|---|
| `未収集` | なし、または `reopened_from` / `reopen_reason` | 未ヒアリング。最終時は0にする。付帯 field は `reopen` で確定から戻したセルだけに付く。 |
| `対象外` | `reason` か `approval_ref` (+ 任意 `qa_ref`) | 当該カテゴリ×platform は対象外 (理由必須)。 |
| `確定` | `qa_ref` (qa_log 参照) | 要件が確定。質疑ログ entry を参照。 |

`reopen` は確定セルを未収集へ置換する前に、存在する `qa_ref` / `qa_refs` / `serves_goals` / `serves_intents` / `approval_ref` を `reopen_log[].discarded` へ退避する。セルへは戻さないが、再確認中も以前の根拠・上位概念トレース・承認を追跡できる。

`対象外` の `reason` には**そのカテゴリ固有の帰結**を書く。除外の共通根拠 (例: 対象 platform は
web のみ) は `approval_log` の 1 箇所に置き、`approval_ref` で指す。byte 同一の理由文を複数
カテゴリへ複製すると `validate-coverage-matrix.py` が違反として検出する — 共通根拠の複製で
一律に埋めた状態は、検討済みと未検討が見分けられないため。

`対象外` セルにも任意で `qa_ref` を付けられる。除外は未検討ではなく**収集した結論**の一種で
あり、どの質疑で外したのかを機械で辿れるようにするための項目である。`apply_turn` は `confirm`
と同じく turn の `qa_id` を `exclude` op へ補完する。

`確定` セルの `qa_ref` は主たる接地根拠の 1 件で、セルの論点を別の問で補ったときの質疑は
`qa_refs` (裏付け) へ結ぶ。書込経路は `add-qa-ref` op
(`{"action": "add-qa-ref", "category": <id>, "platform": <id>, "qa_refs": [<qa_id>, ...]}`) だけである。
`確定` セルにだけ追記でき (確定前は拒否)、`qa_log` に無い id は拒否し、既にある id は重ねない
(冪等)。`state=確定` を変えないので確定巻き戻し防御に抵触せず、reopen→confirm と違って
`required_info` / `required_info_checks` を落とさない。turn に含めて `qa_refs` を省くと turn の `qa_id`
で補完される。ops は順に適用されるので、論点が揃った turn の ops に `confirm` → `add-qa-ref`
(開いた問の qa を含む先行 turn の qa_id。手順は `elicit-question-bank.md` の手順 4) と並べれば、確定と結び付けを 1 turn で行える。
結ばれない qa は、必須情報の接地 (下記の鎖) にも C03 の章の根拠にも数えられない。

## qa_log entry の項目

| 項目 | 必須 | 意味 |
|---|---|---|
| `id` | 必須 | 質疑 entry の識別子。確定セルの `qa_ref` / `qa_refs` の参照先。 |
| `question` | 必須 | 問いの逐語。登録後は書換不可。 |
| `answer` | 必須 | 回答の逐語。登録後は書換不可。 |
| `provenance` | 任意 | その回答の出所 (例: `AskUserQuestion / 選択肢提示あり`、`既存コードの読解`)。出所不明の回答が確定根拠になるのを防ぐ。 |
| `answered_at` | 任意 | 回答時刻 (RFC3339・未来不可)。実測値のみ。 |
| `required_info_items` | 任意 | この回答が満たす `required-info-catalog.json` の `item_id` 配列。追記のみ (和集合)。 |
| `basis` | 任意 | 回答の性質。`user-decision` / `observed-fact` / `agent-inference` のいずれか。 |
| `superseded_by` | 任意 | この entry を置き換えた新しい entry の `id`。`supersede-qa` op だけが書く (write-once)。 |
| `superseded_at` | 任意 | 置き換えを記録した時刻 (RFC3339・未来不可・置き換え先の `answered_at` 以後)。実測値のみ。 |
| `superseded_note` | 任意 | 旧い問のどの基準 (N1-N4) の違反を、同じ論点でどう問い直したか。C06 が置き換えの有効性を照合する材料。 |
| `source` | 任意 (foundation の根拠 qa は必須) | 回答の出所種別。`{"kind":"user-dialogue"}`、書面なら `{"kind":"written-requirements","path","section","sha256"}`、利用者の新規入力を伴わない `harness-remediation` (`trigger`) / `derived-consolidation` (`derived_from` と `approval_ref`) の 4 種。turn で渡すか `set-qa-source` で後付けする。 |
| `source_provenance` | 任意 | `set-qa-source` が後付けしたことの記録 (`metadata_backfill` / `type_repair`)。対話時に記録された `source` と監査が区別するため。 |
| `design_applications` | 任意 (schema 1.1 の確定根拠は必須) | この回答へ効いた設計原則の採否 (後述)。カテゴリ単位の `state.design_applications[category]` とは別物。 |
| `design_application_provenance` | 任意 | `set-qa-design-applications` による事後補完の記録 (`legacy_backfill`)。 |
| `knowledge_ref_corrections` | 任意 | `fix-qa-knowledge-ref` が実在しない `knowledge_ref` を差し替えた append-only 記録。 |

`basis` は「その確定が誰の判断か」を機械可読にする。`user-decision` は利用者が代替案を見た上で
明示選択したもの、`observed-fact` はコード・設定・公式ドキュメントで検証できる観測事実、
`agent-inference` はアシスタントの推定 (利用者確認も検証可能な出典も経ていない) を指す。
推定は仕様と矛盾しないため、これを宣言しない限りどの決定論ゲートにも掛からない。
`validate-coverage-matrix.py` は、確定セルの根拠が `agent-inference` だけの場合を既定で違反とし、
`--require-basis` を付けると確定セルごとに根拠 (`qa_ref` / `qa_refs`) の少なくとも 1 件に `basis` 宣言を要求する
(既存 state への一斉 backfill を強いないため opt-in)。

`required_info_items` は「必須情報が確定へ接地しているか」を決定論で検査するための機械可読な
紐付けである。`validate-knowledge-graph.py --profile required-info --state <spec-state.json>` が
**確定セル → `qa_ref`/`qa_refs` → qa entry → `required_info_items`** の鎖を辿り、
`missing_effect=block` の item が全て接地していることを検証する。qa entry に item_id を書いた
だけで、どの確定セルからも参照されていない回答は接地の証拠として数えない。

初回の確定前に入力 state 自身をこの検証へ渡すと、まだ確定セルが無いため循環する。
`confirm` を含む `apply` / `chunk` は `--required-info <required-info-catalog.json>` を付ける。
writer がメモリ上に作った候補 state に既存 `validate_required_info` を適用し、通過後だけ
`--state` (または `--out`) へ書く。失敗時は入力ファイルも出力ファイルも変更しない。
未確定の回答を蓄積するだけの turn / `reopen` はこの引数なしで行い、集めた回答を
セルへ結び付ける最初の `confirm` から候補検証を行う。`--out` で候補を別pathへ出す場合も
同じ検証を通し、正本へ直接 JSON をコピーしない。

`question` / `answer` の事後書換は writer が拒否する (記録の改竄防止)。訂正が要る場合は新しい
`id` を発行する。`provenance` / `answered_at` は**未設定のときに限り**後から追記でき、既に値が
ある項目の上書きは拒否される (追記は冪等)。C03 compile はこれらを章の「確定内容 (質疑録)」節へ
併記する。

### 置き換え (supersession)

問の設計に欠陥があった entry (中立な問の基準 N1-N4 の違反。正本は
`neutral-question-criteria.md`) は、`question` を凍結したままでは監査の検出が毎周再発する。
その entry は消さず、同じ論点を中立に問い直した新しい entry で**置き換えた**ことを記録する。
記録は旧 entry への `superseded_*` の追記だけで、旧 entry の本文・`corrections`・他の項目は変わらない。

- `superseded_*` は turn からは書けない (turn の未知キーは読み飛ばされ、書いたつもりで失われるため拒否する)。
- 置き換えが有効になるのは (a) 置き換え先が中立な問 (b) 同じ論点 (c) 利用者の回答が記録されている、を
  全て満たすときだけである。writer は (c) だけを決定論で検査し、(a)(b) は C06 が判定する。
  writer が通したことは置き換えの正当性を意味しない。
- C06 は置き換え済みの entry を誘導性の判定の対象から外し、有効な置き換えを「閉じた検出」として報告に残す。
- C03 compile は置き換え済みの entry を「旧版（置き換え先: <qa_id>）」の印付きで描く。

## 時刻項目の検証 (書式 + 単調性)

`recommendation.latest_checked_at` / `user_decision.confirmed_at` / `answered_at` は RFC3339 の
**書式**に加えて「未来でないこと」を writer が課す (時計ずれ許容 300 秒)。書式だけを見る検査は
「書式の正しい嘘」— まだ行っていない照合や採択を済んだものとして書いた値 — を素通りさせるため。
値は `python3 -c 'import datetime; print(datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))'` の実測値を使う。

## category_aggregate 真理値表 (4値・導出のみ)

| 行のセル集合 | 集約 |
|---|---|
| 全セル未収集 | 未着手 |
| 全セル対象外 | 対象外 |
| 未収集混在 (一部のみ未収集) | 収集中 |
| それ以外で未収集0 | 確定 |

`category_aggregate` は writer が真理値表から再計算する。手書き代入は契約違反。

## カテゴリ初期集合の正本

カテゴリの初期集合は C04 `../../ref-system-design-knowledge/references/system-category-taxonomy.json` を Read して得る (prompt へ直書き禁止)。ヒアリングでカテゴリの拡張発見・除外 (理由付き) ができる。

## targets (取得対象一覧) と set-targets op

`targets[]` は外部技術ドキュメントの取得対象一覧で、C02 (`run-system-spec-doc-fetch`) の取得対象と C13 (`validate-source-citation.py`) の全件突合、C03 (`compile-spec-doc.py`) の章割当に使う共有データである。

- **形状**: 各要素は `{"target_id": "<id>"[, "category": "<category_id>"][, "also_categories": ["<category_id>", ...]]}`。`target_id` 必須・重複禁止、`category` 任意 (指定時は該当章へ出典を割り当てる)。
- **also_categories** (任意): 1 つの技術の公式文書が複数の章の判断を支えるとき、主たる章 (`category`) に加えて出典を載せる章を宣言する。`category` を持つ target にだけ指定でき、非空文字列の非空配列で、要素の重複と `category` との一致は拒否する。C03 は主章と宣言した各章の出典表に同じ行を載せる。C02 の取得と C13 の全件突合は `target_id` 単位のままで、record は 1 件に束ねる (章ごとに複製しない)。
- **単一 writer**: `targets[]` も `scripts/apply-spec-transition.py` の `set-targets` op が唯一の書込経路。`init` は空配列で初期化するだけで、対象は `set-targets` で追加する。

```bash
# JSON 配列文字列 or ファイルパス ([...] / {"targets": [...]}) を受け付ける
python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/skills/run-system-spec-elicit/scripts/apply-spec-transition.py" set-targets --state spec-state.json \
  --targets '[{"target_id": "react", "category": "frontend"}, {"target_id": "postgres", "category": "database"}]'
```

- 取得対象が無いプロジェクトは `targets` を空のままにしてよい。その場合 C13 は「targets 空 かつ references 空 = 出典対象なし」で exit0 となり、コンパイル動線を詰まらせない。

## requirements_foundation (上位概念・要件 C9) と serves_goals / set-foundation op

`requirements_foundation` は、カテゴリ×platform の技術マトリクス収集の**手前**で確定する上位概念 (要件定義書の憲法)。ここがブレると、マトリクスをいくら網羅しても「本当にやりたいこと」から乖離する (spec drift) ため、最初に・しっかり抽出して固定し、各技術決定をここへ `serves_goals` でトレース (anchor) する。C01 の新責務 **R0-foundation** が `set-foundation` op で確定し、C03 (`compile-spec-doc.py`) が `00-requirements-definition.md` を先頭章として明示する。

- **要素 (U1-U9)**: `essential_purpose`(U1 本質的目的) / `background`(U2 背景) / `goals`(U3 ゴール `{id,text}`) / `objectives`(U4 目標 `{id,text,measure}`) / `success_criteria`(U5) / `stakeholders`(U6) / `scope`(U7 `{in,out}`) / `constraints`(U8) / `concrete_intents`(U9 `{id,text,serves:[goal_id]}`) / `confirmed`。
- **単一 writer**: `requirements_foundation` の書込は `set-foundation` op が唯一の経路。`init` は空 (`empty_foundation`) で初期化するだけ。goals は `id` 必須・重複禁止、`concrete_intents.serves` は実在 goal id を指す (dangling 拒否)。
- **確定条件**: `confirmed: true` を要求するときは U1-U9 の全項目が値を持つか、該当しない項目が `{"status":"not_applicable","reason":"..."}` で理由付き明示されていること。空のまま確認済みにできない。未確定なら途中保存として空でも保存できる。確定前に U1-U9 の根拠 QA (初回は canonical `qa-foundation-u1`〜`u9`) と承認を `chunk` の turn (`qa_id` / `approval_id`) で `qa_log` / `approval_log` へ記録しておく。`approval_ref` が `approval_log` に無い、または根拠 QA が欠けていれば `set-foundation` は確定を拒否する。
- **U ごとの根拠束縛 (`effective_source_refs`)**: schema 1.1 の確定 foundation は `effective_source_refs` に U1-U9 を過不足なく持ち、各 binding の `qa_ref` / `approval_ref` が一意に実在し、QA question が binding 対象の `U<N>` を明示し、QA が利用者一次入力 (`user-dialogue` または検証可能な `written-requirements`) で置き換え済み (`superseded_by`) でなく、現行 foundation の `approval_ref` と整合することを writer と `--require-foundation` が強制する。原則は U ごとの 1論点 QA だが、answer に U ごとに分離可能な利用者決定が逐語で残る **明示的な共有 binding** は許可し、qa_ref の一致だけを重複違反にしない。共有時の機械ゲートは `qa_ref` ごとの binding U 集合を正本とし、(1) question の **共有対象の全 U marker** と集合の exact match、(2) 各 binding の consumer 別 `evidence_quote` が answer に完全一致し `evidence_sha256 == sha256(evidence_quote UTF-8 bytes)`、(3) consumer 間の quote が同一または包含関係でない、(4) 各 binding の `approval_ref` が同一、を強制する。answer 全体の他 U 言及は binding 対象にはしない。対象 marker 欠落、question の対象外 marker、quote 欠落/改変/hash 不一致/流用は機械層で拒否する。ただし quote が対象 U の現行値を意味的に裏付けるか、AI 要約でなく逐語の利用者決定かは機械層の保証外であり、C06 が question / answer / approval / consumer 別 quote の生証跡を意味監査する。既定の schema 1.0 で `effective_source_refs` を省いた state だけは canonical `qa-foundation-u1`〜`qa-foundation-u9` を fallback に使える (schema 1.1 は `--schema-version 1.1` で選んだときだけ)。canonical entry は初回値の immutable な履歴であり、後続の確定値変更では新 QA/approval、対象 U の effective binding、トップレベル `approval_ref` を同時更新する。値だけを旧証拠へ付け替える操作 (writer が拒否する)、承認ログだけ・AI 要約だけ・AI が生成した entry 自身の digest を一次根拠にする操作は禁止する。
- **serves_goals (トレース)**: 各 `確定` セルは `serves_goals: ["G1", ...]` でどの上位概念 (ゴール) に資するかを明示する。`confirm` op に `serves_goals` を同時付与するか、確定後に `set-serves` op で additive に付与する。`set-serves` は `state=確定` を変えないため確定巻き戻し防御には抵触しない。
- **approval_ref (承認記録へのトレース)**: `対象外` セルは `exclude` op で `approval_ref` を持てるが、`確定` セルにはそれが無いと「回答本文は明示承認を根拠に引用しているのに、セルから承認記録へ機械追跡できない」状態が生じる。確定セル限定の後付け annotation である **`set-approval` op** で `approval_ref` を additive に付与する。`set-serves` と同型で `state=確定` を変えないため確定巻き戻し防御には抵触しない。writer は `approval_log` に実在する id だけを受理する (dangling 拒否)。`chunk` で同 turn に `approval_id` を持つ場合は省略でき、その turn の承認 id が自動で紐づく。

```bash
# 上位概念 U1-U9 を確定 (JSON 文字列 or ファイルパス)
python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/skills/run-system-spec-elicit/scripts/apply-spec-transition.py" set-foundation --state spec-state.json \
  --foundation '{"essential_purpose":"...","background":"...","goals":[{"id":"G1","text":"..."}],"confirmed":true}'
# 確定セルへ serves_goals を付与 (トレース)
python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/skills/run-system-spec-elicit/scripts/apply-spec-transition.py" apply --state spec-state.json \
  --op '{"action":"set-serves","category":"database","platform":"web","serves_goals":["G1"]}'
# 確定セルへ approval_ref を付与 (承認記録へのトレース)
python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/skills/run-system-spec-elicit/scripts/apply-spec-transition.py" apply --state spec-state.json \
  --op '{"action":"set-approval","category":"database","platform":"web","approval_ref":"appr-040"}'
```

### 書面要件の source-index

利用者が要件の書面 (例: `requirements-brief.md`) を渡したとき、内容を AI の回答として再表現して foundation を確定してはならない。初回は U1-U9 を canonical id ごとに 1論点ずつ索引化し、各 `effective_source_refs` をその QA/approval へ結ぶ。後続変更は別 id の entry を追記して binding を差し替える。writer は `source.kind`、書面なら安全な相対 path・非空 section・`answer` 原文と一致する SHA-256・質問中の path/section まで fail-closed で検証する。R6 監査は参照元書面と照合する。

```json
[
  {
    "qa_id": "qa-foundation-u1",
    "question": "書面入力 requirements-brief.md §1 の U1 (本質的目的) は何か",
    "answer": "利用者が渡した当該 section の原文",
    "source": {
      "kind": "written-requirements",
      "path": "requirements-brief.md",
      "section": "§1",
      "sha256": "<sha256(answer)>"
    },
    "ops": []
  }
]
```

この index は既存 `qa_log` の逐語を上書きせず、原文・入力位置・原文ハッシュを監査へ渡す。対話で得た U も同じ id を使い、`source:{"kind":"user-dialogue"}` を付ける。1つの entry に U1-U9 や複数の技術判断を束ねることは writer と `R6-audit-hearing` の誘導・遡及性監査で FAIL とする。

## R0→R1 bootstrap 契約

上位概念をマトリクスより先に確定できるよう、最初に state envelope を生成する。`init --state` は bootstrap 済みの `requirements_foundation` / `decisions` / `targets` / logs を保持して taxonomy の matrix だけを初期化する。

`init --state` は matrix 未着手の bootstrap state 専用である。確定セルを含む state を渡すと、reopen 記録なしで全セルを未収集へ戻してしまうため writer は fail-closed（不明・不整合なら安全側に停止）で拒否する。既存 taxonomy の拡張は `add-category`、確定セルの再確認は `reopen` を使う。

```bash
python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/skills/run-system-spec-elicit/scripts/apply-spec-transition.py" bootstrap --out spec-state.json
python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/skills/run-system-spec-elicit/scripts/apply-spec-transition.py" set-foundation --state spec-state.json --foundation foundation.json
python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/skills/run-system-spec-elicit/scripts/apply-spec-transition.py" init --taxonomy taxonomy.json --state spec-state.json --out spec-state.json
```

## decisions (意思決定支援) と set-decision op

ユーザーが決めきれない論点を、2-3件の無料/低コスト候補を含む比較、最新一次情報に基づくAI推奨、ユーザー確認へ分離して記録する。AI推奨だけで `confirmed` にしてはならない。

**何を `decisions[]` へ載せるか (登録基準)**。載せるのは **R5 が選択肢を組み立てた論点**、すなわち
公式一次情報に接地した 2-3 件の候補・コスト構造・5軸の比較を伴う技術選定に限る。利用者の
明示選択であっても、候補の組み立てを伴わない論点 (業務規則の確認、画面の置き場所、表示範囲の
決定など) は `decisions[]` に入らず、**`qa_log` entry の `basis: user-decision`** として記録する。
両者は根拠の重さが違うのではなく、**残すべき証跡の形が違う** — 前者は「なぜ他案を採らなかったか」
が後から検算できる必要があり、後者は「利用者が何と答えたか」の逐語が正本になる。
`options` / `comparison_basis` を持たない決定を体裁のために `decisions[]` へ入れると、比較して
いない軸を比較したかのように書くことになるため、writer はこれを必須項目の欠落として拒否する。
したがって `decisions[]` と `basis: user-decision` の件数が一致しないのは**設計上の非対称**であり、
接地の網羅は `decisions[]` の件数ではなく `required_info_items` の接地検査で担保する。

- `status`: `needs_guidance` / `recommended_pending_confirmation` / `confirmed`。
- `options`: 2-3件で、最低1件は `cost_model.category=free|low-cost`。各要素は `id` / `label` / `cost_model` / `free_tier_limits` / `goal_fit` / `security_fit` / `pros` / `cons` / `risks` / `lock_in` / `ops_burden` / `evidence_refs` を持つ。`evidence_refs` は公式 `https` URL の非空配列。
- `cost_model`: `category` (`free|low-cost|paid|unknown`) / `amount` (free=0、low-cost/paid=正数、unknownのみnull可) / `currency` / `billing_period` / `tco` を持つ。ライセンス料金だけでなく構築・運用・移行・撤退費を `tco` に明示する。
- `recommendation`: 推奨を提示した状態では `option_id` / `rationale` / `comparison_basis` / `caveats` / `confidence` / `latest_checked_at` が必須。`comparison_basis` は `goal_fit` / `tco` / `security` / `operations` / `lock_in` の全軸を持つ。`caveats` は非空配列、`latest_checked_at` は RFC3339、`option_id` は options 内を指す。
- `serves_goals`: 非空で実在する U3 goal id を指す。
- `user_decision`: `confirmed` のときだけ必須。`{"option_id":"...","confirmed_at":"<RFC3339>"[,"note":"..."]}`。AI推奨 (`recommended_pending_confirmation`) はユーザー確認ではない。`confirmed_at` は**選択が行われた実測時刻**を書く。実測できず記録の書込時刻しか手元に無い場合は、それが選択時刻そのものではなく**上限値**であることを `note` に明記する。RFC3339 検査は書式しか見ないため、書式の正しい推定値は全ゲートを素通りする。

```json
{
  "id": "D1",
  "question": "認証基盤をどれにするか",
  "status": "recommended_pending_confirmation",
  "options": [
    {
      "id":"managed-free", "label":"無料枠のあるmanaged認証",
      "cost_model":{"category":"free","amount":0,"currency":"JPY","billing_period":"month","tco":"無料枠内は月額0円、超過後は従量課金"},
      "free_tier_limits":"月間利用者上限あり", "goal_fit":"短期導入に適合",
      "security_fit":"managed更新とMFAで要件を満たす", "pros":["運用負荷が低い"],
      "cons":["上限超過時課金"], "risks":["価格改定"], "lock_in":"中", "ops_burden":"低",
      "evidence_refs":["https://vendor.example/pricing"]
    },
    {
      "id":"self-hosted", "label":"OSS self-hosted",
      "cost_model":{"category":"low-cost","amount":1000,"currency":"JPY","billing_period":"month","tco":"基盤費に保守工数を加算"},
      "free_tier_limits":"機能制限なし", "goal_fit":"内製運用できる場合に適合",
      "security_fit":"脆弱性更新を期限内に内製適用できる場合に適合", "pros":["移行自由度"],
      "cons":["保守が必要"], "risks":["脆弱性対応遅延"], "lock_in":"低", "ops_burden":"高",
      "evidence_refs":["https://project.example/docs"]
    }
  ],
  "recommendation": {
    "option_id":"managed-free", "rationale":"制約下で目的適合と総費用の均衡が最良",
    "comparison_basis":{"goal_fit":"短期導入に適合","tco":"無料枠内で最小","security":"managed更新を利用","operations":"保守負荷が低い","lock_in":"中程度を許容"},
    "caveats":["無料枠上限を監視"], "confidence":"medium", "latest_checked_at":"2026-07-11T00:00:00Z"
  },
  "serves_goals": ["G1"],
  "user_decision": null
}
```

```bash
python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/skills/run-system-spec-elicit/scripts/apply-spec-transition.py" set-decision --state spec-state.json --decision decision.json
```

## KNOWLEDGE_CANDIDATES_EXTENSION_C — seed 外 knowledge lifecycle

`knowledge_candidates[]` は、固定seedに無い知識をproject-localに発見し、C02の公式一次資料確認を経て深いカードへ育てる領域である。書込は `set-knowledge-candidate` のみが行う。

- 必須共通項目: stable kebab-case `id` / stable `topic` / `status` / `problem` / 実在goalを指す`serves_goals` / `source_refs`。
- 状態は `discovered → qualified → deepened → promoted` の一段階前進のみ。同じstatusでの追記は許すが、巻き戻し・飛び級・topic変更は禁止。
- `qualified` 以降: `source_refs[]` は `{url, official_or_primary:true, checked_at}` を持ち、URLはHTTPS。qualification担当はC02 (`run-system-spec-doc-fetch`)。
- `deepened` 以降: `card` がC04 deep-cardの必須意味項目 (`purpose/background/problems/core_concepts/applies_when/does_not_apply_when/tradeoffs/failure_modes/goal_contribution/primary_sources/freshness`) を全て持つ。
- `promoted`: 保守担当の承認・curated配置を指す `curation_ref` が必須。自動昇格しない。

```json
{
  "id": "offline-first-conflict-resolution",
  "topic": "offline-first conflict resolution",
  "status": "qualified",
  "problem": "複数端末のオフライン更新競合を解決する必要がある",
  "serves_goals": ["G1"],
  "source_refs": [
    {
      "url": "https://www.rfc-editor.org/rfc/rfc6902",
      "official_or_primary": true,
      "checked_at": "2026-07-11T00:00:00Z"
    }
  ]
}
```

```bash
python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/skills/run-system-spec-elicit/scripts/apply-spec-transition.py" set-knowledge-candidate \
  --state spec-state.json --candidate knowledge-candidate.json
```

## hearing_progress の意味論 (SSOT)

`hearing_progress` は goal-seek chunk の **中断/再開状態** を表す record。writer (`scripts/apply-spec-transition.py`) 以外は書かない。

> **不変則**: `complete` / `next_question` は state 全体の不変則である。matrix を書き換える全経路 (`init` / `add-category` / `apply` / `chunk`) は、終了時に未収集セル数から両 field を再同期する。writer 経由の state で「未収集セルが残るのに `complete=true`」は正常状態として発生しない。最終判定の正本は引き続き `validate-coverage-matrix.py --require-complete` とする。

| field | 型 | 意味 | 更新する経路 |
|---|---|---|---|
| `loop_count` | int | **直近 1 invocation (chunk) で適用した turn 数**。累計ではない。 | `chunk` / `bootstrap`・`init` |
| `max_loops` | int (任意) | 直近 `chunk` invocation に実際に指定された上限。監査は 5 をハードコードせず、この実値を使う。 | `chunk` |
| `next_question` | string \| null | 未収集が残ればカテゴリ順・platform 正順の次質問、未収集0なら `null`。 | matrix を書き換える全経路 |
| `complete` | bool | 未収集0なら `true`、1件以上なら `false`。 | matrix を書き換える全経路 |

- **累計ではない (loop_count)**: `run_chunk` はループ開始前に `loop_count = 0` を明示代入する。よって「通算で何 loop 回したか」は spec-state に保持しない。履歴の正本は `qa_log` / `reopen_log` の追記であり、`loop_count` を進捗率の分子に使わない (分母となる総 loop 数は事前に決まらない)。進捗は matrix の未収集セル数で測る。
- **全 matrix writer が再同期する**: `apply` で最後の未収集セルを埋めた場合も、`reopen` や `add-category` で未収集を増やした場合も、`complete` / `next_question` は同じ invocation の終了前に更新される。
- **早期停止監査**: 未収集が残るのに `complete=true` なら、writer 非経由の直接編集か state 破損として `FAIL` にする。loop 上限は `max_loops` があればその実値を使い、固定値 5 で判定しない。
- **`complete=true` かつ `loop_count=0` になる経路**: 未収集0の state に対して **適用 turn 数が 0 になる `chunk`** を実行した場合に限る。具体的には (a) `turns` が空配列、(b) `max_loops <= 0` (`--max-loops 0` および負値。argparse に下限検証がないため CLI から到達可能で、`processed >= max_loops` が初回反復で真になる) のいずれかで、`processed=0` のまま未収集0により `complete=true` が書かれる。`apply` だけではこの組合せに到達しない。
- **resume 契約**: `complete=false` かつ `next_question` 非 null が resumable な中断状態。この 2 field から再開する `--resume` は **skill/command の引数** (`commands/spec-hearing-start.md`) であって writer の CLI flag ではない (writer 側は state を読み直して `chunk` を継続するだけ)。`loop_count` は再開後の chunk で 0 から数え直す。

## qa_log の論点分離 (1 entry = 1 論点)

`qa_log` entry は監査 (C06) が「どの決定がどの往復に接地するか」を検証する単位であるため、**1 entry に 1 論点** を原則とする。

- 複数論点を 1 entry へ束ねると、後段で論点ごとの中立性・遡及性を分離検証できない。
- 既登録 entry の `question` / `answer` は **逐語のまま改変しない** (writer は問答本文の書換を拒否する)。束ねが後から判明した場合は、既存 entry を編集せず **分離索引を新規 entry として追記** し、そこから元 entry を参照する。
- **追記の実行経路と副作用**: qa_log 専用の op は存在しない。`apply_turn` は turn に `qa_id` があれば **`ops` の有無にかかわらず** entry を追記する (同 `id` が既存なら問答本文は変えず、未設定の provenance 項目だけを埋める)。したがって通常の `confirm` turn も qa_log を残す。一方 `apply --op` は turn に `qa_id` を載せられないため、**qa_log を追記できるのは `chunk --turns` 経路だけ**である。matrix を動かさずに索引だけ追記したいときは `{"qa_id": "...", "question": "...", "answer": "...", "ops": []}` (セル op 空) の turn を渡す。ただしこの経路も `loop_count` を 0 から数え直し `complete` / `next_question` を再計算する (`run_chunk` の副作用) ため、matrix を動かさない索引追記でも `hearing_progress` が書き換わる点を承知して使うこと。

### design_applications（回答原文と設計解釈の分離）

schema 1.1 の state では、セルを `confirm` する qa entry は、C04 deep card または doctrine anchor の具体原則が当該回答へどう効いたかを qa 単位の `design_applications[]` に記録する。これは利用者の発言を改変しないため `answer` へ混ぜず、compiler が章固有の適用根拠を描画するための設計解釈として分離する。カテゴリ単位の `state.design_applications[category]` (下記 `set-design-application`。章としての適用記述) とは粒度が違う別 field であり、どちらかで他方を代用しない。

- `knowledge_ref`: deep card path + section、または doctrine concern/authority を指す非空文字列。
- `principle`: 採否を判断した具体原則名。単なる「設計知識」「上記原則」は不可。
- `applicability`: `applied` / `not_applicable`。非適用も隠さず、理由を残す。
- `rationale`: 確定回答に即した章固有の採否理由。全章同一の定型文は禁止。
- `tradeoffs`: 採用費用、非採用時の損失、再評価条件などを最低1件持つ非空文字列配列。

writer は上記形状を検証して qa entry に保存する。schema 1.1 の state では `validate-coverage-matrix.py --require-complete` が確定セルから参照される全 qa entry の非空・形状と provenance の完全一致を fail-closed に再検査し、`validate-design-knowledge-refs.py --matrix spec-state.json --repo-root <project root>` が `knowledge_ref` の参照先の実在を検査する。既定の schema 1.0 state にはこの契約を課さない (既存 state を壊さないための opt-in 境界)。1.1 の state に一時的な `legacy_exempt: true` と非空 `legacy_exempt_reason` を持つ entry が残った場合に限り、`set-qa-design-applications` が既存の question / answer / source を維持したまま検証済み `design_applications` を追記し、`design_application_provenance={"mode":"legacy_backfill","writer":"set-qa-design-applications"}` を残して免除 metadata を除去する。provenance の無い既存解釈は対話経路として保護し、legacy 表示の後付けを拒否する。完了済み legacy backfill の同一 payload 再適用のみ冪等に受け入れ、異なる既存解釈または provenance の上書きは拒否する。C03 は `unrecorded` (解釈欠落) / `dialogue` (対話時解釈) / `legacy_backfill` (事後補完) の3経路を描画し、C05 は unrecorded を未記録 finding とし、backfill は対話時解釈と区別して回答との適合を再照合する。存在確認だけで `design_knowledge_reflection` を緑化させない。

## 単一 transition writer 契約

`scripts/apply-spec-transition.py` のみが matrix / logs / aggregate / hearing_progress / targets / requirements_foundation を書き換える。

- **確定巻き戻し拒否**: `確定` セルへの `confirm` / `exclude` は `TransitionError`。Bash/script 経由でも拒否。
- **R4-reopen 経由のみ確定変更**: `確定` を動かせるのは `reopen` (要 `reason` と `reopened_at`) だけ。`未収集` へ戻し `reopen_log` に根拠を残す。
  `reopened_at` は他の時刻と同じく**呼び出し側の実測値** (`python3 -c 'import datetime; print(datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))'`) を要求し、未来値は拒否する
  (writer が `now()` で埋めると書込時刻が実施時刻を騙るため)。reopen は確定を巻き戻せる唯一の経路であり、
  時刻が無いと「差し替え後の主根拠がこの reopen より後に取り直された回答か」を検査できず、
  先に確定を壊してから既存の回答を主根拠に流用した場合と、正当に取り直した場合が同じ見た目になる。
  時刻を欠く既存 entry の `reopened_at` は**遡って埋めない**。`reopen_log` entry の**既存フィールドを書き換える op は置かない** — reopen は確定を巻き戻せる唯一の経路であり、その記録自体を後から書き換えられる経路を作ると「確定を壊した事実」ごと消せてしまう。
- **`add-reopen-correction` (追記専用)**: 欠測時刻は `reopen_log[].corrections[]` (`{recovered_at, note, observed_reopened_at?}`) への**追記**で回復する。
  `qa_log` が `question`/`answer` を凍結したまま `corrections[]` への追記だけを許すのと同型で、既存キー (`category` / `platform` / `reason` / `from` / `reopened_at`) は不可侵。
  entry に id が無いため `index` で指すが、`match_category` / `match_platform` の照合を必須にして番号だけの指定は受け付けない (取り違えると別の reopen へ他人の時刻が付き、まさにこの記録が防ごうとしている汚染になる)。
  復元値は `reopened_at` へは書かず `observed_reopened_at` として補記側にのみ置く。両者は**意味が違う** — 前者は reopen 直前に測った実測値、後者は writer への適用が完了し state へ反映された時刻で、数十秒の範囲で上界寄りの近似である
  (精度は時刻を持つ entry で検算できる: `reopened_at=2026-09-05T02:03:58Z` に対し同手続きの返す反映時刻は `02:04:18Z`、差は約 20 秒)。
  この条項は 2 度の誤りを経て今の形になった。**誤った論拠も消さずに残す** — 正しい結論だけを置くと、なぜこの区別が要るのかが後から読めなくなるからである。
  1 回目「時刻が実測できないから埋めない」は端的に**偽**だった (reopen の適用はトランスクリプトに時刻付きで残っており、探せば読める)。
  2 回目「既存 entry を書き換える op を置かないため埋めない」は結論こそ維持すべきだが、**禁止対象を取り違えていた** — 守るべきは既存フィールドの改変であって、新しいフィールドの追記ではない。
  `append-only` の下では「訂正 (既存事実の修正)」と「補記 (新しい事実の追加)」は別物であり、後者は改竄経路にならない (独立ヒアリング監査 2026-09-05 の指摘)。
- **`supersede-qa` (追記専用)**: 凍結済みの qa entry を新しい entry で置き換えたことを記録する唯一の経路。
  op は `{"action": "supersede-qa", "qa_id": <旧>, "superseded_by": <新>, "superseded_at": <実測値>, "note": <非空>}`。
  turn に含めた場合、`superseded_by` を省くと turn の `qa_id` (いま問い直した entry) で補完する。
  拒否する条件: 旧・新 entry の不在、自分自身への置き換え、`note` の空、`superseded_at` の書式違反・未来値・置き換え先の
  `answered_at` より前、置き換え先の `answer` が空・`basis` が `user-decision` でない・`answered_at` が無いか旧 entry の
  `answered_at` より後でない (以上が (c))、置き換え先自身が置き換え済み (循環を原理的に作れない)、旧 entry が確定セルの
  主たる接地根拠 (`qa_ref`) のまま (先に R4-reopen し新しい entry で再確定する)、既に別の値で置き換え済み (write-once)。
  同値の再適用は冪等。裏付け (`qa_refs`) からの参照は残してよい。
- **置き換え済みの entry を主たる接地根拠にしない**: `confirm` の `qa_ref` が置き換え済みの entry なら拒否する。
  置き換えは「旧い問を確定の根拠から外した」ことの記録であり、後から同じ entry で確定し直せると、その記録が偽になる。
  確定は置き換え先の entry で行う。
- **goal-seek chunk**: `chunk` は 1 invocation で最大 `max_loops` (既定 5) turn を適用し、その実値を `hearing_progress.max_loops` に保存する。未収集が残れば `complete=false`・`next_question` 非 null、未収集0なら `complete=true` とする。後続の `reopen` / `add-category` / `apply` も同じ不変則へ再同期する。投入 turn が `max_loops` を超えた場合、超過分は適用されないが黙って捨ててはならない。writer は未消化件数を必ず stderr へ出し、`--require-all` 指定時は `TransitionError` で停止して部分適用を書き戻さない。`hearing_progress.complete` は未収集セル0を意味するだけで turn 消化の証跡にはならないため、この可視化が無いと「投入した turn の一部だけが適用された state」を完了扱いできてしまう。
- **set-targets**: `targets[]` の唯一の書込経路 (上記「targets と set-targets op」)。
- **set-foundation / set-serves / set-approval / set-decision / set-knowledge-candidate / set-qa-design-applications / set-qa-source / fix-qa-knowledge-ref**: `requirements_foundation` と effective binding、確定セルの `serves_goals` / `approval_ref`、`decisions[]`、`knowledge_candidates[]`、既存 qa の metadata の唯一の書込経路。どれも既存 qa の `question` / `answer` を改変しない。現行証拠から外す経路は上記 `supersede-qa` だけである。
- **set-qa-source**: `source` を持たない既存 qa へ、質問・回答を改変せず出所だけを追記する。`kind` は利用者の一次入力を表す `user-dialogue` / `written-requirements` と、利用者の新規入力を伴わない `harness-remediation` / `derived-consolidation` の 4 種。後者 2 種を `user-dialogue` と索引すると、C06 中立性監査と foundation trace が「利用者が答えた」という前提のまま偽の一次根拠を数えるため、由来を必須フィールドで持たせて区別する。`harness-remediation` はレビュー・監査の指摘に由来する是正で、どの指摘かを示す非空 `trigger` を要求する。`derived-consolidation` は既存 qa の統合・復旧で新しい情報を増やさないため、非空の `derived_from` (qa id 配列) と `approval_ref` の両方を要求する。書面は安全な相対 `path`・非空 `section`・`answer` 原文 (UTF-8 bytes) と一致する `sha256` を fail-closed に検証する。後付けであることは隠さず `source_provenance={"mode":"metadata_backfill","writer":"set-qa-source"}` を残し、対話時にその場で記録された source と監査が区別できるようにする。既存 source の差し替えは常に拒否し、補完済み source への同一 payload 再適用のみ冪等に受け入れる。この経路が無いと出所補完のために reopen → 再確認で回答ごと作り直すことになり、かえって利用者の一次根拠を失う。ただし `source` が object でない値 (契約違反の素の文字列) は「対話経路で記録済みの source」ではなく壊れた値なので保護対象に含めず、注記本文を `source_note` へ退避したうえで契約形状へ修復し `source_provenance={"mode":"type_repair","writer":"set-qa-source"}` を残す。注記を捨てると「なぜこの qa が存在するか」の唯一の手掛かりを失うため、必ず保存する。
- **fix-qa-knowledge-ref**: 既存 qa の `design_applications[].knowledge_ref` のうち、参照先が実在しないものだけを実在する参照へ差し替える。`set-qa-design-applications` は design_applications を丸ごと一単位として保護するため、対話経路 (provenance なし) の entry では綴り違いすら訂正できず、根拠を持たない引用が恒久的に残る。契約の保護意図は「対話で得た解釈内容を後から書き換えないこと」なので、`principle` / `applicability` / `rationale` / `tradeoffs` に一切触れず、**旧 ref の path が実在しない**場合に限って差し替える。実在する参照の付け替えは「どの知識で判断したか」の書き換えにあたるため常に拒否する。新 ref は path と (指定時は) anchor 見出しの実在を要求し、差し替えは `knowledge_ref_corrections[]` へ append-only で記録して、対話時の引用と後からの接地し直しを監査が区別できるようにする。同一訂正の再適用は冪等に no-op とする。
- **set-design-application / set-doctrine-application**: 章 (カテゴリ) 固有の「その設計知識・上流指針を本章の確定内容へどう適用したか」の唯一の書込経路。前者は `design_applications[category] = {text, recorded_at, basis?}` (deep knowledge card 単位)、後者は `doctrine_applications[category][concern_id] = {text, recorded_at, basis?}` (doctrine concern 単位)。
  どちらも存在理由は同じで、**compile が機械注入した参照を、自分で「適用した」証拠として数える自己循環を断つ**ためにある。card 本文も doctrine registry の転記表も共有資産なので、同じものを引く章どうしが一致するのは当然であり、一致する記述は適用の証拠になり得ない。章固有性を担えるのはここに書かれた記述だけで、未記入なら compile は空欄で濁さず「未記入」と本文に出す。
  `set-doctrine-application` は加えて、**同じ concern を引く他章と正規化後に一致する `text` を拒否する**。registry では 7 concern がいずれも 2 つ以上のカテゴリから参照される (`presentation` → ui-ux / frontend、`data-access` → database / backend、`operations` → infrastructure / maintenance-ops 等) ため、章が違えば確定セルも違うにもかかわらず記述が一致することは、上流の要約を写しただけの指紋になる。
  正規化は空白と句読点・記号の除去に留める — 素の完全一致では句読点 1 つで抜けられ、言い換えの検出まで踏み込むと正当な記述を弾いて「回避のためだけの言い換え」を書き手に強いる (Goodhart を別の口から入れることになる)。表層記号だけなら内容の異なる 2 記述が一致することはなく、偽陽性が原理的に出ない。
  記述には**上流指針に従わなかったことも書ける**。従っていない章に authority の名だけ掲げるほうが、従っていないと書くより有害だからである (例: 単独利用のため SLO を定義していない、目的適合を理由に小画面での列削減を採らなかった)。

## 検証 (deterministic gate)

- loop 中: `python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/validate-coverage-matrix.py" --matrix spec-state.json` (exit0)。
- 最終: 同コマンド `--require-complete` (未収集0 必須, exit0)。上位概念 anchor まで要求する場合は `--require-foundation` を併用する (schema 1.1 は `effective_source_refs`、exact 1.0 は canonical `qa-foundation-u1`〜`u9` を検査)。
- schema 1.1 の state: `python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/validate-design-knowledge-refs.py" --matrix spec-state.json --repo-root "$CLAUDE_PROJECT_DIR"` (exit0) で qa 単位 `design_applications[].knowledge_ref` の参照先実在を検査する。
