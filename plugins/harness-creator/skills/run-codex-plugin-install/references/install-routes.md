# install routeごとの詳細

`SKILL.md` の2つのinstall routeで、helperが実際に行う処理・receipt・exit codeをまとめる。
どちらのrouteもCLIの `--json` 出力の実測を正とし、exit 0だけで成功としない。

## installの範囲 (対象plugin集合)

- 対象plugin集合は、指定したpluginと、その依存closure (`dependency_closure`) である。closureは各pluginの
  `references/package-contract.json` の `depends_on` を、同じmarketplace/sourceの中で推移的にたどって求める
  (fileが無いpluginは依存なし)。どちらのhelperもこの集合を依存の順 (`install_order`) で入れる。
  `--all` ではcatalogの全pluginが対象になる。
- closureを読む場所: local全件routeは `<repo>/plugins/<name>/references/package-contract.json`、
  単一local routeは `<source>/.agents/plugins/marketplace.json` の各entryの `source.path` の下。
  どちらも読むだけでinstall前に求まる。`--check` は未installのpluginをexit 3で落とすので、closureの下見には使わない。
- previewとguardの `<TARGET_SCOPE>` には対象plugin集合の全名・source/ref・platformを書き、
  `<SIDE_EFFECT_SUMMARY>` にはmarketplace登録と各pluginのinstallで変わるuser-global marketplace/cache/configを書く。
- 実行の後、receiptの `install_order` が承認した集合と同じことを確かめる。違えば成功にせず、
  承認していないpluginの名前をユーザーに伝える。uninstallは別のuser-global変更なので、ユーザーが決める。
- 単一local/Git routeでは、承認した集合を `--approved-plugin <name>` (集合の名前ごとに繰り返す) でhelperにも渡す。
  helperは `plugin add` の前に入れる集合と照合し、違えば1件も入れずにexit 3で止まる。事後の照合は
  この照合の確かめ直しで、承認していないpluginが入るのを防ぐ役はhelperの事前照合が担う。
- Git sourceはsnapshotがmarketplace登録の後にしか無いので、下の「Git sourceの2段の承認」で入れる。

## local全件route (`scripts/install-local-plugins.py`)

- 引数: `--repo-root <source>` (絶対path)、`--all` か `--plugin <name>` (複数指定可) のどちらか1つ、
  任意の `--platform claude|codex|both` (既定 `both`)、read-onlyにする `--check`。
  隔離した環境で試すときだけ `--claude-config-dir` / `--codex-home` を渡す。
- 登録するmarketplace root: Claude側は `<repo>/marketplaces/local`、Codex側は `<repo>` を、
  それぞれ別の絶対marketplace rootとして登録する。`--platform` に関係なく両方のcatalogを先に読み、
  読めなければCLI状態を変えずにexit 3で止まる。
- installの範囲: 上の対象plugin集合を依存の順 (`install_order`) で入れる。reportの
  `selected_plugins` が指定した名前、`dependency_closure` が依存で加わった名前になる。
- `--check`: CLI状態を変えずに、installと同じ選択引数の対象を検証する。repository外cwdから回し、
  `status=verified` を確認する。
- statusとexit code:

| status | exit | 意味 |
|---|---|---|
| `installed` | 0 | installを実行し、全対象をCLI実測で確認した |
| `verified` | 0 | `--check` で全対象をCLI実測で確認した |
| `pending_user_gate` | 1 | CLI実測が成功条件を満たしていない。成功として扱わない |
| `stale_runtime` | 1 | versionが同じままsourceの中身が変わり、cacheに古いcopyが残っている。`scripts/build-plugin-release.py` でversionを上げてから入れ直す |
| `invalid` | 3 | 選択引数・catalog・CLI・artifactの契約違反 |

- reportの `hook_trust` は常に `user-review-required`。`next_action` はhookの確認と、
  新しいClaude Code/Codex sessionの開始を求める。

## 単一local/Git route (`scripts/install-codex-plugin.py`)

- 引数: `--source` と `--plugin` は必須、`--ref` はGit sourceだけ、承認した集合を渡す `--approved-plugin`
  (繰り返し可)、隔離時だけ `--codex-home`。`--check` は無い。`--approved-plugin` を渡したGit sourceは、
  `--ref` が40桁のcommit SHAでなければCLIを呼ぶ前にexit 3で止まる。`--source`・`--plugin`・`--ref`・
  `--codex-home` は1回だけ渡す。2回渡すと後の値で黙って上書きせず、空の `--codex-home` と同じく
  argparseがexit 2で止める。40桁のSHAは小文字にそろえ、Codexへの引数・照合・receiptの `ref` で同じ綴りを使う。
- 処理の順:
  1. local sourceは、catalogから対象plugin集合を求め、`--approved-plugin` があればここで照合する (CLIを変える前)。
  2. `codex plugin marketplace add <source> [--ref <ref>] --json` が返す `marketplaceName` を
     marketplace名とする。入力名から推測しない。
  3. Git sourceが登録済み (`alreadyAdded`) なら `codex plugin marketplace upgrade` でsnapshotを更新する。
     ただし `--ref` がcommit SHAで、snapshotがもうそのcommitにあれば、upgradeしない。
  4. Git sourceは、snapshot rootの実際のcommit (`.codex-marketplace-install.json` の `revision` と、
     snapshot rootがcheckoutなら `git rev-parse HEAD`) を読む。2つが食い違う、`revision` が文字列でないなど
     証拠が壊れている、または `--ref` のcommit SHAと違えば、pluginを1件も入れずにexit 3で止まる。
     snapshot rootがcheckoutでgitが答えられれば、commit SHAに固定したcheckoutに未commitの変更 (untrackedを
     含む。Codexが書く install metadata は除く) があっても止まる。commitが同じでも中身が違いうるからである。
     gitが答えられない (`git status` が失敗する) と `revision_evidence.git_dirty` が `null` になり、helperは
     止まらない。snapshot rootがcheckoutでない、またはgitを使えないときは `git_head` と `git_dirty` が
     どちらも `null` で、commitはinstall metadataの `revision` だけで確かめている。この2つはskillの側で扱う
     (SKILL.mdの完了チェックリストと失敗時)。gitは `--no-optional-locks` で読むだけにし、
     利用者の `.git/index` を書き直さない。続けてsnapshotのcatalogから対象plugin集合を求め、
     `--approved-plugin` があれば照合する。
  5. `codex plugin list --json` を読んでから、対象plugin集合を `install_order` の順に
     `codex plugin add <plugin>@<marketplace> --json` で入れる。
  6. Git sourceはsnapshotのcommitを読み直し、addの前と違えば止まる (`revision_evidence.rechecked_after_plugin_add`)。
     続けて `codex plugin list --json` でinstalled/enabledを確かめ直す。addの前のlistに無く、対象plugin集合にも
     無いpluginが現れたら止まる (`unexpected_plugins`)。各pluginのsourceとruntimeの中身のdigestを比べる。
- catalogのmarketplace名と登録されたmarketplace名が違えば、installへ進まずexit 3で止まる。
- receiptの主なfield: `status` / `verified` / `verification_status` / `phase` / `added_plugins` / `source_type` /
  `source` / `marketplace_root` / `ref` / `resolved_revision` / `revision_evidence` / `approved_plugins` /
  `marketplace` / `plugin_id` / `runtime_path` / `enabled` / `hook_trust`。`ref` は引数を写した値で、snapshotの
  実際のcommitは `resolved_revision` (読めなければ `null`) にある。top-levelの `plugin_id` などは要求した
  pluginのもので、依存が循環していても変わらない。`verified` と `verification_status` は全対象の集計で、
  依存のpluginが1件でも未検証なら `verified=false` になる。
- statusとexit code:

| status | exit | 意味 |
|---|---|---|
| `installed` | 0 | 全対象をCLI実測で確認し、runtimeの中身がsourceと同じ |
| `pending_user_gate` | 1 | 同じhook digestの多重activationなどで未検証。成功として扱わない (同名でhookが違う多重activationはここに来ない。下の「同名多重activation」) |
| `stale_runtime` | 1 | versionが同じまま、runtimeの中身がsourceと違う。`scripts/build-plugin-release.py` でversionを上げてから入れ直す |
| (argparseの誤り) | 2 | 必須引数の欠け、1回だけの引数の重複、空の `--codex-home` |
| `invalid` | 3 | 引数の組み合わせ・source・CLI・artifactの契約違反 |

- 止まったとき (exit 3) のreceiptは `status=invalid` と `error` に加えて、`phase` (`preflight` → `marketplace` →
  `snapshot-check` → `plugin-add` → `post-install-verify` のどこで止まったか) と `added_plugins`
  (`plugin add` がexit 0でJSONを返し、helperがそれを読めたplugin id) を載せる。`added_plugins` が空で
  `failed_plugin` も無ければ、helperは `plugin add` を1件も出していない。`added_plugins` のpluginは入ったまま
  残る。addの途中で止まった (非0・非JSON) pluginは `failed_plugin` に載る。CLIが途中まで書いたかはhelperには
  分からないので、そのpluginが入ったかは `codex plugin list --json` で確かめる。対象の外で現れたpluginは
  `unexpected_plugins` に載る。登録まで進んでいれば `marketplace` に、snapshotを読んでいれば
  `resolved_revision` に値が入る。
- 検証はreceiptと `codex plugin list --json` の照合で行う。`next_action` はcurrent hookを確かめて
  trustした後、新しいthreadを始めることを求める。

### Git sourceの2段の承認

helperはmarketplace登録の後にsnapshotからclosureを求める。helperを1回のguardで通すと、承認の時点で
closureが分からない。そこでguardを2段に分け、1段めで登録したsnapshotからclosureを求めて、2段めで承認する。

2段めの承認と実際に入る集合が一致することは、Codex CLIの振る舞いに頼らない。2段めのhelperは登録済みの
marketplaceに対してupgradeを出しうる。固定したSHAのsnapshotをupgradeが動かさないことは、CLIの文書でも
確かめていない。そのためhelperは、`plugin add` の前に次の2つを実物で確かめ、どちらかが崩れれば1件も入れずに止まる。

- snapshotの実際のcommitが、固定したSHAと同じである (上の処理の順の4)。
- snapshotのcatalogから求めた対象plugin集合が、`--approved-plugin` で渡した集合と同じである。

止まったとき、upgradeがsnapshotを別のcommitへ動かしたまま残っていることがある。これはmarketplaceの
snapshot cacheの変更で、2段めの `<SIDE_EFFECT_SUMMARY>` に含める。receiptにupgradeを出したかの印は無いので、
止まったことと、`resolved_revision` の有無と値 (固定したSHAとの差) をユーザーに伝え、登録を残すか消すかは
ユーザーが決める。この2つの照合はどちらも `plugin add` の前なので、receiptの `added_plugins` は空で
`failed_plugin` も無い。addの後の照合 (snapshotの読み直し、対象の外のplugin) で止まったときは、
`added_plugins` のpluginが入ったまま残る。snapshotの読み直しは全件のaddの後に1回だけなので、addとaddの
間にsnapshotが動いたときも、検出は事後になる。

下の手順の1〜2はmanifestの `preflight` (読むだけ)、3〜4と5.の2段めのpreviewは `register-marketplace`、
5.の承認とhelperの実行は `install`、6.は `install` のgateと `verify` にあたる。3.の後、helperを呼ぶ前に止まる
(revisionが固定したSHAでない・closureが求まらない・ユーザーが5.の2段めを承認しない) と、pluginは1件も
入っていないが、1段めで登録したmarketplace
(user-global marketplace configとsnapshot cache) は残る。登録が残ることと、snapshotの `revision` と、
止まった理由をhandoffで伝え、登録を残すか消すかはユーザーが決める。

1. refをcommit SHAに固定する: `--ref` が40桁のcommit SHAでなければ (branch・tag・省略)、mutationの前に止め、
   そのrefが指すcommit SHAをユーザーに確かめてもらう。helperも、`--approved-plugin` を渡したGit sourceで
   SHAでない `--ref` を受け取ると、CLIを呼ぶ前にexit 3で止まる。
2. 登録済みか確かめる (読むだけ): `codex plugin marketplace list --json` で同じsourceのmarketplaceを探し、
   snapshot rootの `.codex-marketplace-install.json` を読む。`ref_name` と `revision` がどちらも固定したSHAなら
   3.を省く。別のrefで登録済みなら、helperのupgradeがsnapshotを動かしうるので止めてユーザーに確かめる。
3. 1段めのguard: argvは `codex plugin marketplace add <source> --ref <commit-sha> --json` だけにする。
   `<TARGET_SCOPE>` にはmarketplace登録だけでpluginは入れないこと、`<SIDE_EFFECT_SUMMARY>` には
   user-global marketplace configとsnapshot cacheの追加を書く。
4. closureを求める (読むだけ): `codex plugin marketplace list --json` のsnapshot rootで `revision` が
   固定したSHAであることを確かめ、`.agents/plugins/marketplace.json` の各entryの `source.path` の下の
   `references/package-contract.json` から対象plugin集合を求める。
5. 2段めのguard: argvはhelper (`install-codex-plugin.py --source <source> --ref <commit-sha> --plugin <plugin>`
   に、4.で求めた集合の名前ごとの `--approved-plugin <name>` を足したもの)。`<TARGET_SCOPE>` に対象plugin集合の
   全名を、`<SIDE_EFFECT_SUMMARY>` にsnapshotのupgradeと各pluginのinstallを書き、ユーザーが承認してから実行する。
   承認した集合がargvに入るので、guardが実行するargvとhelperの事前照合の基準は同じものになる。
6. 実行の後: receiptの `resolved_revision` が固定したSHAで、`revision_evidence.rechecked_after_plugin_add` が
   `true`、`revision_evidence.git_head` があれば `git_dirty` が `false`、`approved_plugins` と `install_order` が
   2段めで承認した集合と同じことを確かめる。`ref` は引数を写した値なので、この照合には使わない。

## 同名多重activation (両route共通)

どちらのhelperも、各pluginのreceiptに `activation_collisions` (CLI listで同じplugin名を持つ候補。1件だけなら空) と
`same_hook_multiple_activation` を載せる。単一local/Git routeは `artifacts[]`、local全件routeは `plugins[]` の
各要素にある。helperが `verified` を落とすのは、enabledな候補のhook digestが同じときだけである。同名のpluginが
別のmarketplace (Claude側は別のscopeも) でもenabledなら、hookが違っても無くても、helperはexit 0・`installed`・
`verified=true` を返し、`activation_collisions` に候補が載るだけになる。skillは、`activation_collisions` に
`enabled=true` の候補が2つ以上あれば成功にせず、候補の `plugin_id`・`marketplace`・`enabled` をユーザーに
伝える。どれを無効にするかはユーザーが決める (対象の外のpluginのdisableは、このskillの範囲の外である)。
