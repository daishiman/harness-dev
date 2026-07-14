# 内容 adequacy 検査プロトコル (Step 12 content-review)

機械 lint だけでは「ひな形通り」だけ確認で内容空虚を素通りさせる欠陥がある。
本プロトコルは **verification obligation resolver → 必要時だけLLM評価 → verdict互換投影 → 機械検査** で「内容の良さ」を build harness に組み込む。正準の選定・再利用契約は `verification-obligation-protocol.md` であり、本書はcontent-review verdictとhookの互換投影を定める。

**位置づけ (証拠の主張型直交)**: 静的レビュー (content-review / elegant-review / rubric) は **design claim (設計 adequacy) の正本**であり、静的設計ゲートの核 (実行 acceptance は Gate D)。behavioral claim (実行挙動: 自走完遂 / 入れ子 Skill / 対話 gate 越え / goal 達成) の受け入れ収束は **Gate D (`run-skill-live-trial`) の実走証拠のみ**を根拠とし、静的 verdict を流用しない (評価縮退の禁止)。ゲート帰属の正本は `$PLUGIN_ROOT/references/orchestrate-gate-pattern.md`。

**重要**: `SKILL.md SHAが変わったらreviewを1回起動` はlegacy admissionであり正準cost modelではない。正準はclaim、入力slice、checker契約、上流claim fingerprintに束縛したreceiptである。SHA verdictはCI互換projectionとして残すが、review起動判断は `plan-verification-obligations.py` の `llm_batches[]` だけに従う。

## 役割境界 (機械 vs LLM)

| 層 | 検査対象 | 実行場所 | 実装 |
|----|---------|---------|------|
| 機械層 | ファイル構造 / frontmatter / 命名 / 行数 / symlink drift / **verdict json の存在と PASS** | CI + pre-push | lint 群 + `lint-content-review.py` |
| LLM 層 | machine proof後にも未解決の **semantic obligation** (意図反映 / 4条件 / rubric 規範) | **ローカル Claude Code のみ** | incremental=`llm_batches[]` ごとに1 context、exhaustiveのみadversarial audit |

リモート CI で LLM を起動しない (API 課金・所要時間回避)。ローカルで評価して json を commit し、CI は存在のみ機械検査する。

## build 完了直後の profile 制御 (incremental default)

profile は `incremental|exhaustive|build-only` の閉列挙で、無指定は `incremental`。`incremental` はgraph-level contractを解決し、current fingerprintに束縛されたPASS receiptを再利用する。入力または上流proofが変わったsemantic obligationだけを実context byte量でbatch化し、builderと別の evaluatorへ渡す。結果は既存の `elegance-verdict.json` / `rubric-verdict.json` に分離投影し、両ファイルを同obligation receiptのevidenceとして記録する。未達・矛盾・低confidenceはAgentを増やさず `escalate` で停止する。

`exhaustive` を利用者が明示した場合だけ、下記の elegance 30思考法と rubric 評価を独立実行し最大3周する。`build-only` は LLM を起動せず trace へ `not-run(profile=build-only)` を残す (PASS証跡の偽装禁止)。

### ループ分類

| ループ | 目的 | 評価基準 | 上限 | 発火 |
|----|----|----|----|----|
| Inner loop | 小さな機能・責務単位で現在ゴールを満たす | `feedback_contract.criteria[loop_scope=inner]` + goal-seek checklist | 再評価=`inner_loop.max_iterations` (既定3) / goal-seek 手順反復=`loop_bounds.goal_seek_inner` (5) ※別ループ | build 中 / evaluator findings |
| Outer loop | ハーネス全体がユーザー目的に近づいているかを改善する | 未解決semantic obligation + 4条件 | incremental=同じobligationの修正→再評価1回、exhaustiveのみ最大3 | obligation resolver / Stop queue / pre-push |

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

`plan-verification-obligations.py` の各 `llm_batches[]` について、列挙された `obligation_ids` と `context_paths` だけを `assign-skill-design-evaluator` へ渡す。対象外skill、全repository、全route reportは読ませない。batch内で(a)矛盾なし、(b)漏れなし、(c)規約整合、(d)依存関係整合、(e)rubric high severity 0 を一度に判定する。findings が無ければ同じ評価結果を互換2 verdictへ分け、両方をreceiptへ束縛する。findings があれば該当obligationの対象だけを修正し1回再評価する。30思考法を使用したと申告してはならない。

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
    verdict json を eval-log/<plugin>/<skill>/content-review/rubric-verdict.json に
    schemas/content-review-verdict.schema.json 準拠で保存すること。"
})
```

## verdict 成果物 (CI互換projection)

`schemas/content-review-verdict.schema.json` 準拠。これらは既存CIとの互換projectionであり、再利用判断の正本は `schemas/verification-evidence.schema.json` のreceipt。最小:

```json
{
  "target": {"plugin": "skill-foo", "skill": "run-bar", "skill_md_sha256": "..."},
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
  }
}
```

## 機械検査 (CI / pre-push)

`scripts/lint-content-review.py --changed-only --base origin/main`:

- `git diff origin/main...HEAD` から `plugins/*/skills/*/SKILL.md` 変更を抽出
- 各変更 skill について `eval-log/<plugin>/<skill>/content-review/{elegance,rubric}-verdict.json` の存在 + `verdict=="PASS"` + `target.skill_md_sha256` が現在の SKILL.md と一致することを検査
- `feedback_loop` は必須。`criteria_evaluated` は**量産先 SKILL.md frontmatter** の `feedback_contract.criteria[].id` 全件と突合し、未評価 ID があれば PASS 不可（frontmatter が正本＝携帯する評価基準。trace は frontmatter 不在時の後方互換 fallback）
- `kind: ref` / symlink skill は対象外。`harness-creator` 自身は dogfooding 対象なので CI/pre-push では除外しない
- 違反時 exit 1 → merge ブロック

### path 改名時の verdict 移行 (retarget 規約)

plugin / skill の改名で verdict の置き場・`target.plugin` が変わる場合の正規手順を定義する (2026-07-02 plugin 改名で確立):

- **SKILL.md の内容 sha256 が不変**のまま path だけ変わった場合に限り、既存 verdict を新パスへコピーし `target.plugin` / `target.skill` を更新+`retargeted_from` 監査キー (旧 eval-log パス+改名日) を追記してよい。sha 不変 = 同一 artifact の証明であり再評価は不要。
- **SKILL.md の内容が 1 byte でも変わった**場合は独立 SubAgent による genuine 再生成が必須。`target.skill_md_sha256` / 評価値 / `criteria_evaluated` の手書換は**偽装**であり禁止 (既存判例どおり)。
- 旧パス側の verdict は凍結アーカイブとして残す (遡及書換しない)。

## hook 発火と queue

Claude Code hook はレスポンス時間と副作用境界を守るため、**重い LLM 評価を直接実行しない**。hook は評価要求を `eval-log/review-queue.jsonl` へ queue 化するが、この queue は**診断ログ** (いつ・何が評価要求されたかの追跡証跡) であり、自動 consumer は存在しない (build / pre-push が queue を読んで消化する機構は無い)。評価の強制は queue ではなく次の 2 層が担う: (1) `Stop` hook が `{"decision":"block","reason":...}` を返して **Claude 本体に評価を実行させる** (トリガのみ・実行は本体)、(2) pre-push / CI の `lint-content-review.py` が verdict の存在・PASS・SHA 一致を機械検査する (最終強制層)。Stop block は無限ループ防止のため `stop_hook_active` 継続中は発火せず、`harness-creator` 自身の変更は対象外 (代わりに stdout 通知のみ出す)、env `HARNESS_CREATOR_NO_REVIEW_BLOCK=1` で opt-out できる。

| Hook | 役割 |
|----|----|
| `PostToolUse:Skill` | `run-build-skill` / `delegate-codex-skill-review` 等の完了後、`check-review-trigger.py` を queue-only で起動し、対象 artifact と hook_trigger を評価要求として記録 |
| `PostToolUse:Edit|Write` | SKILL.md / rubric / workflow-manifest 変更時に `check-review-trigger.py` を queue-only で起動し、stale verdict 再評価要求を記録 |
| `Stop` | `check-review-trigger.py`。未評価/stale skill を queue 化し、`decision:block` で Claude 本体へ差し戻す。本体はobligation resolverを再実行し、`llm_batches[]` がある場合だけ互換2 verdictを生成する。`run-elegant-review` + rubric evaluator は exhaustive 明示時だけ。`harness-creator` 自身は自己ブロック回避のため通知のみ、CI/pre-push は同じ2 verdict契約を強制 |
| `pre-push` / CI | `lint-content-review.py` で verdict の存在・PASS・SHA一致を強制 (最終強制層) |

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
