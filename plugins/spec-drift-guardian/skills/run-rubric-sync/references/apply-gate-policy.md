# apply-gate-policy

`run-rubric-sync` (C02) の **allowlist・apply-gate 条件 (G1-G5)・pre/post-image hash 手順・proposal_sha256 正規化・fail-closed マトリクス**の逐語正本。SKILL.md と `prompts/R2-plan.md`/`prompts/R3-apply.md` はここを参照し、規則を各所へ再定義しない (SSOT 一元化)。

## 1. allowlist (target_path の許容集合)

apply mode が Edit してよいのは、`target_path` が次の glob の**いずれか**に一致する場合**のみ**。glob 外は propose にも含めず、apply では変更 0 件で fail-closed する。

| kind | glob | 例 |
|---|---|---|
| rubric | `plugins/harness-creator/**/rubric.json` | `plugins/harness-creator/skills/assign-skill-design-evaluator/references/rubric.json` |
| template | `plugins/harness-creator/**/templates/**` | `plugins/harness-creator/skills/run-build-skill/templates/...` |
| schema | `plugins/harness-creator/**/*.schema.json` | `plugins/harness-creator/skills/run-skill-create/schemas/build-trace.schema.json` |

- 判定は Python `fnmatch`/`pathlib.PurePath.match` 等の**決定論照合**で行い、LLM の目視で許可しない。
- `target_path` は repo-root 相対で正規化する (先頭 `./`・`..` を排除、symlink 追跡なし)。
- allowlist の**外側**にある triage 影響 (例: guardian 自身や他 plugin) は proposal に含めず、「対象外パス」として理由を記録する (guardian が自 drift 源になるのを防ぐ)。

```python
import fnmatch, pathlib
ALLOWLIST = [
    "plugins/harness-creator/**/rubric.json",
    "plugins/harness-creator/**/templates/**",
    "plugins/harness-creator/**/*.schema.json",
]
def in_allowlist(path: str) -> bool:
    p = pathlib.PurePosixPath(path).as_posix()
    return any(fnmatch.fnmatch(p, g) for g in ALLOWLIST)
```

## 2. apply-gate 条件 (G1-G5 全充足で apply、1 つ欠けたら変更 0 件)

| # | 条件 | 検証 | fail 時 |
|---|---|---|---|
| G1 | **監査 PASS** | C04 `sync-audit-verdict.json` の `verdict=="PASS"` かつ `proposal_sha256==sync-proposal.proposal_sha256` (container digest) | 変更 0 件・「監査不一致/未 PASS」で停止 |
| G2 | **明示承認** | container の `approval.granted==true` かつ `by`/`evidence` が非 null | 変更 0 件・「未承認」で停止 |
| G3 | **allowlist 内** | 全 `proposals[].target_path` が §1 の glob に一致 | 変更 0 件・「対象外パス」で停止 |
| G4 | **pre-image 一致** | 各 proposal の適用直前に実ファイル sha256 を再計算し `proposals[].pre_image_sha256` と一致 (`pre_image_sha256=null` は新規作成提案=対象ファイル不在が正) | 変更 0 件・「hash drift」で停止 |
| G5 | **独立 verifier の同意 (対象束縛つき)** | C03 `triage-verdict.json` の `agree==true` **かつ** `diff_sha256 == triage-report.diff_sha256` | 変更 0 件・「不同意」/「別 diff への agree 流用」で停止 |

**G1-G5 の機械検証 (適用直前に必ず実行)**:

```bash
python3 $CLAUDE_PLUGIN_ROOT/scripts/check-triage-complete.py --mode pre-apply \
  --issue <N> --sync-proposal <sync-proposal.json> \
  --sync-audit-verdict <sync-audit-verdict.json> \
  --triage-report <triage-report.json> --triage-verdict <triage-verdict.json> \
  --target-root .
```

exit 0 = apply 可 / exit 1 = G1-G5 のいずれか不成立で**変更 0 件のまま停止** (`reasons[]` に理由) / exit 2 = artifact malformed・引数不足。`--triage-report` / `--triage-verdict` は G5 の機械検証に使うため pre-apply でも必須 (省略すると exit 2 で apply へ進めない)。close ゲート (`--mode close` 既定) は適用**後**の post-image を突合するため pre-image drift を構造上検出できない (適用後の実ファイルは post-image になっている)。G4 を LLM の shasum 手順だけに委ねると見落とし時に drift したまま適用されるため、**この script の exit 0 を得てから Edit する**。

- **G5 の対象束縛が要る理由**: `agree=true` は「**特定の diff についての**同意」であり、flag だけを見ると主語が浮く。C01 を再実行して triage-report が変わったのに C03 を再実行していない場合、旧 verdict の `agree=true` が流用され、誤 triage に基づく Edit が着弾する。close ゲートは同じ一致を強制するが、そこで弾いても実ファイルは既に変わっている。
- G1-G5 は AND。**部分適用は禁止**: `proposals[]` のうち 1 つでも G1-G5 を満たさなければ、その issue の apply を実行せず全体を停止する (中途半端な適用で close ゲートを誤誘導しない)。

## 3. pre/post-image hash 手順

対象ファイルの**内容 sha256** を用いる。macOS/Linux で同一値を得るため先頭 64hex を採る:

```bash
# macOS
shasum -a 256 "$TARGET" | cut -d' ' -f1
# Linux (fallback)
sha256sum "$TARGET" | cut -d' ' -f1
```

- **pre_image_sha256** = propose 時点の対象ファイル内容 hash。apply 直前に再計算して照合 (G4)。
- **post_image_sha256** = Edit 適用**後**の対象ファイル内容 hash。status=applied_verified では非 null 必須。
- 対象ファイルが存在しない場合の hash は `null` とし、新規作成提案かどうかを before=null で表す。存在しないのに before≠null なら fail-closed。

## 4. proposal_sha256 の正規化 (C04 と一致させる digest)

sync-proposal は `proposals[]` を正本とするコンテナ形。container の `proposal_sha256` は、apply 時に付与される揮発フィールドで動くと C04 監査と不整合になるため、**不変核のみ**で計算する:

- container の `issue` を先頭に固定し、続けて全 `proposals[]` 要素の不変核を連結する。
- 各 proposal 要素の不変核キー (この順に固定): `target_path`, `axis`, `before`, `after`, `proposed_diff`, `pre_image_sha256`。
- container の `status`/`approval`/`proposal_sha256` 自身、各要素の `post_image_sha256`/`validator_results` は digest 計算から**除外**する。
- JSON は `sort_keys=True, ensure_ascii=False, separators=(",", ":")` で正規化し UTF-8 で sha256 を取る。
- proposals 要素は `target_path` 昇順に並べてから連結する (要素順に依存しない安定 digest)。単一要素でも同一手順。

```python
import hashlib, json
PROPOSAL_CORE = ["target_path", "axis", "before", "after", "proposed_diff", "pre_image_sha256"]
def proposal_digest(container):  # container: sync-proposal (issue + proposals[])
    norm = sorted(container["proposals"], key=lambda x: x["target_path"])
    blob = json.dumps({"issue": container["issue"]}, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    blob += "".join(
        json.dumps({k: it[k] for k in PROPOSAL_CORE}, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        for it in norm
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
```

## 5. validator_results (apply 後の検証)

適用後、対象 artifact の妥当性を決定論 validator で確認し `validator_results[]` に記録する (status=applied_verified では 1 件以上):

| target kind | validator (例) | passed 条件 |
|---|---|---|
| schema (`*.schema.json`) | `python3 -c 'import json,sys; json.load(open(sys.argv[1]))'` + JSON Schema self-validate | JSON parse 成功 ∧ meta-schema 準拠 (exit 0) |
| rubric (`rubric.json`) | `python3 -c 'import json; json.load(...)'` + rubric 必須キー検証 | parse 成功 ∧ 必須キー充足 |
| template | 該当 lint (例: プレースホルダ整合) / JSON なら parse | lint exit 0 |

- `validator_results[]` の各要素は `{validator, exit_code, passed}`。`passed=false` が 1 件でもあれば適用を revert 候補として提示し、status を applied_verified に**しない** (post-image 検証未達)。
- validator が無い kind でも最低 1 件 (parse/構文チェック) は実行する。無検証で applied_verified にしない。

## 6. fail-closed マトリクス (期待挙動の一覧)

| case | 期待 status | 実ファイル変更 | 記録 |
|---|---|---|---|
| 承認済み・監査 PASS・allowlist 内・hash 一致 | applied_verified | allowlist 対象のみ Edit | post hash + validator |
| 未承認 (approval.granted=false) | proposed のまま | 0 件 | 理由=未承認 |
| 監査 FAIL / proposal_sha256 不一致 | proposed のまま | 0 件 | 理由=監査不一致/未 PASS |
| pre-image hash drift | proposed のまま | 0 件 | 理由=hash drift・再 propose 促し |
| allowlist 外 target_path | 提案に含めない/apply せず | 0 件 | 理由=対象外パス |
| complete≠true / triage-verdict agree=false | proposed 生成せず | 0 件 | 理由=上流未確定・fail-closed |

いずれの fail-closed でも **commit / PR / issue close は行わない**。
