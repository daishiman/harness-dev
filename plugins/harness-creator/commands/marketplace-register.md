---
description: harness の plugin を Claude Code または Codex へ登録する手順を、ローカル clone 指定と GitHub ref 指定の 2 パターンで案内する。
argument-hint: "[local|github]  省略時は両方を提示"
allowed-tools: Read, Bash
name: marketplace-register
kind: command
version: 0.1.0
owner: team-platform
since: 2026-08-11
---

# /marketplace-register

`$ARGUMENTS` (`local` / `github` / 空) に応じて、harness の plugin を Claude Code へ
marketplace 登録する手順を提示する。

## Codex: harness-creator の登録

Codex では Claude marketplace と独立した root
`.agents/plugins/marketplace.json` (name: `harness-dev`) を使う。

```bash
# ローカル clone
python3 plugins/harness-creator/scripts/install-codex-plugin.py \
  --source /absolute/path/to/harness --plugin harness-creator

# GitHub の merge 済み main
python3 plugins/harness-creator/scripts/install-codex-plugin.py \
  --source daishiman/harness-dev --ref main --plugin harness-creator
```

更新時も同じhelperを再実行し、新規threadで確認する。helperはGit sourceが既登録なら
marketplace snapshotをupgradeし、install後にlist receiptを検証する。hook trustは
`/hooks`またはPlugins画面でユーザーが確認する。生成した他pluginをCodex対応する場合は
`run-codex-plugin-package`、明示installは`run-codex-plugin-install`を使う。

## 前提: Claude marketplace は 2 枚ある

| | ファイル | 載る plugin | 登録の入力値 |
|---|---|---|---|
| 公開 | `.claude-plugin/marketplace.json` (name: `skills`) | `distributable` が false でないもの | `daishiman/harness-dev` |
| ローカル | `marketplaces/local/.claude-plugin/marketplace.json` (name: `harness-local`) | **全 plugin** (非配布を含む) | `<harness-root>/marketplaces/local` |

分かれている理由は `scripts/build-local-marketplace.py` の docstring が正本。要点は
**公開側は `distributable: false` の plugin を載せられない** (`validate-plugin-completeness.py`
の MK-004 逆ガードと `NEVER_DISTRIBUTE` denylist が二層で拒否する) こと。
`harness-creator` / `slide-report-generator` / `ubm-goal-setting` などはここに該当するため、
**手元で使うにはローカル経路が必須**。

### source 形式の制約 (踏み抜きやすい)

`plugins[].source` の文字列形式は **marketplace ルート配下を指す `./` 相対パス**しか
受け付けない。`../` で親へ遡ると次で拒否される。

```
Failed to install: This plugin's marketplace entry is invalid: source: Invalid input
```

そのためローカル marketplace は `marketplaces/local/plugins -> ../../plugins` の相対
symlink を持ち、`source` を `./plugins/<name>` にしている (公式カタログと同形)。
symlink は生成物と一組で、`--check` が両方を検査する。

**source がローカル実体を指していても、install は copy である。** 2026-08-11 実測:
`~/.claude/plugins/cache/harness-local/<name>/<version>/` に 539 個の実ファイルが
置かれ symlink は 0 件、`installed_plugins.json` に `gitCommitSha` が固定される。
したがって **harness 側の編集は再取得するまで反映されない**。更新手順は後述。

## Claude パターン A: ローカル clone を登録する (非配布 plugin を使う場合)

1. 生成物が最新か確認し、古ければ再生成する。

   ```bash
   python3 ${HARNESS_ROOT:-.}/scripts/build-local-marketplace.py --check \
     || python3 ${HARNESS_ROOT:-.}/scripts/build-local-marketplace.py
   ```

2. Claude Code で `/plugins` → **Add Marketplace** を開き、harness の
   `marketplaces/local` の**絶対パス**を入力する。値は次で得られる。

   ```bash
   python3 -c "import pathlib,os; print(pathlib.Path(os.environ.get('HARNESS_ROOT','.')).resolve() / 'marketplaces' / 'local')"
   ```

3. `/plugin install <name>@harness-local` で導入する。
   `<name>` は `marketplaces/local/.claude-plugin/marketplace.json` の `plugins[].name`。

### 更新の流れ (harness 側を直したあと)

install はキャッシュへの copy で、キャッシュのディレクトリ名が **version** である
(`cache/harness-local/harness-creator/1.3.0-codex.20260713-1/`。`+` は `-` へ潰れる)。
よって version を据え置いたまま中身だけ直しても、Claude Code から見れば「同じ版」で
あり取り直す理由が無い。ここを人手で管理すると必ず上げ忘れるので自動化してある。

```bash
python3 ${HARNESS_ROOT:-.}/scripts/build-plugin-release.py --install \
  --project-dir /path/to/your/project
```

`--only <name>` を付けなければ**内容が変わった全 plugin** が対象になり、その
`plugins/<name>/.claude-plugin/plugin.json` が in-place で書き換わる。1 つだけ上げたい
ときは `--only` で絞ること。書込先は plugin manifest のほか
`marketplaces/local/`・`.claude-plugin/marketplace.json`・`.codex-plugin/plugin.json`
(持つ plugin のみ)・`config-version-lock.json` に及ぶ。まず `--dry-run` で対象を見るのが安全。

これが一度に行うこと:

1. 内容 hash を `marketplaces/local/plugin-fingerprints.json` と突き合わせ、変わった
   plugin を検出する (git commit ではなく作業ツリーの内容が基準。install が見ているのが
   作業ツリー実体だから)。
2. 変わった plugin の `version` を patch 採番する。build metadata は捨てる。
3. ローカル marketplace を再生成する。
4. `claude plugin marketplace update harness-local` → `claude plugin update
   <name>@harness-local --scope project` を駆動する。

反映後は **Claude Code の再起動が要る** (CLI が `Restart to apply changes.` と出す)。

`--check` は無書込で「version 上げ忘れ」だけを報告し、あれば exit 1。CI
(`run-ci-checks.sh`) と `run-skill-create` の step 3.7 に組み込んであるので、
新 plugin の記録漏れ・既存 plugin の上げ忘れは自動で止まる。

major/minor を上げたいときは `plugin.json` を手で編集すればよい。script は
「内容が変わった」しか知らず破壊的変更を判定できないため、手動採番があればそれを
尊重して対応表の更新だけを行う。

#### symlink projection は使わない

`.claude/{agents,skills,commands}` へ実体を張る方式は 2026-08-11 に廃止した。
実体参照なので編集は即反映されるが、代償が大きい:

- `env.CLAUDE_PLUGIN_ROOT` を 1 値しか持てず、他 plugin を独自 env (`HC_ROOT` /
  `SRG_ROOT`) で迂回し、plugin 側コードにもフォールバック分岐が必要になる。
- plugin の `hooks.json` を運べない。実際に SRG の PostToolUse hook を
  `settings.json` へ絶対パスで手動移植する必要があった。
- skill/command が増減するたび symlink を張り直す必要がある。

install 経路なら Claude Code が plugin ごとに `CLAUDE_PLUGIN_ROOT` を与え、
`hooks.json` も自動で効く。上の自動採番があれば「即反映されない」という唯一の
弱点も消えるため、install へ一本化してある。

### 反映されないときの切り分け

| 症状 | 原因 | 対処 |
|---|---|---|
| `source: Invalid input` で install 失敗 | `source` が marketplace ルート外を指している | `plugins` symlink が消えていないか `--check`。再生成で復旧する |
| `Component summary not available for remote plugin` | Claude Code が source をローカルと解釈できていない | 同上。`source` が `./plugins/<name>` 形式か確認 |
| 新しく作った plugin が Discover に出ない | 生成物が古い | `--check` が DRIFT を返すはず。再生成する (`run-skill-create` 経由なら workflow step 3.6 が自動実行するので、手で `plugins/<name>/` を作った場合に起きる) |
| 再生成したのに出ない | Claude Code 側のキャッシュ | `/plugins` → Marketplaces で該当 marketplace を update。効かなければ一度削除して Add し直す |
| harness 側を直したのに挙動が変わらない | install は copy であり、version が同じ間は取り直されない | `build-plugin-release.py --install`。Claude Code の再起動も要る |
| `Plugin "<name>" not found` | `claude plugin update` は `<name>@<marketplace>` 形式を要求する | `claude plugin update <name>@harness-local --scope project` |
| `--scope project` なのに対象が見つからない | project scope は **cwd の project** を見る (project dir を渡す option が無い) | 対象 project へ cd するか `build-plugin-release.py --project-dir` を使う |

**marketplace.json を修正した後は、既に登録済みでも Claude Code 側の再読込が要る。**
登録状態は `~/.claude/plugins/known_marketplaces.json`、パース結果は
`~/.claude/plugins/plugin-catalog-cache.json` で確認できる。

## Claude パターン B: GitHub から登録する (配布可 plugin のみ)

1. 公開 marketplace が最新か確認する。

   ```bash
   python3 ${HARNESS_ROOT:-.}/scripts/validate-plugin-completeness.py
   ```

2. `/plugins` → **Add Marketplace** に次のいずれかを入力する。

   - `daishiman/harness-dev` (owner/repo 形式)
   - `git@github.com:daishiman/harness-dev.git` (SSH 形式・private repo の場合)

3. `/plugin install <name>@skills` で導入する。

この経路では `distributable: false` の 8 plugin は**出てこない**。これは仕様である。

公開へ回せるのはそのうち 5 つだけで、`harness-creator` / `prompt-creator` /
`plugin-dev-planner` の 3 つは `validate-plugin-completeness.py` の
`NEVER_DISTRIBUTE` 固有名 denylist に載っており、`distribution.distributable` を true
にしても

```
<name>: internal-only plugin must explicitly declare "distributable": false but got
distributable=True (NEVER-DISTRIBUTE)
```

で hard error になる。フラグが true へ漂流しても再配布を止めるための多層防御なので、
この 3 つは **Claude ではローカル経路 (パターン A) でのみ使う**。
`harness-creator` の Codex 配布は冒頭の `.agents` marketplace 経路で独立して行う。

残る 5 つを公開したい場合は `references/package-contract.json` の
`distribution.distributable` を true にしたうえで、README の絶対パス依存
(`lint-readme-plugin-root-portability.py` が非配布 plugin では skip している) を
解消する必要がある。

## 注意: marketplace 名の衝突

`daishiman/HarnessHub` も marketplace 名 `skills` を名乗っている。両方を Add Marketplace
すると `<plugin>@skills` の exact identity が曖昧になる。同時登録する場合はどちらかの
`name` を改名すること。ローカル側 (`harness-local`) は最初から別名なので衝突しない。
