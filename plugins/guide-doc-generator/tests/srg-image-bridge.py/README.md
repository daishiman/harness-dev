# C21 `srg-image-bridge.py` 受入テスト (P04-C21-01 で赤に固定)

本ディレクトリは **実装より先に判定基準を固定する** ためのテスト群である。契約は全て
`plugin-plans/guide-doc-generator/briefs/script-brief-C21.json` の
`argv` / `stdin` / `stdout` / `stderr` / `exit_codes` / `write_scope` / `single_writer` /
`algorithm` / `acceptance_checks` / `failure_modes` / `network` と、
`briefs/RESOLUTION-P03.md` の **Y-01** (C21 の `network: true` と冪等再利用の位置づけ)、
`component-inventory.json` の C21 定義から起こしてある。P05 の実装がテストを自分に
都合よく書き換えられないよう、判定基準はここで確定させる。

## 実行

```bash
python3 -m unittest discover -s plugins/guide-doc-generator/tests/srg-image-bridge.py -p 'test_*.py'
```

Python 3.10+ の標準ライブラリのみ。repo ルートから実行する。

**P04-x-08 (RESOLUTION-R23 反映) 時点は 291 件中 120 件が赤で、内訳は failures のみ (errors 0)。**
R23 の 4 ファイル (`test_r23_*.py` 計 99 件) を追加し、共有 fixture (`_harness.section` /
`plan_payload`) を R23 後の計画形へ更新したため、既存ファイル側も「未実装の契約に触れた」赤へ変わる。
**既存 assert は 1 件も削除・弱体化していない** (`DelegationOnlyTest` は 9 件全緑のまま。`test_source_invariants.py` は 23 件全緑)。
初出時 (P04-C21-01) は 192 件中 188 件が赤だった。赤は import 例外では
なく「実装が未存在」「依存成果物が未存在」という診断可能なアサーション失敗
(`_harness.require_script` / `require_file`) である。緑の 4 件は
`test_cross_component.InventorySyncTest` — 実装に依存せず **plan 側の宣言だけ**を照合する検査
(`network: true` が inventory とブリーフの両方にあること等) なので、P04 時点でも通るのが正しい。

## この leaf が固定した 3 つの要点

1. **委譲であって再実装でない (C17 / AC-C21-1)。** `test_source_invariants.py` が、画像生成 API 呼び出し・
   プロンプト本文の組み立て・genome の複製・`base64` 化・`codex` の直接起動が **ソースに 0 件**であり、
   委譲が `subprocess`(`shell=False`) 経由の vendor script 2 本だけであることを静的に要求する。
   出力が正しく見えても自前実装なら R12 の設計が壊れているので、振る舞い検査だけでは足りない。
2. **fail-soft は skip であって成功ではない (C18 / AC-C21-2・3)。** exit 0 は「生成した」と
   「skip した」の両方を含むため、`test_stdout_contract.py` が
   *status で区別できること*・*skip 時も images を全件 `skipped` で列挙すること*・
   *skip 理由が `skip_reason` / `skip_detail` / stderr に現れること* を要求する。
   fail-soft の対象は「委譲先が無いこと」だけであり、**委譲が失敗したこと** (build-image-prompts.js の
   非 0 終了・PNG 未回収) は exit 1、**呼び出し契約違反** (必須欠落・motif 語彙違反・`--srg-root` 明示ミス) は
   exit 2 で、いずれも skip へ畳ませない。
3. **PNG のバイト列は C21 が最後まで持ち、data URI 化はしない (C13 境界)。** 回収は署名検査 →
   `copy2` → 再検査で、加工しない。`test_delegation_and_recovery.py` が
   `<assets-dir>/images/<slug>.png` のバイト列 = 作業ディレクトリの生成物であることを要求する。

## テスト実行時にネットワークも codex も起こさない仕掛け

- `_harness.make_fake_bin()` が **fake `node` / fake `codex`** を tmp の bin ディレクトリへ置き、
  `PATH` をそこだけに差し替える。fake node は `build-image-prompts.js` /
  `generate-images-codex.js` の CLI 形 (`<slide-dir> [--plan] [--genome] [--dry-run] [--batch] [--source]`)
  だけを模し、ファイルを置いて exit 0 を返す。実物の node も codex も動かず、通信も課金も起きない。
- fake の挙動は環境変数で切り替える: `HB_FAKE_NODE_VERSION` (版数)、`HB_FAKE_PROMPTS`
  (`all|none|fail`)、`HB_FAKE_PNGS` (`all|first|invalid|none`)。呼ばれた argv は
  `HB_FAKE_LOG` の JSON 行に積まれ、「起動していないこと」の検査に使う。
- `_harness.clean_env()` は既定で **`HB_ROOT` を tmp の偽 plugin root に向ける**。この repo には
  `plugins/slide-report-generator` が実在するので、これをしないと解決段 (c) が実物を拾ってしまい
  「SRG 不在」を再現できない。実物を使うのは
  `test_srg_resolution.RealPluginNeighbourTest` (兄弟解決の確認・`--dry-run`) だけで、
  そこでも node は fake のままである。

## 契約 id の対応表

| id | acceptance_checks の要旨 | 主に固定したファイル |
|---|---|---|
| AC-C21-1 | 自前の画像生成・プロンプト組み立てが 0 件で、委譲だけである (C17) | `test_source_invariants.py` (`DelegationOnlyTest` / `NoReimplementationAcrossScriptsTest`) |
| AC-C21-2 | SRG 実体不在 → exit 0・`skipped`/`srg-absent`・images 全件 skipped・node も codex も起動しない (C18) | `test_srg_resolution.py` (`AbsentSrgTest`)、`test_stdout_contract.py` (`SkipShapeTest`) |
| AC-C21-3 | node 不在 → exit 0・`runtime-absent`・`skip_detail` に node。起動を試みない | `test_runtime_gate.py` (`NodeAbsentTest` / `NodeVersionTest`) |
| AC-C21-4 | C01 の生成フローで画像ステップだけ skip され、成功として黙って畳まれない | `test_cross_component.py` (`BuildSkillContractTest`) — 判定本体は C01 の統合テストが持つ |
| AC-C21-5 | `--dry-run` → exit 0・`dry-run`・prompt/meta 生成・`delegated_commands` に codex exec・PNG 0 件 | `test_dry_run.py` |
| AC-C21-6 | 委譲先が exit 0 でも回収不足なら exit 1 / `partial` | `test_delegation_and_recovery.py` (`PartialRecoveryTest`) |
| AC-C21-7 | PNG 署名を持たない生成物は `failed`、素材へコピーしない | `test_delegation_and_recovery.py` (`InvalidPngTest`) |
| AC-C21-8 | genome に無い motif / `--srg-root` の明示ミス → どちらも exit 2 (skip へ畳まない) | `test_plan_validation.py` (`MotifVocabularyTest`)、`test_srg_resolution.py` (`SubstanceCheckTest`) |
| AC-C21-9 | 書き込みは `<assets-dir>` 配下だけ。SRG 配下・構成データ・HTML を変更しない | `test_write_scope.py` |
| AC-C21-10 | 標準ライブラリのみ (C27)。自前 socket 無し | `test_source_invariants.py` (`StdlibOnlyTest`) |
| AC-C21-11 | 全 slug が既存 PNG で満たされたら委譲先を起動せず exit 0・`generated`・バイト不変 | `test_idempotent_reuse.py` (`FullReuseTest`) |
| AC-C21-12 | `textPolicy` の既定が `baked-with-overlay` で `bakedText` が非空。`overlay-only` 固定がソースにも生成物にも残っていない (R23 (a)) | `test_r23_text_policy.py` (`DefaultPolicyTest`) |
| AC-C21-13 | `overlayText` 空 / 理由なし `overlay-only` はどちらも exit 2、node を起動しない | `test_r23_text_policy.py` (`OverlayTextIsAlwaysRequiredTest` / `OverlayOnlyRequiresReasonTest`) |
| AC-C21-14 | 焼き込みブロック数・字数の境界ちょうどは通り、超過と形式違反は exit 2。期待値は brief から読み、テストに数値リテラルを直書きしない (R23 (b)) | `test_r23_baked_text.py` |
| AC-C21-15 | `image_style_families.selection_rule.map` どおりに genome が振り分けられ、混在時は family ごとに `build-image-prompts.js` を起動する。明示上書きが勝ち、どちらも無ければ exit 2 (R23 (c)) | `test_r23_style_family.py` |
| AC-C21-16 | 平坦化の代理指標 (density_level / 3 役 motifs / adaptation_trace / meta 照合) の違反が exit 2。成功時は motifs が platform → primary → props の順で連結される (R23 (d)) | `test_r23_degradation.py` |
| AC-C21-17 | 密度語彙・motif 名・layoutTemplate 名をハードコードせず genome から読む。画素解析ライブラリの import が 0 件 (R23 (d)(e)) | `test_r23_degradation.py` (`RejectedChecksStayRejectedTest` / `GenomeIsNotCopiedIntoTestsTest`) |

ブリーフの他ブロックから起こした検査:

| 出所 | 固定した内容 | ファイル |
|---|---|---|
| `argv` / `exit_codes` 2 | 必須 flag・未知 flag・非ディレクトリ・JSON 不正・section 必須キー欠落 → exit 2 | `test_argv_and_exit_codes.py` |
| `stdin` | 使用しない (読むと非対話経路で詰まる) | `test_argv_and_exit_codes.StdinTest` |
| `stdout` / `stderr` | 判定 JSON のキー・enum・`path` は assets-dir 相対・人間向けの文は stderr だけ | `test_stdout_contract.py` |
| `algorithm` 3 | 解決順 (a)>(b)>(c)、実体判定は vendor script 2 本の実在 (名前ではない) | `test_srg_resolution.py` (`ResolutionOrderTest` / `SubstanceCheckTest`) |
| `algorithm` 4 | node major 下限 18、codex は本番のみ必須、vendor 配下の元位置から絶対パス起動 | `test_runtime_gate.py`、`test_dry_run.py` |
| `algorithm` 5-7 | 作業ディレクトリ `<assets-dir>/srg-work/assets/generated`、1 section = 1 slide、slug `sec-NN-<kebab>`、`pattern`/`textPolicy`/`backgroundSource`/`generation` の固定値 | `test_write_scope.py`、`test_plan_validation.DeckPlanShapeTest`、`test_stdout_contract.SlugContractTest` |
| `algorithm` 8 | motif 部分集合・40 字/12 字の下限・曖昧語禁止 → exit 2 | `test_plan_validation.py` |
| `algorithm` 9-10 | `--genome` を明示、build-image-prompts の非 0 は exit 1、prompt 0 件は exit 1 | `test_dry_run.py`、`test_delegation_and_recovery.DelegateFailureTest` |
| `algorithm` 12 | 冪等再利用は正規ステップ (P03 Y-01)。既存が壊れていれば再生成する | `test_idempotent_reuse.py` |
| `algorithm` 13-15 | 委譲先の exit code を鵜呑みにしない・署名検査・部分成功は exit 1 | `test_delegation_and_recovery.py` |
| `algorithm` 3b / 8b / 9 / 14b (R23) | family ごとの genome 解決 (同梱 genome の欠落は skip でなく exit 2)、R23 事前検査の診断コード、family 分割起動、回収 meta の drift 開示 (exit code は変えない) | `test_r23_style_family.py`、`test_r23_degradation.py` |
| `baked_text_discipline` / `image_style_families` / `degradation_proxy_checks` (R23) | (a) 既定 textPolicy / (b) 焼き込み量と 3 形式 / (c) family 全域写像 / (d) 平坦化代理指標 / (e) 全件同一構図の拒否 | `test_r23_text_policy.py`、`test_r23_baked_text.py`、`test_r23_style_family.py`、`test_r23_degradation.py` (詳細は `../R23-ALIGNMENT.md`) |
| `network` (P03 Y-01) | frontmatter の `network: true` と inventory の一致、かつ自前 socket 0 件 | `test_source_invariants.FrontmatterTest`、`test_cross_component.InventorySyncTest` |
| task-spec の受入判定 | 同一入力の再現性 (決定論変換部分のみ。PNG バイト一致は約束しない) | `test_determinism.py` |

## gaps (ブリーフから確定できず、テストで断定していない点)

| what | why |
|---|---|
| `--image-plan` のトップレベル形 (`sections` 以外) が未定義 | ブリーフは各 section のフィールドだけを規定し、`deck.title` / `background` / `accent` の出所を書いていない。fixture は `title` / `background` / `accent` をトップレベルに置いているが、**それらの欠落を exit 2 とする検査は書いていない**。C05 (agent-brief-C05) 側の出力契約と突き合わせて確定させること (ブリーフ `open_questions` 1 件目と同じ論点)。 |
| `skip_detail` の文言 | 「node/codex/version のどれか」とあるだけで書式が無いので、`node` / `codex` の語を含むこと・版数不足が読めることだけを要求している。 |
| `srg_root` の表現 (絶対パス / 相対) | ブリーフは `path` としか書いていない。テストは「vendor script 2 本を含むディレクトリを指していること」と、明示指定時は指定値と一致することだけを見る。 |
| `delegated_commands` の要素型 | 「実行した argv 列」とあり本番は argv 配列を要求したが、`--dry-run` で回収する codex コマンドは SRG の stdout 由来なので文字列の可能性がある。dry-run 側は list / str の両方を許し、`codex exec` を含む行があることだけを要求している。 |
| `--dry-run` 時の冪等スキップの扱い | algorithm 12 は本番経路の記述で、dry-run に既存 PNG があるときの status が未定義。テストは `status="dry-run"` のままで既存バイトが変わらないことを要求した (課金も上書きも起きない側に倒した)。この選択が誤りなら **テストではなくブリーフを直すこと**。 |
| 委譲時の環境変数の受け渡し | fake node/codex は `HB_FAKE_*` を読むので、実装が subprocess へ環境を **丸ごとは渡さない** 設計にすると fixture が動かない。ブリーフは env の scrub を要求していないため継承を前提にしている。scrub が必要なら allowlist ではなく denylist 側で設計し、この README を更新すること。 |
| AC-C21-4 の統合判定 | C01 の生成フロー全体は本 leaf の write_scope 外。ここでは C01 SKILL.md が C21 を起動し skip 理由と status をレポートへ出す契約を宣言していることだけを固定した。 |
