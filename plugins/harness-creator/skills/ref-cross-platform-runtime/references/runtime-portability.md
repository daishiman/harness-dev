# 単独 install / 配布ポータビリティの不変条件 (三層)

marketplace から **plugin 単独で install** / clone された先 (cwd 非依存・repo 構造非依存)
でも plugin 資産が壊れないための不変条件を **三層** に分けて定義する。各層は別レイヤーであり、
基準root・対象ファイル・機械担保が異なる。

| 層 | 対象ファイル | 壊れ方 | 機械担保 lint |
|---|---|---|---|
| **層0: marketplace / install** | Claude `marketplaces/local/.claude-plugin/marketplace.json` + Codex `.agents/plugins/marketplace.json` | 2製品で基準rootが違うのに同じcwd相対pathをCLIへ渡し、別directoryからpluginが見えない | `install-local-plugins.py --all --check` + installer pytest |
| **層1: runtime hook script (実行時 import)** | `plugin.json hooks[].command` の script | 単独 install で自 plugin 外を import-time 依存し raise → 全フックが exit≠0 で毎回クラッシュ | `scripts/lint-runtime-portability.py` + `scripts/lint-vendored-ssot.py` |
| **層2: README ドキュメント層 (導入者コピペ)** | `plugins/*/README.md` + `references/*-setup.md` 等 setup 手順の bash/sh フェンス | 導入者が素のターミナルへコピペ → `$CLAUDE_PLUGIN_ROOT` 空展開で先頭が `/lib/...` になり `No such file` | `scripts/lint-readme-plugin-root-portability.py` |

> **配布先は製品別に判定する**: harness-creator 自身は Claude 公開
> marketplace では `distribution.distributable:false` のままだが、Codex では
> `codex_distribution.distributable:true` として単独 install 対象である。したがって
> harness-creator 自身も plugin 境界外 symlink と install 位置依存を持たない。

---

## marketplace / install のcwd非依存性 (層0)

製品間で相対`source`の基準rootが異なる。manifestへmachine固有の絶対pathを保存せず、CLI登録時だけ
`install-local-plugins.py`が次のrootを絶対pathへ正規化する。

| 製品 | marketplace file | CLIへ渡すroot | 永続scope |
|---|---|---|---|
| Claude Code | `marketplaces/local/.claude-plugin/marketplace.json` | `<repo>/marketplaces/local` | user |
| Codex | `.agents/plugins/marketplace.json` | `<repo>` | user-global |

両catalogのentryはそれぞれのroot基準で`./plugins/<name>`を指す。helperはplugin集合の一致、
repo `plugins/` 内への閉包、両manifestの実在、install後のenabled状態、実行CLI identity、
manifest version、実在する絶対runtime path、artifact modeを検証する。
scriptは`__file__`からrepo rootを導出し、session cwdを入力にしない。

```bash
python3 /absolute/path/to/harness/plugins/harness-creator/scripts/install-local-plugins.py --all
cd /tmp
python3 /absolute/path/to/harness/plugins/harness-creator/scripts/install-local-plugins.py --all --check
```

## product別 plugin root 契約

- Claude Code側のSkill実行契約では`${CLAUDE_PLUGIN_ROOT}`をplugin rootとして使う。
- Codexが`${PLUGIN_ROOT}`と互換用`${CLAUDE_PLUGIN_ROOT}`を保証するのはplugin hook commandである。通常Skillのshell実行ではこれらのhost注入を前提にしない。
- Codex hookはsession cwdで実行されるため、hook内の`./scripts/x.py`は使用しない。
- 共通hook commandの正規形は`${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/x.py`とする。
- SKILL.mdまたは配下promptが同梱resourceをshell実行する場合、owner SKILLはfrontmatter
  `runtime_root_policy: host-skill-path`と`Runtime root contract`本文を持つ。Codexではホスト提示の
  absolute `SKILL.md` pathから`.codex-plugin/plugin.json`または`.claude-plugin/plugin.json`を持つ
  祖先を上方探索し、manifest `name`一致を確認したrootを各shell invocation内の論理`PLUGIN_ROOT`とする。
  cwd推測とliteral placeholderは禁止し、promptはowner Skill契約を継承する。実行script自身も
  `__file__`相対でrootを解決する。

---

## runtime hook の単独 install ポータビリティ (層1)

marketplace から **plugin 単独で install** された先 (cwd 非依存・repo 構造非依存) でも、
hook が import-time にクラッシュせず `exit 0` を維持するための不変条件と機構。

### 不変条件

runtime hook script (`plugins/*/.claude-plugin/plugin.json` の `hooks[]` に配線された
command script) は、**import-time (モジュールトップレベル) に自 plugin root 外のモジュールへ
依存して `raise` してはならない**。

理由: hook は Stop / Edit / Write / Skill 等で毎回 import-time 実行される。単独 install では
plugin 外 (repo-root `scripts/` 等) は存在しない。トップレベルで外部モジュールを動的 import
解決し、不在時に raise すると、その plugin の **全フックが import 時クラッシュ** (exit≠0) し、
ユーザの全 Edit/Write/Stop が壊れる ("exit は常に 0" のフック設計と矛盾)。

### 機構 (二層分離: 再現性は仕組みで担保)

1. **vendoring (実体コピー)**: 必須共有モジュールは正本 (repo-root `scripts/`) から各 plugin の
   `scripts/` へ **byte 完全一致の実体ファイル**でコピーする。symlink は plugin 境界を越えるため
   単独 install (tar 展開) で dangling する。正本は repo-root のまま、plugin 内コピーは移植性ミラー。
   - 例: `scripts/feedback_contract_ssot.py` → `plugins/harness-creator/scripts/feedback_contract_ssot.py`
   - 例: `plugins/harness-creator/scripts/notion_config.py` → `plugins/skill-intake/scripts/notion_config.py`

2. **fail-soft ローダ**: 共有モジュールの解決は次の優先順で行い **絶対に raise しない**。
   - (a) env `PLUGIN_ROOT/scripts/<module>.py`、次に`CLAUDE_PLUGIN_ROOT/scripts/<module>.py`
     (Codexは両方、Claude Codeは後者をhook実行時に設定)
   - (b) `Path(__file__).parents` の上方探索 (vendored plugin 内コピーを dev/install 双方で発見)
   - (c) 全滅時は **最小 fallback オブジェクトを return** (consumer が実際に使う述語のみ保守的値で提供)。
     vendored コピーが常在するため fallback は実質 dead code (多層防御の最終安全弁)。

3. **queue / 副作用の書込先安全化**: git repo 解決に失敗したとき (git 外 / 単独 install) に
   `os.getcwd()` へ fallback して **無関係なユーザ cwd を汚染しない**。`CLAUDE_PLUGIN_ROOT`
   配下 (self-relative) へ固定するか、書込不能なら silent skip (exit 0 維持・append-only 副作用境界と整合)。

### 機械担保 (lint / CI / byte 一致)

| lint | 検証内容 |
|---|---|
| `scripts/lint-vendored-ssot.py` | vendored コピー = 正本 の byte 一致 (drift で fail-closed)。symlink 回帰も検出。 |
| `scripts/lint-runtime-portability.py` | hook script が import-time に自 plugin 外を fail-closed 依存 (raise) しないことを AST 静的検査。 |

両 lint は Makefile (`make lint` / `make test`) と CI (`harness-creator-kit-ci.yml`) に配線済み。
回帰 pytest (`tests/scripts-root/test_root__lint_runtime_portability.py` /
`tests/scripts-root/test_root__lint_vendored_ssot.py`) が修正前パターンの FAIL / 修正後の PASS を固定する。

### 検証手順 (単独 install 再現)

plugin ディレクトリのみを repo 外 temp へコピーし (vendored 実体を含める)、空 env で hook を実行し
`exit=0` / Traceback 無しを確認する。

```
cp -R plugins/harness-creator /tmp/standalone/harness-creator
cd /tmp/standalone   # git 外・CLAUDE_PLUGIN_ROOT 未設定
echo '{}' | python3 /tmp/standalone/harness-creator/skills/run-elegant-review/scripts/check-review-trigger.py
echo exit=$?   # => exit=0
```

---

## README ドキュメント層のポータビリティ (層2)

marketplace から install した導入者が README のセットアップ/疎通確認コマンドを
**素のターミナルへコピペ**しても壊れないための不変条件と機構。層1 (実行時 import) とは
別レイヤーで、対象は「導入者がコピペするコマンド例」である。

### 不変条件

配布 plugin の導入者向け文書 (README + `references/*-setup.md` 等の setup 手順) の
bash / sh コードフェンス (= 導入者が素のターミナルへコピペしうるコマンド) に、次を
**一次手順として書いてはならない**:

- fallback 無しの裸 `$CLAUDE_PLUGIN_ROOT/...`
- repo 相対直書き `python3 plugins/<name>/...`
- Python の `os.environ["CLAUDE_PLUGIN_ROOT"]` (未定義時 KeyError を誘発)

**理由**: `$CLAUDE_PLUGIN_ROOT` は Claude Code 実行環境でのみ注入される変数である。導入者が
素のターミナルへコピペすると空文字へ展開し、パス先頭が `/lib/...` になって
`can't open file '/lib/...'` で壊れる。repo 相対
`python3 plugins/<name>/...` も marketplace install 先の作業フォルダに `plugins/` が無く壊れる。

### 機構 (二層分離: 再現性は仕組みで担保)

1. **doctor スクリプト同梱 + README チャット委譲 (一次導線)**: セットアップ疎通確認は
   install 位置を `__file__` 相対で自己解決する **doctor スクリプト**を同梱し、README の疎通確認は
   **チャット委譲** (`/<name>-doctor` スラッシュコマンド or 自然文「セットアップを確認して」) を
   一次導線にする。Claude が install 位置を解決して実行するため生変数を露出しない。
   - doctor は install 位置を `os.path.dirname(os.path.abspath(__file__))` で自己解決し、
     plugin root環境変数に一切依存しない (生ターミナルで実行しても壊れない)。

2. **生パスは開発者補足へ降格 + fallback 形**: 生パスの直叩き例は「開発者向け (clone 直叩き)
   補足」へ降格し、**fallback 形 `${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-plugins/<name>}}`** で書く
   (両方未定義なら repo 直下相対へ落ちるので clone 開発者でも素のターミナルで同一挙動)。
   Python は `os.environ.get("PLUGIN_ROOT") or os.environ.get("CLAUDE_PLUGIN_ROOT") or
   "plugins/<name>"` を使う。

3. **doctor の設計原則**: 秘密 (鍵・トークン) は本体を出さず **マスク表示** のみ・
   **WARN-not-FAIL** (個別失敗は WARN に集約し doctor 全体は exit 0。診断でありゲートでない =
   brew doctor の教訓)・外部 API は **GET 専用** (参照専用ガードと整合・書き込みしない)・
   既存 lib を **import 再利用** しロジックを複製しない。

### 実装パターン

- doctor実装はinstall位置を`__file__`から自己解決し、鍵をマスクし、診断失敗をWARNへ集約する。
- READMEはチャット委譲を一次導線にし、生パスの直叩きはclone開発者向け補足へ降格する。
- 既存libをimportして再利用し、診断用に本体ロジックを複製しない。

### 機械担保 (lint / CI)

| lint | 検証内容 |
|---|---|
| `scripts/lint-readme-plugin-root-portability.py` | 配布 plugin (`distributable != false`) の**ユーザー向け文書** (README + `references/*-setup.md` / `skills/*/references/*setup*.md`) の bash/sh (及び python) コードフェンスに、一次手順の裸 `$CLAUDE_PLUGIN_ROOT/...` / repo 相対直書き `python3 plugins/<name>/...` / `os.environ["CLAUDE_PLUGIN_ROOT"]` 添字が無いことを **fail-closed** で静的検査。番号付きリスト内の 0-3 スペース字下げフェンス (CommonMark) も走査する。fallback 形 `${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-plugins/<name>}}` と、同一フェンス内に開発者補足注記 (「開発者」/「clone」を含む) を添えた裸変数は許可。`distributable: false` の plugin と `*setup*.md` 命名でない reference (LLM/開発者向け仕様) は対象外。 |

Makefile (`make lint` の `readme-portability` ターゲット) と CI (`harness-creator-kit-ci.yml`) に配線済み。
新規 plugin の README / setup 手順も `plugins/*/README.md`・`plugins/*/references/*setup*.md`・
`plugins/*/skills/*/references/*setup*.md` の glob で自動的に検査対象へ入る (被覆漏れなし)。

### 検証手順 (生ターミナル空展開の再現)

配布 plugin の README bash フェンスを空 env でコピペ実行し、`$CLAUDE_PLUGIN_ROOT` 未定義でも
先頭が `/lib/...` にならない (fallback で repo 直下相対へ落ちる) ことを確認する。

```
env -u PLUGIN_ROOT -u CLAUDE_PLUGIN_ROOT bash -c 'echo "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-plugins/<name>}}/lib/x.py"'
# => plugins/<name>/lib/x.py  (裸 $CLAUDE_PLUGIN_ROOT/... なら先頭が /lib/x.py になり壊れる)
```
