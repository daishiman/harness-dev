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
  "qa_log": [{"id": "qa-001", "question": "...", "answer": "..."}],
  "approval_log": [{"id": "appr-001", "note": "..."}],
  "reopen_log": [{"category": "database", "platform": "web", "reason": "...", "from": "確定"}],
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
| `対象外` | `reason` か `approval_ref` | 当該カテゴリ×platform は対象外 (理由必須)。 |
| `確定` | `qa_ref` (qa_log 参照) | 要件が確定。質疑ログ entry を参照。 |

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
python3 scripts/apply-spec-transition.py set-targets --state spec-state.json \
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
python3 scripts/apply-spec-transition.py set-foundation --state spec-state.json \
  --foundation '{"essential_purpose":"...","background":"...","goals":[{"id":"G1","text":"..."}],"confirmed":true}'
# 確定セルへ serves_goals を付与 (トレース)
python3 scripts/apply-spec-transition.py apply --state spec-state.json \
  --op '{"action":"set-serves","category":"database","platform":"web","serves_goals":["G1"]}'
```

## R0→R1 bootstrap 契約

上位概念をマトリクスより先に確定できるよう、最初に state envelope を生成する。`init --state` は bootstrap 済みの `requirements_foundation` / `decisions` / `targets` / logs を保持して taxonomy の matrix だけを初期化する。

```bash
python3 scripts/apply-spec-transition.py bootstrap --out spec-state.json
python3 scripts/apply-spec-transition.py set-foundation --state spec-state.json --foundation foundation.json
python3 scripts/apply-spec-transition.py init --taxonomy taxonomy.json --state spec-state.json --out spec-state.json
```

## decisions (意思決定支援) と set-decision op

ユーザーが決めきれない論点を、2-3件の無料/低コスト候補を含む比較、最新一次情報に基づくAI推奨、ユーザー確認へ分離して記録する。AI推奨だけで `confirmed` にしてはならない。

- `status`: `needs_guidance` / `recommended_pending_confirmation` / `confirmed`。
- `options`: 2-3件で、最低1件は `cost_model.category=free|low-cost`。各要素は `id` / `label` / `cost_model` / `free_tier_limits` / `goal_fit` / `security_fit` / `pros` / `cons` / `risks` / `lock_in` / `ops_burden` / `evidence_refs` を持つ。`evidence_refs` は公式 `https` URL の非空配列。
- `cost_model`: `category` (`free|low-cost|paid|unknown`) / `amount` (free=0、low-cost/paid=正数、unknownのみnull可) / `currency` / `billing_period` / `tco` を持つ。ライセンス料金だけでなく構築・運用・移行・撤退費を `tco` に明示する。
- `recommendation`: 推奨を提示した状態では `option_id` / `rationale` / `comparison_basis` / `caveats` / `confidence` / `latest_checked_at` が必須。`comparison_basis` は `goal_fit` / `tco` / `security` / `operations` / `lock_in` の全軸を持つ。`caveats` は非空配列、`latest_checked_at` は RFC3339、`option_id` は options 内を指す。
- `serves_goals`: 非空で実在する U3 goal id を指す。
- `user_decision`: `confirmed` のときだけ必須。`{"option_id":"...","confirmed_at":"<RFC3339>"[,"note":"..."]}`。AI推奨 (`recommended_pending_confirmation`) はユーザー確認ではない。

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
python3 scripts/apply-spec-transition.py set-decision --state spec-state.json --decision decision.json
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
python3 scripts/apply-spec-transition.py set-knowledge-candidate \
  --state spec-state.json --candidate knowledge-candidate.json
```

## 単一 transition writer 契約

`scripts/apply-spec-transition.py` のみが matrix / logs / aggregate / hearing_progress / targets / requirements_foundation を書き換える。

- **確定巻き戻し拒否**: `確定` セルへの `confirm` / `exclude` は `TransitionError`。Bash/script 経由でも拒否。
- **R4-reopen 経由のみ確定変更**: `確定` を動かせるのは `reopen` (要 reason) だけ。`未収集` へ戻し `reopen_log` に根拠を残す。
- **goal-seek chunk**: `chunk` は 1 invocation で最大 `max_loops` (5) turn を適用。未収集が残れば `hearing_progress.complete=false`・`next_question` 非 null を保存 (resumable)。未収集0のときだけ `complete=true`。
- **set-targets**: `targets[]` の唯一の書込経路 (上記「targets と set-targets op」)。
- **set-foundation / set-serves / set-decision / set-knowledge-candidate**: `requirements_foundation`、確定セルの `serves_goals`、`decisions[]`、`knowledge_candidates[]` の唯一の書込経路。

## 検証 (deterministic gate)

- loop 中: `python3 $CLAUDE_PLUGIN_ROOT/scripts/validate-coverage-matrix.py --matrix spec-state.json` (exit0)。
- 最終: 同コマンド `--require-complete` (未収集0 必須, exit0)。
