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
  "qa_log": [{"id": "qa-001", "question": "...", "answer": "...", "provenance": "AskUserQuestion / 選択肢提示あり", "answered_at": "2026-09-04T21:20:00Z"}],
  "approval_log": [{"id": "appr-001", "note": "..."}],
  "reopen_log": [{"category": "database", "platform": "web", "reason": "...", "from": "確定", "reopened_at": "2026-09-05T00:31:44Z"}],
  "category_aggregate": {"<category_id>": "確定|収集中|未着手|対象外"},
  "targets": [{"target_id": "react"}],
  "requirements_foundation": {
    "essential_purpose": "", "background": "",
    "goals": [{"id": "G1", "text": "..."}],
    "objectives": [{"id": "O1", "text": "...", "measure": "..."}],
    "success_criteria": [], "stakeholders": [],
    "scope": {"in": [], "out": []}, "constraints": [],
    "concrete_intents": [{"id": "I1", "text": "...", "serves": ["G1"]}],
    "confirmed": false
  },
  "decisions": [],
  "knowledge_candidates": [],
  "hearing_progress": {"loop_count": 0, "next_question": null, "complete": false}
}
```

## canonical platform id (6・必須行)

`web` / `mobile` / `tablet` / `desktop-windows` / `desktop-linux` / `desktop-macos`。全カテゴリ行にこの6 platform が全存在する (対象外は理由付き)。別名 platform id を作らない。

## cell state (loop 中は3値)

| state | 付帯 | 意味 |
|---|---|---|
| `未収集` | なし | 未ヒアリング。最終時は0にする。 |
| `対象外` | `reason` か `approval_ref` (+ 任意 `qa_ref`) | 当該カテゴリ×platform は対象外 (理由必須)。 |
| `確定` | `qa_ref` (qa_log 参照) | 要件が確定。質疑ログ entry を参照。 |

`対象外` の `reason` には**そのカテゴリ固有の帰結**を書く。除外の共通根拠 (例: 対象 platform は
web のみ) は `approval_log` の 1 箇所に置き、`approval_ref` で指す。byte 同一の理由文を複数
カテゴリへ複製すると `validate-coverage-matrix.py` が違反として検出する — 共通根拠の複製で
一律に埋めた状態は、検討済みと未検討が見分けられないため。

`対象外` セルにも任意で `qa_ref` を付けられる。除外は未検討ではなく**収集した結論**の一種で
あり、どの質疑で外したのかを機械で辿れるようにするための項目である。`apply_turn` は `confirm`
と同じく turn の `qa_id` を `exclude` op へ補完する。

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

`basis` は「その確定が誰の判断か」を機械可読にする。`user-decision` は利用者が代替案を見た上で
明示選択したもの、`observed-fact` はコード・設定・公式ドキュメントで検証できる観測事実、
`agent-inference` はアシスタントの推定 (利用者確認も検証可能な出典も経ていない) を指す。
推定は仕様と矛盾しないため、これを宣言しない限りどの決定論ゲートにも掛からない。
`validate-coverage-matrix.py` は、確定セルの根拠が `agent-inference` だけの場合を既定で違反とし、
`--require-basis` を付けると確定セルの根拠に `basis` 宣言そのものを要求する
(既存 state への一斉 backfill を強いないため opt-in)。

`required_info_items` は「必須情報が確定へ接地しているか」を決定論で検査するための機械可読な
紐付けである。`validate-knowledge-graph.py --profile required-info --state <spec-state.json>` が
**確定セル → `qa_ref`/`qa_refs` → qa entry → `required_info_items`** の鎖を辿り、
`missing_effect=block` の item が全て接地していることを検証する。qa entry に item_id を書いた
だけで、どの確定セルからも参照されていない回答は接地の証拠として数えない。

`question` / `answer` の事後書換は writer が拒否する (記録の改竄防止)。訂正が要る場合は新しい
`id` を発行する。`provenance` / `answered_at` は**未設定のときに限り**後から追記でき、既に値が
ある項目の上書きは拒否される (追記は冪等)。C03 compile はこれらを章の「確定内容 (質疑録)」節へ
併記する。

## 時刻項目の検証 (書式 + 単調性)

`recommendation.latest_checked_at` / `user_decision.confirmed_at` / `answered_at` は RFC3339 の
**書式**に加えて「未来でないこと」を writer が課す (時計ずれ許容 300 秒)。書式だけを見る検査は
「書式の正しい嘘」— まだ行っていない照合や採択を済んだものとして書いた値 — を素通りさせるため。
値は `date -u +%Y-%m-%dT%H:%M:%SZ` の実測値を使う。

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

- **形状**: 各要素は `{"target_id": "<id>"[, "category": "<category_id>"]}`。`target_id` 必須・重複禁止、`category` 任意 (指定時は該当章へ出典を割り当てる)。
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
- **確定条件**: `confirmed: true` を要求するときは U1-U9 の全項目が値を持つか、該当しない項目が `{"status":"not_applicable","reason":"..."}` で理由付き明示されていること。空のまま確認済みにできない。未確定なら途中保存として空でも保存できる。
- **serves_goals (トレース)**: 各 `確定` セルは `serves_goals: ["G1", ...]` でどの上位概念 (ゴール) に資するかを明示する。`confirm` op に `serves_goals` を同時付与するか、確定後に `set-serves` op で additive に付与する。`set-serves` は `state=確定` を変えないため確定巻き戻し防御には抵触しない。

```bash
# 上位概念 U1-U9 を確定 (JSON 文字列 or ファイルパス)
python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/skills/run-system-spec-elicit/scripts/apply-spec-transition.py" set-foundation --state spec-state.json \
  --foundation '{"essential_purpose":"...","background":"...","goals":[{"id":"G1","text":"..."}],"confirmed":true}'
# 確定セルへ serves_goals を付与 (トレース)
python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/skills/run-system-spec-elicit/scripts/apply-spec-transition.py" apply --state spec-state.json \
  --op '{"action":"set-serves","category":"database","platform":"web","serves_goals":["G1"]}'
```

## R0→R1 bootstrap 契約

上位概念をマトリクスより先に確定できるよう、最初に state envelope を生成する。`init --state` は bootstrap 済みの `requirements_foundation` / `decisions` / `targets` / logs を保持して taxonomy の matrix だけを初期化する。

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

## 単一 transition writer 契約

`scripts/apply-spec-transition.py` のみが matrix / logs / aggregate / hearing_progress / targets / requirements_foundation を書き換える。

- **確定巻き戻し拒否**: `確定` セルへの `confirm` / `exclude` は `TransitionError`。Bash/script 経由でも拒否。
- **R4-reopen 経由のみ確定変更**: `確定` を動かせるのは `reopen` (要 `reason` と `reopened_at`) だけ。`未収集` へ戻し `reopen_log` に根拠を残す。
  `reopened_at` は他の時刻と同じく**呼び出し側の実測値** (`date -u +%Y-%m-%dT%H:%M:%SZ`) を要求し、未来値は拒否する
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
- **goal-seek chunk**: `chunk` は 1 invocation で最大 `max_loops` (5) turn を適用。未収集が残れば `hearing_progress.complete=false`・`next_question` 非 null を保存 (resumable)。未収集0のときだけ `complete=true`。
- **set-targets**: `targets[]` の唯一の書込経路 (上記「targets と set-targets op」)。
- **set-foundation / set-serves / set-decision / set-knowledge-candidate**: `requirements_foundation`、確定セルの `serves_goals`、`decisions[]`、`knowledge_candidates[]` の唯一の書込経路。
- **set-design-application / set-doctrine-application**: 章 (カテゴリ) 固有の「その設計知識・上流指針を本章の確定内容へどう適用したか」の唯一の書込経路。前者は `design_applications[category] = {text, recorded_at, basis?}` (deep knowledge card 単位)、後者は `doctrine_applications[category][concern_id] = {text, recorded_at, basis?}` (doctrine concern 単位)。
  どちらも存在理由は同じで、**compile が機械注入した参照を、自分で「適用した」証拠として数える自己循環を断つ**ためにある。card 本文も doctrine registry の転記表も共有資産なので、同じものを引く章どうしが一致するのは当然であり、一致する記述は適用の証拠になり得ない。章固有性を担えるのはここに書かれた記述だけで、未記入なら compile は空欄で濁さず「未記入」と本文に出す。
  `set-doctrine-application` は加えて、**同じ concern を引く他章と正規化後に一致する `text` を拒否する**。registry では 7 concern がいずれも 2 つ以上のカテゴリから参照される (`presentation` → ui-ux / frontend、`data-access` → database / backend、`operations` → infrastructure / maintenance-ops 等) ため、章が違えば確定セルも違うにもかかわらず記述が一致することは、上流の要約を写しただけの指紋になる。
  正規化は空白と句読点・記号の除去に留める — 素の完全一致では句読点 1 つで抜けられ、言い換えの検出まで踏み込むと正当な記述を弾いて「回避のためだけの言い換え」を書き手に強いる (Goodhart を別の口から入れることになる)。表層記号だけなら内容の異なる 2 記述が一致することはなく、偽陽性が原理的に出ない。
  記述には**上流指針に従わなかったことも書ける**。従っていない章に authority の名だけ掲げるほうが、従っていないと書くより有害だからである (例: 単独利用のため SLO を定義していない、目的適合を理由に小画面での列削減を採らなかった)。

## 検証 (deterministic gate)

- loop 中: `python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/validate-coverage-matrix.py" --matrix spec-state.json` (exit0)。
- 最終: 同コマンド `--require-complete` (未収集0 必須, exit0)。
