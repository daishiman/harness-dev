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

`$ARGUMENTS` (`local` / `github` / 空) に応じて、Claude Code / Codex へ
marketplace 登録・install する手順を提示する。案内だけでは実行せず、導入依頼がある場合に
`run-codex-plugin-install` へ渡す。

## ローカル clone: 両製品へ全 plugin を導入する

共通入口は `install-local-plugins.py`。絶対 script path を使えば cwd に依存せず、
Claude Code の user scope と Codex の user-global registry へ全件を導入できる。

```bash
python3 /absolute/path/to/harness/plugins/harness-creator/scripts/install-local-plugins.py --all --platform both

# install 状態を変更せず、別 cwd からも receipt を検証する
python3 /absolute/path/to/harness/plugins/harness-creator/scripts/install-local-plugins.py --all --platform both --check
```

単独指定は `--all` を `--plugin <name>` に置き換える。導入先を限定する場合は
`--platform claude` / `--platform codex` を使う。manifest と両製品の repository catalog は
維持したまま、実導入する製品だけを選ぶ。hook trust は `/hooks` または Plugins 画面で
ユーザーが確認し、反映後は新しいセッションで使う。

## Codex: Git ref から単独導入する

Codex は repository root の `.agents/plugins/marketplace.json` (name: `harness-dev`) を使う。
merge 済み ref からの導入は既存の単独 helper が担う。

```bash
python3 /absolute/path/to/harness/plugins/harness-creator/scripts/install-codex-plugin.py \
  --source daishiman/harness-dev --ref main --plugin <name>
```

更新時も同じ helper を再実行する。既登録の Git source は marketplace snapshot を更新し、
install 後に receipt を検証する。package の投影・検査は `run-codex-plugin-package`、
導入・検証は `run-codex-plugin-install` に責務を分ける。

## 前提: Claude marketplace は 2 枚ある

| | ファイル | 載る plugin | 登録の入力値 |
|---|---|---|---|
| 公開 | `.claude-plugin/marketplace.json` (name: `skills`) | `distributable` が false でないもの | `daishiman/harness-dev` |
| ローカル | `marketplaces/local/.claude-plugin/marketplace.json` (name: `harness-local`) | **全 plugin** (非配布を含む) | `<harness-root>/marketplaces/local` |

分かれている理由は `scripts/build-local-marketplace.py` の docstring が正本。要点は
**公開側は `distributable: false` の plugin を載せられない** (`validate-plugin-completeness.py`
の MK-004 逆ガードと `NEVER_DISTRIBUTE` denylist が二層で拒否する) こと。
非配布 plugin もローカル catalog には登録され、両製品へ導入できる。公開可否の正本は
各 plugin の `references/package-contract.json` と上記 validator、実際の掲載範囲は
それぞれの catalog で確認する。件数や plugin 名の一覧をここで重複管理しない。

### source 形式の制約 (踏み抜きやすい)

`plugins[].source` の文字列形式は **marketplace ルート配下を指す `./` 相対パス**しか
受け付けない。`../` で親へ遡ると次で拒否される。

```
Failed to install: This plugin's marketplace entry is invalid: source: Invalid input
```

そのためローカル marketplace は `marketplaces/local/plugins -> ../../plugins` の相対
symlink を持ち、`source` を `./plugins/<name>` にしている (公式カタログと同形)。
symlink は生成物と一組で、`--check` が両方を検査する。

**Claude は source がローカル実体を指していても、install は copy である。** 2026-08-11 実測:
`~/.claude/plugins/cache/harness-local/<name>/<version>/` に 539 個の実ファイルが
置かれ symlink は 0 件、`installed_plugins.json` に `gitCommitSha` が固定される。
したがって **harness 側の編集は再取得するまで反映されない**。更新手順は後述。

## ローカル catalog の準備

生成物の drift は `build-local-marketplace.py --check` と
`sync-plugin-platforms.py --repo-root /absolute/path/to/harness --all --check` で確認する。更新が必要なら各 generator で
再生成し、冒頭の共通 installer を実行する。Claude 側は `<repo>/marketplaces/local`、
Codex 側は `<repo>` を共通 helper が登録するため、製品ごとの手動登録は不要。

### 更新の流れ (harness 側を直したあと)

Claude install はキャッシュへの copy で、キャッシュのディレクトリ名が **version** である
(`cache/harness-local/harness-creator/1.3.0-codex.20260713-1/`。`+` は `-` へ潰れる)。
よって version を据え置いたまま中身だけ直しても、Claude Code から見れば「同じ版」で
あり取り直す理由が無い。ここを人手で管理すると必ず上げ忘れるので自動化してある。

CHANGELOG を先に更新してから対象 plugin の版を進め、両製品の package/catalog を
検査したうえで共通 installer を再実行する。

```bash
python3 /absolute/path/to/harness/scripts/build-plugin-release.py --only <name>
python3 /absolute/path/to/harness/scripts/build-plugin-release.py --check --only <name>
python3 /absolute/path/to/harness/scripts/build-local-marketplace.py --check
python3 /absolute/path/to/harness/plugins/harness-creator/scripts/sync-plugin-platforms.py --repo-root /absolute/path/to/harness --all --check
python3 /absolute/path/to/harness/plugins/harness-creator/scripts/install-local-plugins.py --plugin <name> --platform both
```

release は manifest と派生 version/catalog/lock を更新し、installer は user install 状態を
更新・検証する。`--only` を付けない release は変更された全 plugin を対象にする。
Claude は copy、Codex local は `live-source`、Git ref は `git-snapshot` として扱い、
receipt の `runtime_path` と `verified` で反映先を確認する。Claude の反映後は再起動する。

`--check` は無書込で「version 上げ忘れ」だけを報告し、あれば exit 1。CI
(`run-ci-checks.sh`) と `run-skill-create` の step 3.7 に組み込んであるので、
新 plugin の記録漏れ・既存 plugin の上げ忘れは自動で止まる。

major/minor を上げたいときは `plugin.json` を手で編集すればよい。script は
「内容が変わった」しか知らず破壊的変更を判定できないため、手動採番があればそれを
尊重して対応表の更新だけを行う。

#### repository の native surface 同期

repository 内の `.claude/{agents,skills,commands}` projection は
`sync-native-surfaces.py` (`make native-surfaces-check` / `make native-surfaces-apply`) が
管理する。`.claude/settings.json` の `enabledPlugins` の完全 identity を activation scope とし、
scope 外を無条件に投影しない。これは repository の開発用 surface 同期であり、
冒頭の user install と別の責務である。

### 反映されないときの切り分け

| 症状 | 原因 | 対処 |
|---|---|---|
| `source: Invalid input` で install 失敗 | `source` が marketplace ルート外を指している | `plugins` symlink が消えていないか `--check`。再生成で復旧する |
| `Component summary not available for remote plugin` | Claude Code が source をローカルと解釈できていない | 同上。`source` が `./plugins/<name>` 形式か確認 |
| 新しく作った plugin が Discover に出ない | 生成物が古い | `--check` が DRIFT を返すはず。再生成する (`run-skill-create` 経由なら workflow step 3.6 が自動実行するので、手で `plugins/<name>/` を作った場合に起きる) |
| 再生成したのに出ない | Claude Code 側のキャッシュ | `/plugins` → Marketplaces で該当 marketplace を update。効かなければ一度削除して Add し直す |
| harness 側を直したのに挙動が変わらない | install は copy であり、version が同じ間は取り直されない | 対象を release して共通 installer を再実行。Claude Code の再起動も要る |
| `Plugin "<name>" not found` | plugin identity または catalog が一致しない | catalog を検査し、共通 helper に `--plugin <name>` を渡す |

**marketplace.json を修正した後は、既に登録済みでも Claude Code 側の再読込が要る。**
登録状態は `~/.claude/plugins/known_marketplaces.json`、パース結果は
`~/.claude/plugins/plugin-catalog-cache.json` で確認できる。

## Claude パターン B: GitHub から登録する (配布可 plugin のみ)

1. 公開 marketplace が最新か確認する。

   ```bash
   python3 /absolute/path/to/harness/scripts/validate-plugin-completeness.py
   ```

2. `/plugins` → **Add Marketplace** に次のいずれかを入力する。

   - `daishiman/harness-dev` (owner/repo 形式)
   - `git@github.com:daishiman/harness-dev.git` (SSH 形式・private repo の場合)

3. `/plugin install <name>@skills` で導入する。

この経路に載る plugin は公開 catalog が正本である。`distributable:false` または
`NEVER_DISTRIBUTE` 対象は公開 catalog に登録しない。これはローカル install を妨げない。
公開可否を変更する場合は package contract と validator の制約を確認し、公開対象の
配置非依存性を `lint-readme-plugin-root-portability.py` で検証する。

## 注意: marketplace 名の衝突

`daishiman/HarnessHub` も marketplace 名 `skills` を名乗っている。両方を Add Marketplace
すると `<plugin>@skills` の exact identity が曖昧になる。同時登録する場合はどちらかの
`name` を改名すること。ローカル側 (`harness-local`) は最初から別名なので衝突しない。
