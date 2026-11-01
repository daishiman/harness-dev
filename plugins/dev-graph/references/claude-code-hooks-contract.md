# Claude Code hooks contract

## 配線方針

- 共有既定はplugin同梱の`hooks/hooks.json`。`.claude/settings.json`はplugin hookを使えない導入先だけの明示opt-in fallbackとし、`claude_hooks.source`は`plugin|project|disabled`のいずれか1つに固定する。
- initは既存`.claude/settings.json`を全書換せず、preview→構文検証→hooks配列の識別子付きdeep merge→atomic replaceを行う。既存hookは保持し、rollback manifestを残す。
- `.claude/settings.local.json`、managed policy、`allowManagedHooksOnly`、`disableAllHooks`により実効設定が変わる場合は診断し、登録済みと誤報しない。
- project fallbackは`${CLAUDE_PLUGIN_ROOT}`へ依存せず、installer/initがpreview付きで確認したrepo-local code symlink `.claude/dev-graph-plugin`を使う。link realpathはC24のplugin sourceと一致させ、PreToolUse C10を含む全eventをまとめて切り替える。
- `source=project`はdev-graphをClaude pluginとして有効化していないplain-symlink導入モードだけに許可する。initはeffective hooksを検査し、plugin hookが1件でも見える状態ではproject mergeを拒否する。`source=plugin`時はproject側dev-graph hookを除去/rollbackし、config値だけで排他化できたとみなさない。

## イベント契約

| Event | Matcher | 動作 | 判定権限 |
|---|---|---|---|
| `PreToolUse` | `Bash|Write|Edit|MultiEdit|NotebookEdit` | C10 `guard-graph-schema.py` が graph authority への直接書込み・bridge 迂回・content root の破壊操作を静的判定で遮断する (下節「遮断時間契約」)。Codex は `Bash` だけを登録する | 遮断時だけexit 2 |
| `SessionStart` | `startup|resume` | C24/C27でworktree contextとlease/pending eventを読取り、期限到来時はC03/C26 scheduled reconciliationを起動して短いcontextを返す | completion判定はC26 |
| `PostToolUse` | `Bash` | 成功済みtool inputをJSONとして検査し、`git pull`、`git merge`、`git push`、`gh pr merge`のときだけC26をasync起動 (beads repoでは`git push`もC26 reconciliation発火の対象。beads還流はC26の完了確定の下流)。他はno-op | asyncのためなし |
| `PostToolUse` | `Bash` | `audit-graph-authority-drift.py` が graph authority の digest/`graph_revision` を台帳と突合し、C10 が遮断できない経路による drift を事後検出する。同期実行 (confirmed 判定をagentへ返すため) | `confirmed` drift でexit 2 |
| `TaskCompleted` | matcherなし | task subject/descriptionに`[DG:<graph_node_id>]`がある場合だけC27 leaseを`pending_review`へparkする。PR merge前でも正常終了を許し、GitHub taskをdoneにしない | identity/owner不整合時だけexit 2 |

`Stop`は再入loopを作りやすいため使わない。PostToolUseはコマンド文字列をshellで再実行せず、許可した操作の観測トリガーとしてだけ扱う。

## security / idempotency

- commandは`${CLAUDE_PLUGIN_ROOT}`と`${CLAUDE_PROJECT_DIR}`だけを引用符付き固定command stringで渡す。stdin/tool commandをshellへ連結・再実行せず、script側でevent名・tool名・cwd・session/task identifier・長さを検証する。
- plugin root は read-only の共有 harness で、bytecode cache (`__pycache__`) も書かない。commandは`python3 -B`で起動し、hook が起こす子 script にも`-B`を渡す。plugin の module を import する script は、import の前に自分で`sys.dont_write_bytecode = True`を置く (呼出し側の`PYTHONDONTWRITEBYTECODE`には頼らない)。`tests/test_no_bytecode_in_harness.py`が静的と実起動の両方で確かめる。0.1.17 までの project fallback が書いた`python3 "…"`の配線は、`-B`の有無だけの違いなので init の再実行が同じ配線とみなし、書き換えない (hook script 自身の止め方で .pyc は書かれない)。
- C24がcaller root containment、C27がrepository/worktree identityを検証する。tool input、環境変数、gh outputのtoken/authorization値をlogへ出さない。
- event keyは`repository_id:event:session_id:tool_use_id:head_sha`。git common dir配下のdev-graph event ledgerとatomic lockで重複・再入を抑止する。
- async hookは状態判定を返さない。TaskCompletedは当該`graph_node_id`のlease transitionだけを行い、無関係なClaude taskは常にno-opとする。PR open検知後はC26/C27が`pending_merge`へ進め、merge後だけdurable doneへ進める。

## C10 PreToolUse の遮断時間契約

- graph authority (`.dev-graph/state/`、`.dev-graph/config.json`、`graph-node.schema.json`) への直接書込み、Beads/GitHub bridge 迂回、content root への破壊操作は `guard-graph-schema.py` の `static_denial` で判定する。遮断対象の判定経路では subprocess、graph 全件 schema 検査、network I/O を起動しない。
- repository context 検査は静的遮断を通過した入力にだけ実行する。PreToolUse timeout が「遮断すべき操作を許可する fail-open 窓」にならない順序を不変条件とする。
- shell redirect は quote 外の演算子とその宛先だけを評価する。遮断例を引用した notes 等の散文は redirect とみなさず、tokenize 不能な入力だけ安全側 fallback を使う。
- `.dev-graph/config.json` と初期 `.dev-graph/state/graph.json` の正規 writer は `scripts/build-init-scaffold.py` (project fallback の hook 配線は `scripts/build-project-hook-fallback.py`)。init は receipt を検証し、直接 Write/Edit/Bash redirect/`Path.write_text()` へ退避しない。node 登録後の graph 変更は C02 `scripts/build-graph-node.py` と `scripts/register-package.py` に限定する。
- シェル書込み先解析は `lib/guard_graph_commands.py` に分離し、hook entrypoint は input 正規化・静的遮断・context 検査の順序だけを所有する。判定部品は entry point ではないので `hooks/` に置かない (`tests/test_hooks_entry_point_contract.py`)。
- inline Python (`python -c` / heredoc) の書込み先解析は `lib/guard_python_writes.py`、副作用のない path 式評価は `lib/guard_python_path_eval.py` に分離する。Python は shell の command 位置にある場合だけ抽出し、環境変数代入・`env`・`bash -c` 内の heredoc は追跡する一方、`echo` / `cat` が文字として保持する Python 例は実行とみなさない。`ast` の定数伝播により、変数代入・`Path` の `/` 結合・`os.path.join`・f-string・`%` 書式・import 別名で字面が分断されていても、リテラル直書きと同じ境界で扱う。標準 library の mutation 関数は import 解決後の qualified name で判定し、同名のユーザー定義関数を巻き込まない。書込み判定は mode 文字列 (`open`) と整数 flag (`os.open` の `O_WRONLY`/`O_CREAT` 等) の双方を見る。`rename` / `replace` / `move` は元 path と宛先の双方を変更対象とする。`ast` は subprocess を起動しないため遮断時間契約を変えない。
- `getattr(x, '<リテラル>')` は `x.<リテラル>` へ畳んでから照合する。method 名を文字列へ逃がす形も path を変数へ逃がす形と同じ境界で扱う。`str()`/`os.fspath()`/`os.path.abspath` 等の identity 包みも透過する。
- path を要素へ分解する形 (`'/'.join(parts)`・`Path(*parts)`・`parts[0]`) は list/tuple リテラルを列として保持して畳む。区切りを定数属性で組む形 (`os.sep`)、親を参照する形 (`Path.parent`)、末尾を差し替える形 (`with_name`/`with_suffix`)、bytes 字面も同じ境界で扱う。
- 定数伝播には再帰の深さ上限がある。上限を超えて root が未解決になっても、末尾が `state/graph.json` の確定形なら fail-closed 側で遮断する。未解決 root の下の `config.json` は `.dev-graph/tmp/` の draft でありうるため通す (init の正規手順を巻き添えにしない)。
- 残る限界は `exec`/`eval` の source 内で path を組み立てる形、`replace` / slice / base64 等の任意文字列変換、別 script file の本文へ書込みを移す形。再帰的 source 解析や任意 file 読込みは所要時間を入力に依存させるため、遮断時間契約と両立しない。C02 atomic writer の使用規約と PostToolUse の authority drift 監査で補完する。
- 評価しきれない path 式は fail-closed とする。確定した prefix が `.dev-graph/` 配下から出ていない限り遮断し、`.dev-graph/tmp/`・`.dev-graph/cache/` のように保護外だと確定した prefix だけ通す。「解決できなかったので許可する」は fail-open として扱わない。

## C10 が遮断できない範囲と、それを埋める層

C10 の判定材料は PreToolUse に届くコマンド文字列だけである。遮断は「interpreter 起動 x 書込み
動詞 x authority path」の共起で成立するため、**書込みを別 script file へ移した間接起動
(`python3 tools/writer.py`、`bash tools/writer.sh`) はこの 3 条件がコマンド文字列上で 1 つも
成立せず、PreToolUse では原理的に遮断できない**。script の中身を読みに行けば遮断できるが、
それは C10 の遮断時間契約 (上節) を破り、PreToolUse timeout による fail-open 窓を再び開く。
遮断強度と遮断時間はトレードオフであり、ここでは遮断時間側を不変条件として保持する。

同様に閉じられないのは、実行時にしか値が定まらない書込み (argv・環境変数・関数戻り値)、
`exec`/`eval`、および外部プロセスへの委譲である。逆に、コマンド文字列の中で完結する変数経由
(`p = Path(...) / 'graph.json'; open(p, 'w')`) は C10 が変数を畳んで解決し遮断する。

| 層 | 実体 | 担当 | 閉じない範囲 |
|---|---|---|---|
| 遮断 | C10 `guard-graph-schema.py` (PreToolUse) | コマンド文字列で共起が読める直接書込み・変数経由書込み | script file 経由の間接起動、実行時決定値 |
| 事後検出 | `audit-graph-authority-drift.py` (PostToolUse) | 「内容が変わったのに `graph_revision` が進んでいない」= C02 writer では成立し得ない形 | revision を正しく +1 し envelope も canonical に保った迂回書込み |
| store検証 | C11 `validate-graph-schema.py` + `lib/graph_envelope.py` | canonical envelope (必須 3 key `schema_version`/`graph_revision`/`nodes` と任意の `repository_id`。未知 key は不可)、nodes[] の schema/DAG | envelope も node schema も満たす意味的改竄 |

- **`graph_revision` の +1 不変条件が事後検出の土台である**。C02 writer は 1 回の書込みにつき必ず
  `graph_revision` を +1 する。この不変条件を緩める変更は、事後検出層を同時に無効化する。
- 事後検出の判定は `confirmed` (正規 writer では成立し得ない形。exit 2) と `advisory`
  (正規運用でも起こり得る弱い痕跡。exit 0 + receipt) の 2 段とする。shell segment 全体が
  VCS 履歴移動または read-only git command だけの場合の revision 後退と
  「コマンド文字列に正規 writer 名が現れない」は advisory に留める。前者は履歴移動であり、後者は
  正規 writer を wrapper script から呼ぶ運用と区別できないためである。
- `git checkout main && python3 writer.py` のように非 git command が混在する場合は VCS 操作へ
  偽装できないよう confirmed のままとする。`git -c alias...`、command substitution、改行 command
  も任意 command 実行を含み得るため advisory 緩和へ入れない。
- 監査台帳は保護対象外の `.dev-graph/tmp/authority-audit.json` に置く。`state/` や `config.json`
  へ置くと監査自身の書込みが C10 の保護対象を叩く。
- 台帳は判定結果によらず毎回更新する。更新を止めると同じ drift を毎回報告し続け、是正済みか
  どうかが判別できなくなる。

**この 3 層はいずれも単独では閉じない。** 「C10 があるから graph authority は保護されている」は
成り立たず、正しくは「直接書込みは遮断され、間接書込みは形の痕跡として事後に現れる」である。
graph の意味的正しさは最終的にレビュー時の diff 確認に依存する。

## 公式仕様参照

- https://code.claude.com/docs/en/hooks
- https://code.claude.com/docs/en/hooks-guide
- https://code.claude.com/docs/en/configuration
- https://code.claude.com/docs/en/debug-your-config
