# 内容 adequacy 検査プロトコル (Step 12 content-review)

機械 lint だけでは「ひな形通り」だけ確認で内容空虚を素通りさせる欠陥がある。
本プロトコルは **verification obligation resolver → 必要時だけLLM評価 → verdict互換投影 → 機械検査** で「内容の良さ」を build harness に組み込む。正準の選定・再利用契約は `verification-obligation-protocol.md` であり、本書はcontent-review verdictの互換投影と、それを強制するCI / pre-pushの機械検査を定める。

**位置づけ (証拠の主張型直交)**: 静的レビュー (content-review / elegant-review / rubric) は **design claim (設計 adequacy) の正本**であり、静的設計ゲートの核 (実行 acceptance は Gate D)。behavioral claim (実行挙動: 自走完遂 / 入れ子 Skill / 対話 gate 越え / goal 達成) の受け入れ収束は **Gate D (`run-skill-live-trial`) の実走証拠のみ**を根拠とし、静的 verdict を流用しない (評価縮退の禁止)。ゲート帰属の正本は `$PLUGIN_ROOT/references/orchestrate-gate-pattern.md`。

**重要**: `SKILL.md SHAが変わったらreviewを1回起動` はlegacy admissionであり正準cost modelではない。正準はclaim、入力slice、checker契約、上流claim fingerprintに束縛したreceiptである。SHA verdictはCI互換projectionとして残すが、review起動判断は `plan-verification-obligations.py` の `llm_batches[]` だけに従う。

## 役割境界 (機械 vs LLM)

| 層 | 検査対象 | 実行場所 | 実装 |
|----|---------|---------|------|
| 機械層 | ファイル構造 / frontmatter / 命名 / 行数 / symlink drift / **verdict json の存在と PASS** | CI + pre-push | lint 群 + `lint-content-review.py` |
| LLM 層 | machine proof後にも未解決の **semantic obligation** (意図反映 / 4条件 / rubric 規範) | **ローカル Claude Code / Codex** | incremental=`llm_batches[]` ごとに1 context、exhaustiveのみadversarial audit |

リモート CI で LLM を起動しない (API 課金・所要時間回避)。ローカルで評価して json を commit し、CI は存在のみ機械検査する。

## build 完了直後の profile 制御 (incremental default)

profile は `incremental|exhaustive|build-only` の閉列挙で、無指定は `incremental`。`incremental` はgraph-level contractを解決し、current fingerprintに束縛されたPASS receiptを再利用する。入力または上流proofが変わったsemantic obligationだけを実context byte量でbatch化し、builderと別の evaluatorへ渡す。結果は既存の `elegance-verdict.json` / `rubric-verdict.json` に分離投影し、両ファイルを同obligation receiptのevidenceとして記録する。未達・矛盾・低confidenceはAgentを増やさず `escalate` で停止する。

`exhaustive` を利用者が明示した場合だけ、下記の elegance 30思考法と rubric 評価を独立実行し最大3周する。`build-only` は LLM を起動せず trace へ `not-run(profile=build-only)` を残す (PASS証跡の偽装禁止)。

### ループ分類

| ループ | 目的 | 評価基準 | 上限 | 発火 |
|----|----|----|----|----|
| Inner loop | 小さな機能・責務単位で現在ゴールを満たす | `feedback_contract.criteria[loop_scope=inner]` + goal-seek checklist | 再評価=`inner_loop.max_iterations` (既定3) / goal-seek 手順反復=`loop_bounds.goal_seek_inner` (5) ※別ループ | build 中 / evaluator findings |
| Outer loop | ハーネス全体がユーザー目的に近づいているかを改善する | 未解決semantic obligation + 4条件 | incremental=同じobligationの修正→再評価1回、exhaustiveのみ最大3 | obligation resolver / CI・pre-push の `lint-content-review.py` |

> **"inner" 命名の自己説明** (JSON キー名は数値 SSOT に直結するため変更しない): 同じ "inner" 語が 2 つの別ループを指す。`inner`(=goal-seek の**手順反復**。AI が手順を都度導出する内ループ, 上限5) と `inner_loop`(=content-review の**再評価**反復, 上限3) は別物。前者は「手順」を、後者は「評価」を反復する。

負のフィードバックは findings を減らす方向（C1-C4違反、high severity、rubric低スコア）で該当obligationだけ改善→再評価へ戻す。incrementalは1回で収束しなければ `escalate`、明示exhaustiveだけ最大3周とする。正のフィードバックは良い設計判断・再利用可能パターンを抽出し、outer loop で `run-elegant-review/references/amplified-patterns.json` または対象 skill の references へ横展開候補として残す。どちらも無限周回は禁止し、上限到達時は `INCOMPLETE` + `human_review_required=true` で停止する。

> **exhaustive有界反復の数値正本 = `run-elegant-review/references/convergence-policy.json` の `loop_bounds`**。有界反復は3つの別ループに分かれる: ① goal-seek 手順反復 `inner_max_loops=5`、② exhaustive content-review の評価→改善 ceiling `inner_loop.max_iterations=3`、③ exhaustive Outer 再評価 `max_iterations=3`。incrementalはこのceilingを使わず1再評価で `escalate` する。**①(5) と ②(3) は別ループの上限であり矛盾ではない**。
>
> **互換入口ゲート（admission_control）**: `skill_md_sha256` 一致はlegacy verdict projectionの高速pre-filterとして維持するが、proof再利用の十分条件ではない。正準resolverはobligation fingerprintとreceipt evidence SHAを照合する。`--force-review` は互換pre-filterを上書きするだけで、正準の依存proof検査を迂回しない。

### 完了チェックリスト と feedback_contract.criteria の使い分け（同源・別用途）

初見時に「どちらに何を書くか」で詰まりやすい。両者は **同じ `brief.goal` から導出される同源**だが、用途と置き場所が異なる。

| 観点 | 完了チェックリスト | feedback_contract.criteria |
|----|----|----|
| 役割 | 二値の達成判定 / 実行停止条件（goal-seek ループを「もう回さない」判断） | 評価観点 + `verify_by` 写像（誰が・どう検証するか） |
| 形式 | `- [ ]` の自然文チェック項目 | `{id, loop_scope, text, verify_by}` の構造化 criterion |
| 置き場所 | SKILL.md 本文 `## ゴールシーク実行` の Checklist | SKILL.md frontmatter `feedback_contract.criteria`（量産先が携帯する正本）+ build-trace |
| 検証主体 | 実行中の AI 自身（自己評価ループ） | inner=lint/script、outer=content-review/elegant-review |
| 導出方向 | `brief.goal` → Checklist（**先に書く**） | 各停止条件を `verify_by` 付き criterion へ**写像して導出**（**後に書く**） |

**導出方向は Checklist が上流・criteria が下流**。run-build-skill は Step 1 で goal/Checklist を確定し、Step 3.5 で各 Checklist 停止条件を「何で検証するか(`verify_by`)」へ写像して frontmatter + trace に固定する。criteria を先に書いて Checklist を後付けしてはならない（停止条件が検証手段に引きずられ空洞化するため）。

### incremental: unresolved semantic batch (必要なcontextだけ)

`plan-verification-obligations.py` の各 `llm_batches[]` について、列挙された `obligation_ids` と `context_paths` だけを `assign-skill-design-evaluator` へ渡す。対象外skill、全repository、全route reportは読ませない。30思考法を使用したと申告してはならない。

1 context が読み、合否は次元ごとに別の verdict へ書き分ける。1 つの verdict に複数次元の合否を混ぜない (`$PLUGIN_ROOT/references/orchestrate-gate-pattern.md` のアンチパターン)。

| verdict | 合否を決めるもの | 中身 |
|----|----|----|
| `elegance-verdict.json` | LLM | C1 矛盾なし / C2 漏れなし / C3 整合性 / C4 依存関係整合。C3 のうち rubric rule で採点できる規約整合 (命名・frontmatter・行数・節の有無など) は rubric verdict の結果を参照し、同じ指摘を elegance 側に重ねて書かない |
| `rubric-verdict.json` | `render-findings-score.py` | 機械採点の `findings[]`・score・threshold。LLM が渡すのは、機械で採点できない rule (`pending_human` と、判定の実装が無い high rule。例: BD-004) の判定だけ |

rubric verdict は手で書かず、判定ファイルを渡して script に書かせる。

```bash
python3 plugins/harness-creator/skills/assign-skill-design-evaluator/scripts/render-findings-score.py \
  --rubric-refs <L0> [<L1> ...] <L2> --target plugins/<plugin>/skills/<skill> \
  --write-rubric-verdict eval-log/<plugin>/<skill>/content-review/rubric-verdict.json \
  --judgments "$SCRATCH/judgments.json"
```

```json
{"reviewer": "assign-skill-design-evaluator",
 "judgments": {"BD-004": {"verdict": "PASS", "reason": "trigger 2 つが手順 1・2 に対応する"}},
 "positive_feedback": ["契約の節が先頭にある"]}
```

`criteria_evaluated` を省けば frontmatter の `feedback_contract.criteria[].id` が入る。判定の欠け、機械で採点した rule への判定 (機械の結果は上書きできない)、変更した本人の reviewer、frontmatter の criteria を欠く `criteria_evaluated` があれば、script は全部を一度に stderr へ並べて exit 3 で返し、何も書かない。verdict が PASS になるのは、score が threshold 以上で、機械の high 違反が無く、判定がすべて PASS のときだけ。`target` は `lint-content-review.py --print-target` から取る。

findings が無ければ 2 verdict を両方receiptへ束縛する。findings があれば該当obligationの対象だけを修正し、次節の 3 点で 1 回再評価する。

### 改善後の再レビュー (3 点に絞る)

初稿診断 (R5) や `run-elegant-review` で選んだ指摘を直したあとに、文書全体を 4 条件と rubric で読み直すと、すでに PASS した節をもう一度読むことになる。改善後に確かめるのは次の 3 点だけである。

1. **選んだ指摘が解消したか**: 読むのは指摘の本文と、その `finding_locations` の節。
2. **変わった hunk に新しい C1-C4 違反や rubric の high 違反が無いか**: 読むのは、適用前の写しか git との差分の hunk と、その hunk を含む節。rubric の high 違反は読んで判断せず、現在の SKILL.md で `render-findings-score.py` を回して確かめる。
3. **criteria の被覆**: frontmatter の criteria が全部 `criteria_evaluated` に入るか。lint が機械で確かめるので LLM は読まない。

結び直しは安い経路から順に試し、通らなければ次へ進む (各経路の条件は「レビュー由来の修正後の sha 結び直し」)。

| 順 | 経路 | LLM | 通る条件 |
|----|----|----|----|
| 1 | `sync-content-review-sha.py --finding-ids` | 使わない | 変わった節が、挙げた指摘の `finding_locations` の節に収まる |
| 2 | `sync-content-review-sha.py --replay` | 使わない | 登録済みの変換を当て直すと、現在の SKILL.md と bytes で一致する |
| 3 | `sync-content-review-sha.py --scoped-review` | 変わった節だけを読む独立 reviewer 1 context | 範囲の上限に収まり、上の 1・2 が PASS |
| 4 | 全体の再レビュー | 文書全体を読む 1 context (前節の incremental) | 上のどれも通らない。新しい verdict を書き、`sha_rebinds[]` はそこで切れる |

rubric の指摘 (`render-findings-score.py` が書く `negative_feedback`) は `finding_locations` を持たないので、`--finding-ids rubric:N` では結び直せない。直したら 3 か 4 を使う。

### exhaustive 1: elegance review (30 思考法 × 4 条件)

```
Agent({
  subagent_type: "run-elegant-review",
  prompt: "<plugin>/<skill> を Phase1 思考リセット → Phase2 3並列分析 → Phase3 改善で検証。max_iter=3。
    verdict json を eval-log/<plugin>/<skill>/content-review/elegance-verdict.json に
    schemas/content-review-verdict.schema.json 準拠で保存すること。"
})
```

`elegant-improvement-executor` は Phase 3 専用であり、content-review の入口として直接呼ばない。入口を `run-elegant-review` に固定することで、思考リセットと 30 思考法 coverage を省略しない。

### exhaustive 2: rubric review (規範採点)

```
Agent({
  subagent_type: "assign-skill-design-evaluator",
  prompt: "<plugin>/<skill> を rubric (ref-skill-design-rubric) で採点。
    機械で採点できない rule の判定を judgments.json に書き、
    render-findings-score.py --write-rubric-verdict eval-log/<plugin>/<skill>/content-review/rubric-verdict.json
    --judgments <judgments.json> で verdict を書かせること (verdict JSON を手で書かない)。"
})
```

## verdict 成果物 (CI互換projection)

`schemas/content-review-verdict.schema.json` 準拠。これらは既存CIとの互換projectionであり、再利用判断の正本は `schemas/verification-evidence.schema.json` のreceipt。`target` は手で組まず、レビューを始める前に `python3 scripts/lint-content-review.py --print-target <plugin>/<skill>` の出力をそのまま写す (`skill_md_sha256` と同じ値の `reviewed_skill_md_sha256`、references/ などを含めた `skill_dir_digest` が入る)。最小:

```json
{
  "target": {
    "plugin": "skill-foo", "skill": "run-bar",
    "skill_md_sha256": "<64 hex>", "reviewed_skill_md_sha256": "<64 hex>", "skill_dir_digest": "<64 hex>"
  },
  "review_kind": "elegance",
  "verdict": "PASS",
  "reviewer": "run-elegant-review",
  "reviewed_at": "2026-05-26T12:00:00Z",
  "iterations": 2,
  "feedback_loop": {
    "loop_scope": "both",
    "criteria_evaluated": ["IN1", "OUT1", "OUT2"],
    "positive_feedback": ["再利用可能な良設計判断"],
    "negative_feedback": [],
    "iteration": 2,
    "iteration_limit": 3,
    "hook_trigger": "manual",
    "next_action": "none"
  },
  "finding_locations": {
    "elegance:1": {"sections": ["手順 > Step 2"], "source_id": "F-0003"}
  }
}
```

`negative_feedback` に指摘を書いたら、`finding_locations` に「その指摘を直すとき触れる節」を `<review_kind>:<n>` ごとに書く。n は `negative_feedback` の 1 始まりの位置。節は SKILL.md の見出しの文字列で、同じ見出しが複数あれば `親 > 子` で一意にする。`#` (文書全体) は挙げられない。指摘が id を持つ所見から来たとき (`/skill-improve` が振る `F-NNNN`、`run-elegant-review` の `findings.json` の `issues[].id`、初稿診断 R5 の id) は、その id を `source_id` に必ず書く。改善側は利用者が選んだ id のまま `--finding-ids F-0003` と渡せ、`<review_kind>:<n>` へ読み替える必要がない。2 verdict に同じ `source_id` があれば、その id 1 つで両方の指摘を使う。`finding_locations` の無い指摘は、修正を当てても結び直せない (次節)。

## 機械検査 (CI / pre-push)

`scripts/lint-content-review.py --all` (下記「強制の経路」の CI 段):

- 全 skill (symlink と Codex 配布用コピーを除く) について `eval-log/<plugin>/<skill>/content-review/{elegance,rubric}-verdict.json` の存在 + `verdict=="PASS"` + `target.skill_md_sha256` が現在の SKILL.md と一致することを検査
- `target.skill_dir_digest` があれば、SKILL.md 以外でモデルが読む文書 (references/ prompts/ schemas/ templates/ など。scripts/ tests/ fixtures/ は除く。正本は `feedback_contract_ssot.CONTENT_REVIEW_DIGEST_EXCLUDE`) の digest と一致することを検査 (stale-dir-digest)。`--changed-only` は、その範囲の file が変わった skill も検査に入れる
- `sha_rebinds[]` の連鎖を検査 (rebind-chain): 最初の `from_sha` が `target.reviewed_skill_md_sha256`、各 `from_sha` が直前の `to_sha`、最後の `to_sha` が `target.skill_md_sha256`。各記録は `finding_ids`・`replay`・`scoped_review` のどれか 1 つだけを持つ。elegance と rubric は同じ `sha_rebinds` / `reviewed_skill_md_sha256` / `skill_dir_digest` を持ち (pair-mismatch)、1 つの指摘 (id・本文) は 1 回しか使えない
- `scoped_review` の記録を検査 (scoped-review): reviewer が変更した本人でない、節が 1〜3 個、`content-review/scoped-reviews/<to_sha>.json` の写しがあり、その sha256 と中身 (plugin・skill・from/to・sections・reviewer・PASS/PASS・指摘 0 件) が記録と一致する。1 本の連鎖に範囲つき再レビューは 2 回まで
- `feedback_loop` は必須。`criteria_evaluated` は**量産先 SKILL.md frontmatter** の `feedback_contract.criteria[].id` 全件と突合し、未評価 ID があれば PASS 不可（frontmatter が正本＝携帯する評価基準。trace は frontmatter 不在時の後方互換 fallback）
- `kind: ref` / symlink skill は対象外。`harness-creator` 自身は dogfooding 対象なので CI/pre-push では除外しない
- 違反時 exit 1 → merge ブロック

### path 改名時の verdict 移行 (retarget 規約)

plugin / skill の改名で verdict の置き場・`target.plugin` が変わる場合の正規手順を定義する (2026-07-02 plugin 改名で確立):

- **SKILL.md の内容 sha256 が不変**のまま path だけ変わった場合に限り、既存 verdict を新パスへコピーし `target.plugin` / `target.skill` を更新+`retargeted_from` 監査キー (旧 eval-log パス+改名日) を追記してよい。sha 不変 = 同一 artifact の証明であり再評価は不要。
- **SKILL.md の内容が 1 byte でも変わった**場合は独立 SubAgent による genuine 再生成が必須。`target.skill_md_sha256` / 評価値 / `criteria_evaluated` の手書換は**偽装**であり禁止 (既存判例どおり)。唯一の例外は次節「レビュー由来の修正後の sha 結び直し」で、これも手で書き換えず script が条件を確かめてから結び直す。
- 旧パス側の verdict は凍結アーカイブとして残す (遡及書換しない)。

### レビュー由来の修正後の sha 結び直し

SKILL.md を 1 byte でも変えると `target.skill_md_sha256` がずれ、`lint-content-review.py` は stale-sha で FAIL する。レビューが勧めた修正を当てただけでも stale になるため、「再レビュー → 新しい指摘 → 編集 → また stale」が周回する。stale-sha の判定は変えない。レビュー由来の修正と審査を経ない書き換えの区別は、修正を当てた直後にだけ呼ぶ決定論 script `run-elegant-review/scripts/sync-content-review-sha.py` が受け持ち、lint は script が残した記録が切れずにつながっているか (連鎖) を見る。

```bash
# 指摘を当てる前に写しを取る (git に適用前の版があれば省いてよい)
cp plugins/<plugin>/skills/<skill>/SKILL.md "$SCRATCH/before.md"
# 指摘を当てたあと
python3 plugins/harness-creator/skills/run-elegant-review/scripts/sync-content-review-sha.py \
  --plugin <plugin> --skill <skill> --from-sha <修正前に実ファイルから測った sha256> \
  --finding-ids elegance:1,rubric:2 --from-file "$SCRATCH/before.md" [--dry-run]
```

script は次の 5 条件を**全部**満たすときだけ、両 verdict の `target.skill_md_sha256` を現在の sha へ結び直す (c・d は `--finding-ids` のとき。`--replay` と `--scoped-review` は c・d の代わりに下記の条件を見る)。

- a. `elegance-verdict.json` と `rubric-verdict.json` が両方あり、どちらも `verdict=PASS`。`target.plugin` / `target.skill` が対象と一致する。
- b. 両 verdict の `target.skill_md_sha256` が `--from-sha` と一致し、`sha_rebinds[]` の最後の `to_sha` ともつながっている。つまり verdict を取った後、今回の修正より前に別の編集が入っていない。
- c. `--finding-ids` が空でなく、各 id が実在の指摘を指し、過去の結び直しで使われていない。id は `<review_kind>:<n>` (n はその verdict の `feedback_loop.negative_feedback` の 1 始まりの位置) か、`finding_locations[*].source_id` に書かれた元の id (`F-0003` など)。どの verdict の `source_id` にも無い id は拒否する。記録には読み替えた後の `<review_kind>:<n>` を残す。
- d. 変わった節が、挙げた指摘の `finding_locations` の節 (とその子の節) に収まる。適用前の SKILL.md (`--from-file`、無ければ git の index・HEAD・直近 64 commit から sha256 が `--from-sha` の版) と現在を見出しで節に分けて比べる。code fence の中の `#` 行は見出しに数えない。さらに、下の範囲つき再レビューと同じ上限と保護を当てる。変わった節が 3 を超える、変わった行が 60 を超える、変わった節が入出力契約の中にある、または criteria が名指す節 (とその子の節) にあるときは拒否する。経路で境目が違うと、大きな変更ほど緩い経路で通せてしまうためである。
- e. verdict が `target.skill_dir_digest` を持つなら、それが現在の skill ディレクトリの digest と一致する。

結び直しでは `sha_rebinds[]` に `{from_sha, to_sha, finding_ids, rebound_at, tool}` を追記し、`target.reviewed_skill_md_sha256` が無ければ元のレビューの sha を書く (連鎖の起点)。`verdict` / `reviewer` / `reviewed_at` / `iterations` / `feedback_loop` / `finding_locations` は変えない。両ファイルは一時ファイルと `os.replace` で置換し、片方だけ書き換わった状態を残さない。現在の sha が `--from-sha` と同じなら noop、両 verdict がすでに現在の sha なら already-bound を返す。どちらも書き込みはなく exit 0。2 verdict の `target.reviewed_skill_md_sha256`・`skill_dir_digest`・`sha_rebinds` が食い違うとき (lint の pair-mismatch) は、どの経路でも書く前に拒否する。拒否は exit 1、引数や入出力の誤り (`--from-file` の sha が `--from-sha` と違うとき、verdict の `target` や `sha_rebinds` の形が崩れているとき、SKILL.md が UTF-8 で読めないときを含む) は exit 2。

**機械的な移行 (`--replay <移行 id>`)**: 内容の意味を変えない決定的な変換か、全 skill 共通の契約の定型語句だけを置き換える決定的な変換を全 skill へ当てたとき (例: `artifact-delivery-v1` = 契約の写しを `artifact_delivery: artifact-delivery-v1` の参照へ置き換える harness-vvd の移行、`diagnostic-choice-2way` = 初回の選択肢を 4 択から `accept-as-is / diagnose` の 2 択へ書き換える harness-znj の移行) は、`--finding-ids` の代わりに `--replay artifact-delivery-v1` を渡す。script は登録済みの変換 (`REPLAYS`。いまは `lint-entrypoint-artifact-first.py` の `rewrite_copied_contract` と `rewrite_diagnostic_choices`) を適用前の SKILL.md に当て直し、結果が現在の SKILL.md と bytes で一致するときだけ結び直す。記録は `finding_ids` の代わりに `replay` を持つ。変換のほかに 1 文字でも変えていれば拒否する。変換を登録するのは、変換の持ち主が「frontmatter の他のキーと本文を変えない」こと、共通契約の定型語句を置き換える変換なら「語句の表の外を 1 文字も変えず、表で直せない書き方が残る SKILL.md には当てない」ことを test で示したものだけ。skill ごとの判断に触れる書き換えは、この経路を使わず再レビューする。

**範囲つき再レビュー (`--scoped-review <JSON>`)**: 指摘を当てたついでに節の外も少し直したときなど、`--finding-ids` の節に収まらない小さな変更を、全体を読み直さずに結び直す。差分の大きさだけで結び直すことはしない。必ず独立 reviewer が変わった節を読む。reviewer は変更した本人以外で、`assign-skill-design-evaluator` か `run-elegant-review` を使う (`root`・`self`・`elegant-improvement-executor` は不可)。reviewer は変わった節だけを「改善後の再レビュー」の 3 点で読み、次の JSON を作業用の場所に書く。rubric の PASS は感想で書かない。現在の SKILL.md で `render-findings-score.py` を回して high 違反が無く、変わった節にかかる判定 rule (BD-004 など) を読み直して PASS のときだけ書く。

```json
{"kind": "scoped-content-review", "plugin": "<plugin>", "skill": "<skill>",
 "from_sha": "<修正前の sha256>", "to_sha": "<現在の sha256>",
 "sections": ["手順 > Step 2"], "verdicts": {"elegance": "PASS", "rubric": "PASS"},
 "negative_feedback": [], "reviewer": "assign-skill-design-evaluator", "reviewed_at": "2026-11-14T12:00:00Z"}
```

```bash
python3 plugins/harness-creator/skills/run-elegant-review/scripts/sync-content-review-sha.py \
  --plugin <plugin> --skill <skill> --from-sha <修正前の sha256> \
  --scoped-review "$SCRATCH/scoped-review.json" --from-file "$SCRATCH/before.md"
```

`--finding-ids` とは同時に渡せない。次のどれかに当たると script は拒否し、全体の再レビューを求める。上限の正本は `feedback_contract_ssot.SCOPED_REVIEW_*` で、schema・lint・script は同じ値を使う。

- 2 つの verdicts が PASS でない、または `negative_feedback` が空でない。指摘が出たら、直してから全体を再レビューする。
- frontmatter、見出し (追加・削除・改名・並び替え)、最初の見出しより前のどれかが変わった。
- 変わった節が `sections` の外にある。`sections` が 3 を超える。変わった行が 60 を超える。
- 変わった節が入出力契約の節 (`Purpose & Output Contract` / `入出力契約`) にある。または frontmatter の criteria が名指す節かその子の節である。成果物の約束と評価基準は、一部だけ読んで決めない。
- `sections` のどれかが入出力契約の節を名指す (`親 > 子` のどの段でも)。lint はこの記録を通さないので、script も書く前に止める。
- 前の全体レビューから数えて、範囲つき再レビューがすでに 2 回ある。小さな結び直しを重ねるうちに、誰も全体を読まない状態が続くのを防ぐ。
- 起点の sha (`target.reviewed_skill_md_sha256`) が無い。連鎖が切れている。`skill_dir_digest` が合わない。

通ると script はレビューの写しを `content-review/scoped-reviews/<to_sha>.json` に置き、`sha_rebinds[]` に `scoped_review` (sections・reviewer・reviewed_at・写しの path と sha256) を足す。lint は写しが残っているかと、写しの sha256 と中身が記録と一致するかを確かめる。写しを後から書き換えると lint で落ちる。

**再レビューが要る場合** (script は exit 1 で拒否し、結び直さない):

- verdict が FAIL / INCOMPLETE か、片方の verdict が無い。
- `--from-sha` が verdict の sha と一致しない。審査を経ない編集が先に入っている。`sha_rebinds[]` の連鎖が切れている。
- 指摘の無い verdict (`negative_feedback` が空) しかない。引ける id が無いので、どんな編集も再レビューになる。
- id が存在しないか、すでに使われている (1 指摘で結び直せるのは 1 回)。使用済みかは指摘本文でも見るので、2 verdict に同じ本文で並ぶ指摘を、片方の id で使ったあともう片方の id で再び使うことはできない。
- 挙げた指摘に `finding_locations` が無い、節が見つからない・一意に決まらない、または変更がその節の外にある。frontmatter・見出し (追加・削除・改名・並び替え・段の変更)・最初の見出しより前・`#` 直下の前書きの変更は、どの指摘の節にも入らないので必ず再レビューになる。
- references/ などを変えて `skill_dir_digest` が合わない。
- 適用前の SKILL.md が `--from-file` にも git にも無い。

拒否されたら verdict JSON を手で書き換えず、「要再レビュー」として報告する。変更が範囲つき再レビューの上限に収まるなら `--scoped-review` を使い、収まらなければ独立 evaluator に verdict を作り直させる。script は変更が節に収まることまでは確かめるが、節の中の書き換えが指摘どおりかまでは確かめない。`sha_rebinds[]` の from / to / ids を監査の手がかりにし、疑わしければ再レビューする。`sha_rebinds[]` を手で書くのは偽装であり、連鎖検査がつなぎ目の食い違いを止める。

## 強制の経路 (CI / pre-push)

content-review は Claude Code hook から発火させず、queue も持たない。重い LLM 評価は hook から起動しない。semantic evaluator が動くのは、incremental の `llm_batches[]` で artifact 提示後に利用者が診断を選んだときと、exhaustive を明示したときだけである。verdict の存在・PASS・SHA 一致は、次の機械層だけが強制する。不可逆操作や秘密の防止は、それぞれの安全 hook に残す。

| 層 | 実行 | 強制する内容 |
|----|----|----|
| CI (`.github/workflows/governance-check.yml`) | `python3 scripts/lint-content-review.py --all` | 全 skill の 2 verdict の存在・PASS・SHA 一致・`feedback_loop`・criteria 突合。違反は exit 1 で merge をブロックする (最終強制層) |
| pre-push (`.githooks/pre-push` → `scripts/run-ci-checks.sh`) | CI workflow の段をそのまま再生 | push 前に CI と同じ検査を先に行う。`PUSH_SKIP_CI=1` で飛ばしても CI で再検査される |
| 手元 (`make content-review`) | `lint-content-review.py --all` | 同じ検査を任意に回す。差分だけ見たいときは `--changed-only` |

Codex 委譲の完了も新しい自動実行層を増やさない。`delegate-codex-skill-review` はレスポンス JSON / patch / handoff を artifact として保存し、その artifact を既存の content-review verdict 契約に正規化して評価する。

## skip / opt-out

- `brief.skip_content_review: true` または CLI `--skip-content-review` を build 時に明示時のみ skip
- 必ず `trace.layer_decisions` に理由記録 (例: 「typo 修正のみで内容変更なし」)
- skip した skill は `git diff` で SKILL.md 変更が出ない場合のみ整合 (内容変更があれば必ず評価する)
- ローカルで skip 通そうとしてもリモート CI が成果物不在で block する (二重防御)

## ループ until pass

verdict=FAIL の場合:
- AI が指摘内容に従い SKILL.md / references を改善
- 再評価して PASS まで反復 (max_iter=3)
- max_iter 到達で INCOMPLETE → `human_review_required: true` で停止 (force_pass 禁止)

## 関連

- `workflow-manifest.json` phase `content-review` (step 12, profile-controlled / incremental default)
- `references/verification-obligation-protocol.md` (選定・fingerprint・receiptの正本)
- `schemas/verification-{contract,evidence}.schema.json`
- `schemas/content-review-verdict.schema.json`
- `/scripts/lint-content-review.py` (top-level)
- `plugins/harness-creator/skills/run-elegant-review/`
- `plugins/harness-creator/skills/assign-skill-design-evaluator/`
- `ref-skill-design-rubric`
