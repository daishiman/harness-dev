# 34a 章 settings.json マージ仕様

最終更新: 2026-10-10（`scripts/build-claude-settings.py` の今の挙動に合わせて全体を書き直した。本文の行番号は 2026-10-10 時点の同 script のもの）

## §1 目的

`scripts/build-claude-settings.py`（以下 builder）が、開発用 `.claude/settings.json` に対して何をするかの正本仕様を定める。builder がすることは次の3つだけである。

1. plugin の permissions（`deny` と `ask`）を `.claude/settings.json` の `permissions` に合わせ、台帳 `_build_claude_settings.managed_permissions` に記録する。
2. 前の実行で入れた値（台帳の `managed_hooks` と `managed_permissions` に載っている値）を取り除く。台帳に載っていない値は project 所有として残す。
3. plugin どうしで skill・agent・command の名前がぶつかっていないかを調べる（§4）。

### plugin の hook は settings へ投影しない

当初の案では、plugin の hook（`plugin.json` の inline `hooks` と `hooks/*.json`）を正規化して `.claude/settings.json` の `hooks` へ書き出し、台帳 `managed_hooks` で管理するつもりだった。今の builder はこれをしない。

- **hook の配り元**: Claude Code と Codex の plugin loader が、plugin root の `hooks/hooks.json` から hook を1回だけ読む。2026-10-10 時点で `plugins/*/hooks/hooks.json` は13 plugin にあり、`plugins/*/.claude-plugin/plugin.json` に `hooks` を持つものは無い。
- **しない理由**: settings にも同じ hook を書くと、plugin loader の配布と合わせて同じ hook が2回動く（[34章](./34-plugin-governance-roadmap.md) の「settings.json マージ仕様（hook 二重発動の予防）」）。
- **実装**: `discover_plugins()` は hook を読んで正規化し、検証するだけ（L396-398 のコメント）。`build()` は `generated_hooks = []` に固定している（L764-768）。`tests/test_build_claude_settings.py` の `test_inv4_plugin_hooks_are_not_project_managed` が `managed_hooks == []` を、`test_same_plugin_inline_and_hook_file_are_not_projected` が plan の `settings.hooks == []` を固定する。
- **前に投影した hook**: 台帳 `managed_hooks` に載っている hook は、`remove_managed_values()`（L458-505）が `hooks` から取り除く（`test_plugin_delivered_hooks_are_pruned_from_project_settings`）。今の builder は台帳 `managed_hooks` を毎回 `[]` で書くので、取り除く対象があるのは古い台帳が残っているときだけである。

本章のほかの節で hook に触れるところは、すべてこの節を前提にしている。

plugin package に何を同梱するかは [36章](./36-plugin-package-harness-contract.md) が正本である。本章は、同梱された設定を builder が `.claude/settings.json` にどう反映するかだけを扱う。

## §2 三層モデル参照と正本境界

34章の三層モデルは、Layer1 `plugin.json`、Layer2 `hooks/` と `settings/`、Layer3 `.claude/settings.json` の3つである。builder が Layer3 へ派生させるのは permissions だけで、hook は派生させない。hook は Layer2 の `hooks/hooks.json` がそのまま配布の正本になる（§1）。

| 領域 | 正本 |
|---|---|
| plugin 移行の Phase gate、hook と設定の置き場所 | [34章](./34-plugin-governance-roadmap.md) |
| settings に反映するときの不変条件と台帳の構文 | 本章 |
| CLI 契約 | builder の `USAGE`（L34-42）と `test_help_matches_contract_usage`（§12） |
| 実装と検証 | `scripts/build-claude-settings.py`、`tests/test_build_claude_settings.py`、`tests/scripts-root/test_root__build_claude_settings.py` |
| `.claude/{skills,agents,commands}` の symlink と、その名前の衝突 | `scripts/build-claude-symlinks.py`、`tests/test_build_claude_symlinks.py` |
| plugin package に何を同梱するか | [36章](./36-plugin-package-harness-contract.md) |

以前の版は、CLI 契約・実装検証・symlink の namespace preflight の正本として `doc/migration/phase0/` の 04・07・03 を挙げていた。しかし repo に `doc/migration/` は無い（2026-10-10 に確認）。そのため参照を外し、上の表の実物に置き換えた。

## §3 対象データと非対象データ

| 種別 | builder が読むもの | `.claude/settings.json` へ | 扱い |
|---|---|---|---|
| hooks | `plugin.json` の `hooks`（object の inline 宣言）、`hooks/*.json` | 書かない（§1） | 読んで正規化し、検証するだけ。`HOOK_EVENTS` に無い event や型の違いは exit 3（L122-148）。`plugin.json` の `hooks` が文字列（参照）なら、参照先が plugin の `hooks/` の下のファイルであることだけを確かめ、中身は `hooks/*.json` の走査で読む。`hooks/` の外を指すか、ファイルが無ければ exit 3（L360-376） |
| permissions.deny | `plugin.json` の `permissions.deny`、`settings/permissions.json`（`permissions` で包んでも包まなくてもよい） | `permissions.deny` | 完全一致は1件にまとめる。同じ rule を別の plugin が `ask` で宣言したら exit 2（§9） |
| permissions.ask | 同上の `ask` | `permissions.ask` | 同上 |
| permissions.allow など | 読まない | 書かない | `normalize_permissions()` は `deny` と `ask` だけを見る（L155）。`allow` があってもエラーにはならず、無視される |

`skills/`・`agents/`・`commands/` は settings には入らない。`.claude/{skills,agents,commands}/` の symlink は `scripts/build-claude-symlinks.py` が作る。同名で実体が違うものがあれば、そちらも `conflict` として exit 2 で止まる（同 script L186-221・L384-386）。builder 側も、§4 で同じ名前の衝突を独立に調べる。

## §4 グローバル名前空間 preflight

本節は 36章 PKG-003 と名前空間の定義を共有する。PKG-003 は package 単位の衝突検査で、本節は builder が settings に反映する前に plugin 群全体で行う検査（`namespace_preflight()` L513-553）である。

| 名前空間 | キー | 同名のときの扱い |
|---|---|---|
| skill | `skills/<dir-name>` と `SKILL.md` の frontmatter `name` | 実体（`real_path`）が同じか、内容の hash（`content_sha256()` L208-226。`__pycache__`・`*.pyc`・`.DS_Store` などは除く）が同じなら `shared` として通す。違えば `conflict` で exit 2 |
| agent | `agents/<file-name>`（`.md` を含むファイル名。`.md` ファイル以外のもの（directory を含む）があれば exit 3、L261-262） | skill と同じ |
| command | `commands/<file-name>`（agent と同じ） | skill と同じ |
| permission | `rule` | 完全一致は1件にまとめる。`deny` と `ask` に分かれたら exit 2（§9） |
| plugin | `.claude-plugin/plugin.json` の `name` | 同名は exit 3（`duplicate plugin name`） |
| hook | なし | builder は調べない。plugin の hook は settings に入らず（§1）、plugin 間の hook の重なりは builder の判定の対象外である（L766-767 のコメント、INV-5） |

36章の PKG-003 は `hook-name` も名前空間に挙げているが、builder の名前空間に hook は無い。

公式 plugin の実行時の namespaced invocation と、開発用の `.claude/skills/<short-name>` symlink は別物として扱う。dev 短名の symlink では、実体の違う同名を許さない。同名を残したい場合は、plugin 側で skill 名か directory 名を変える。

## §5 settings JSON 構造

builder が書く `.claude/settings.json` の形は次のとおり。2026-10-10 時点では permissions を持つ plugin が無いので、台帳はどちらも空である。`hooks` に入るのは project 所有の hook だけである。

```json
{
  "_build_claude_settings": {
    "managed_hooks": [],
    "managed_permissions": []
  },
  "permissions": {
    "deny": ["Bash(rm -rf*)"],
    "ask": []
  },
  "hooks": {
    "SessionStart": [
      {
        "hooks": [{"type": "command", "command": "<project 所有の hook>"}]
      }
    ]
  },
  "enabledPlugins": {}
}
```

書く順は `_build_claude_settings` → `permissions` → `hooks` → そのほかの key（元の順のまま）である（`build_desired_settings()` L633-679）。台帳の2つの key、`permissions.deny`、`permissions.ask`、`hooks` は毎回書く。`hooks` が空なら `{}` になる。

構造の検証（`validate_settings_structure()` L411-441）は、target を読むとき（L93）と、書く前の desired（L678）の両方にかける。

- `permissions` は object。`deny` と `ask` があれば array。
- `hooks` は object。各 key の値は array。array でなければ exit 3。
- key が `HOOK_EVENTS`（§6）にある event なら、entry は object、entry の `hooks` は array、その各要素は `type: "command"` と空でない `command` を持つ。
- key が `HOOK_EVENTS` に無い event は、中身を検証せずにそのまま残す（L426-437、`test_target_unknown_hook_event_preserved`）。2026-10-10 の `.claude/settings.json` にある `FileChanged` と `TaskCreated` がこれに当たる。
- そのほかの top-level key（`enabledPlugins` など）は触らずに残す（INV-6）。

## §6 管理メタデータ構文

JSON にはコメントが無い。また Claude Code は `hooks` の直下の key を hook event として読む。そのため `hooks` の下に `_generated_section_start` などの番兵キーを置いてはならない。管理情報は top-level の `_build_claude_settings`（台帳）にだけ置く。

番兵キーの禁止は規則であり、builder が機械的に止めるのは一部だけである（2026-10-10 に scratchpad の fixture で確かめた）。

- builder 自身は番兵キーを書かない。
- `hooks` の下の key の値が array でなければ exit 3 になる（例: `"_generated_section_start": "x"` は `hooks._generated_section_start must be an array`）。
- 値が array なら `HOOK_EVENTS` に無い event として扱われ、そのまま残る（exit 0）。この形の番兵キーを builder は見つけられない。

```bnf
managed-metadata    ::= "_build_claude_settings": managed-object
managed-object      ::= {"managed_hooks": [managed-hook*], "managed_permissions": [managed-permission*]}
managed-hook        ::= {"event": hook-event, "matcher": string-or-null, "command": string, "from_plugin": string}
managed-permission  ::= {"scope": permission-scope, "decision": permission-decision, "rule": string, "from_plugin": string}
hook-event          ::= "PreToolUse" | "PostToolUse" | "PostToolUseFailure" | "UserPromptSubmit" | "UserPromptExpansion" | "Stop" | "SubagentStop" | "SessionStart" | "SessionEnd" | "Notification" | "PreCompact" | "PostCompact" | "TaskCompleted"
permission-scope    ::= "permissions.deny" | "permissions.ask"
permission-decision ::= "deny" | "ask"
```

- `hook-event` は builder の `HOOK_EVENTS`（L15-32）である。plugin 側の hook がこれ以外の event を使うと exit 3 になる（`test_managed_source_unknown_hook_event_blocked_exit3`）。target の `.claude/settings.json` 側は、これ以外の event も残す（§5）。
- `managed_hooks`: 今の builder は毎回 `[]` を書く（§1）。古い台帳を読むときは、`event` と `command` を持つ要素を `(event, matcher または "", command)` で照合する。entry の command が1つでも台帳と一致すれば、その entry ごと `hooks` から取り除く（L461-464・L471-491）。
- `managed_permissions`: 今回 plugin から入れた rule を記録する。次の実行では、`(scope, rule)` が一致する rule を `permissions` から取り除いてから入れ直す（L465-468・L493-503）。
- 台帳に載っていない値は project 所有として残す（INV-1）。台帳が object でない場合や、各 key が array でない場合は、空の台帳として扱う（`managed_from_target()` L444-455）。

## §7 マージアルゴリズム

`build()`（L758-790）と `main()`（L793-826）の流れは次のとおり。

```text
target = load .claude/settings.json           # 無ければ {}。root が object でない・構造違反は exit 3
before = user_section_sha256(target)           # 台帳に載った値を除いた残りの sha256
project_root = target の2つ上の directory
plugins = discover_plugins(--plugins-dir)      # directory 名の順。--exclude-plugin の名前は manifest を読む前に飛ばす
  for each plugin:
    read .claude-plugin/plugin.json            # 無い・壊れている・name の重複は exit 3
    hooks: inline object + hooks/*.json        # 正規化と検証だけ（§1）
    permissions: plugin.json の permissions + settings/permissions.json（deny と ask だけ）
    namespace: skills / agents / commands
    plugin が project_root の外なら exit 3
plugins を plugin name の順に並べる
namespace = namespace_preflight(plugins)       # §4
generated_hooks = []                           # §1: 投影しない
permissions, permission_conflicts, dedupe = merge_permissions(plugins)   # §9
desired:
  user = remove_managed_values(target)         # 古い台帳の hook と permission を取り除く
  _build_claude_settings = {managed_hooks: [], managed_permissions: permissions}
  permissions.deny / ask = user の rule + まだ無い plugin の rule
  hooks = user の hook のまま
  そのほかの key = user のまま
  validate_settings_structure(desired)
if user_section_sha256(desired) != before:
  conflicts に INV-1 を足す
main:
  --print-user-section-hash → hash を出して exit 0
  conflicts がある         → plan を出して exit 2（書かない）
  --dry-run                → plan を出して exit 0（書かない）
  --check                  → plan を出す。target と desired が同じなら exit 0、違えば exit 1（書かない）
  それ以外                 → atomic_write（INV-8）。読み直して INV-1 をもう一度確かめる（違えば exit 2）
```

`--print-user-section-hash` も先に `build()` を通るので、plugin の形の誤りがあれば exit 3 になる。

## §8 不変条件

plan の `invariants_checked` は今も INV-1〜INV-12 の12個を並べる（L33）。INV-4 と INV-5 は、§1 のとおり hook を投影しなくなったので、意味を今の実装に合わせて書き直した。

### INV-1 user 管理値保存

台帳（`managed_hooks` と `managed_permissions`）に載っていない既存の値は残す。比べるのは byte ではなく、台帳の値を除いた JSON を key 順で正規化した sha256 である（`user_section_sha256()` L507-510）。書く前に desired で比べ（L774-778。違えば conflict として exit 2）、書いた後に読み直してもう一度比べる（L810-814。違えば exit 2。このときファイルはもう書き換わっている）。

注意: project が手で書いた permission と同じ rule を plugin も宣言すると、その rule が台帳に載る。すると「台帳を除いた残り」から消えるので、INV-1 違反として exit 2 になる（2026-10-10 に fixture で確かめた。この場合の test は無い）。plugin の rule を入れたいときは、project 側の同じ rule を先に消す。

機械検証: `test_inv1_user_section_byte_equality`。

### INV-2 決定的生成

同じ plugin 群と target からは、同じ plan と同じ settings ができる。plugin は name の順（L408）、permission は `(from_plugin, scope, rule)` の順（L597）に並べる。

機械検証: `test_inv2_deterministic_output`。同じ入力で `--dry-run --json` を2回実行し、出力が同じかを比べる。

### INV-3 冪等性

同じ入力で2回書いた後の `--check` は、差分なしで exit 0 を返す。

機械検証: `test_inv3_idempotent`。書く、もう一度書く、`--check` の3段階で確かめる。

### INV-4 plugin の hook を台帳に載せない

当初は「複数 plugin の hook を plugin name の順に並べる」という条件だった。hook を投影しなくなったので、意味を変えた。plugin がいくつ hook を宣言しても、台帳 `managed_hooks` は `[]`、plan の `settings.hooks` は `[]` になる。古い台帳に載っている hook は取り除く。

機械検証: `test_inv4_plugin_hooks_are_not_project_managed`、`test_same_plugin_inline_and_hook_file_are_not_projected`、`test_plugin_delivered_hooks_are_pruned_from_project_settings`。

### INV-5 plugin 間の hook の重なりは builder の衝突にしない

当初は「異なる plugin が同じ event・matcher・command を出したら exit 2」という条件だった。今の builder は hook を settings に書かないので、これを衝突として扱わない。plugin 間で同じ hook があっても exit 0 で、plan の `conflicts` に `type: "hook"` は出ない。

hook の衝突を判定する `merge_hooks()`（L556-590）は script に残っているが、`build()` からは呼ばれていない。`tests/scripts-root/test_root__build_claude_settings.py` の `test_merge_hooks_*` が、この関数を単体で確かめているだけである。

機械検証: `test_inv5_shared_plugin_hook_is_outside_project_conflict_scope`。

### INV-6 未知キー保存

未知の top-level key、`HOOK_EVENTS` に無い hook event、台帳に載っていない hook と permission は消さない。

機械検証: `test_inv6_unknown_top_level_preserved`、`test_target_unknown_hook_event_preserved`。

### INV-7 JSON 正規化

ファイル全体を UTF-8（`ensure_ascii=False`）、indent 2、末尾改行ありで書き直す（`serialize()` L71-72）。書式は project の値も含めてそろえ直すが、project の key の順は保つ。key の順は §5 のとおり。

機械検証: `test_inv7_json_normalization`。

### INV-8 原子的書き込み

同じ directory の一時ファイルに書いてから、`os.rename` で置き換える。失敗したら一時ファイルを消し、元のファイルは残る（`atomic_write()` L732-751）。conflict のとき、`--dry-run` のとき、`--check` のときは書かない。

機械検証: `test_inv8_atomic_write_failure_keeps_original`。

### INV-9 グローバル名前空間一意性

§4 の衝突があれば exit 2 で、`.claude/settings.json` を書かない。`.claude/skills` などの symlink は builder ではなく `build-claude-symlinks.py` が作り、同名の衝突はそちらでも exit 2 になる（§3）。

機械検証: `test_inv9_namespace_conflict_exit2`、`test_distinct_content_same_name_still_conflicts`。共有を衝突にしないことは、`test_symlink_shared_skill_is_not_conflict`、`test_byte_identical_physical_skill_copies_are_shared`、`test_build_cache_in_one_physical_copy_is_still_shared` で確かめる。

### INV-10 settings 構造検証

target を読むときと、書く前の desired に、§5 の構造検証をかける。

機械検証: `test_inv10_settings_structure_validation`。

### INV-11 permissions マージ安全性

permissions は、完全一致（scope・decision・rule）だけを1件にまとめる。まとめた数は plan の `summary.dedupe` に出す。同じ rule が `deny` と `ask` に分かれた場合は、自動で優先順位を決めずに exit 2 にする。

機械検証: `test_inv11_permissions_dedupe_and_conflict`。

### INV-12 plan 完全性

`--dry-run --json` の plan は、settings だけでなく、§4 の名前空間 preflight の結果も含める。

機械検証: `test_inv12_plan_completeness`。plan に `namespace`・`settings`・`conflicts`・`invariants_checked` があり、`invariants_checked` が INV-1〜INV-12 であることを確かめる。plan のすべての key は §12 にある。

## §9 衝突検出

### hook 衝突検出

builder は hook の衝突を調べない（§1、INV-5）。

### permissions 衝突検出

`merge_permissions()`（L593-623）の流れは次のとおり。

```text
generated = 全 plugin の permission を (from_plugin, scope, rule) の順に並べたもの
by_rule = {}; exact = {}
for p in generated:
  if p.rule が by_rule にあり、その decision が p.decision と違う:
    conflicts.append({type: "permission", rule: p.rule, decisions: [2つの decision を並べたもの]})
    continue
  by_rule[p.rule] = p.decision
  if (p.scope, p.decision, p.rule) が exact にある:
    dedupe += 1
    continue
  exact に入れて、出力に加える
conflicts があれば exit 2（書かない）
```

衝突のキーは `rule` だけである。以前の版の疑似コードは `(scope, rule)` をキーにしていた。しかし scope は decision と1対1なので、それでは deny と ask の衝突を見つけられない。実装は `rule` をキーにしている（L605）。

## §10 例

### 例 1: hook だけを持つ plugin（今の repo の形）

`plugins/harness-creator/hooks/hooks.json` のように hook を `hooks/hooks.json` に置く plugin があっても、builder の出力に hook は出ない。2026-10-10 に `python3 scripts/build-claude-settings.py --check --json` を実行した結果は次のとおり。

- exit 0。`plugins` は22件、`excluded_plugins` は空、`conflicts` は空。
- `settings` は `{"hooks": [], "permissions": []}`。
- `summary` は `{"add": 0, "keep": 0, "dedupe": 0, "conflict": 0}`、`user_values_preserved` は `true`。
- `namespace` は skill 127件（`ok` 106・`shared` 21）、agent 68件、command 31件で、衝突は0件。

### 例 2: permissions を持つ plugin

`plugins/a/settings/permissions.json` が `{"permissions": {"ask": ["Bash(curl*)"]}}` で、target がまだ無いとき、builder は次の settings を書く。

```json
{
  "_build_claude_settings": {
    "managed_hooks": [],
    "managed_permissions": [
      {
        "scope": "permissions.ask",
        "decision": "ask",
        "rule": "Bash(curl*)",
        "from_plugin": "a"
      }
    ]
  },
  "permissions": {
    "deny": [],
    "ask": [
      "Bash(curl*)"
    ]
  },
  "hooks": {}
}
```

### 例 3: 前に投影した hook を取り除く

`test_plugin_delivered_hooks_are_pruned_from_project_settings` の形である。実行前の target は次のとおり。

```json
{
  "_build_claude_settings": {
    "managed_hooks": [
      {"event": "PreToolUse", "matcher": "Write|Edit", "command": "python3 stale-plugin-hook.py", "from_plugin": "alpha"}
    ],
    "managed_permissions": []
  },
  "permissions": {"deny": [], "ask": []},
  "hooks": {
    "PreToolUse": [
      {"matcher": "Write|Edit", "hooks": [{"type": "command", "command": "python3 stale-plugin-hook.py"}]},
      {"matcher": "Write", "hooks": [{"type": "command", "command": "python3 user-hook.py"}]}
    ]
  }
}
```

実行後は、`managed_hooks` が `[]` になり、`hooks.PreToolUse` には `python3 user-hook.py` の entry だけが残る。

### 例 4: permission の衝突

plugin `a` が `deny: ["R"]`、plugin `b` が `ask: ["R"]` を宣言すると exit 2 になる。plan の `conflicts` は `[{"type": "permission", "rule": "R", "decisions": ["ask", "deny"]}]` で、target は書き換わらない。

### 例 5: project が手で書いた rule と plugin の rule が同じ

target の `permissions.deny` に、台帳に載っていない `"R"` がある。そこへ plugin も `deny: ["R"]` を宣言すると exit 2 になる。plan の `conflicts` は `[{"type": "invariant", "id": "INV-1", "message": "user values changed"}]` である（INV-1 の注意）。

## §11 機械検証手段

| 条件 | 検証 |
|---|---|
| 矛盾なし | 本章、34章の「settings.json マージ仕様（hook 二重発動の予防）」、builder の実物を照合する |
| 漏れなし | `tests/test_build_claude_settings.py` が INV-1〜INV-12 の test を1件以上ずつ持つ（§8 の各 INV の「機械検証」）。関数単位の test は `tests/scripts-root/test_root__build_claude_settings.py` にある |
| 整合性あり | plan の `invariants_checked` が INV-1〜INV-12 を並べ、`namespace` に preflight の結果を含める（INV-12） |
| CI | `make native-surfaces-check` が `plugins/harness-creator/scripts/sync-native-surfaces.py --check` を実行する。それが builder を `--json --check` で呼ぶ（範囲外の plugin は `--exclude-plugin` で外す。同 script L520-531）。`make native-surfaces-check` は `.github/workflows/governance-check.yml` と `.github/workflows/harness-creator-kit-ci.yml` が実行する |

以前の版にあった task 04・07 を使った照合と「02 → 04 → 07 → 08」の順序は、§2 の理由（`doc/migration/` が無い）で外した。

## §12 CLI 契約への引き継ぎ

CLI の正本は builder の `USAGE`（L34-42）で、`test_help_matches_contract_usage` が `--help` の出力を固定している。2026-10-10 の `--help` の出力は次のとおり。

```text
usage: build-claude-settings.py [-h]
                                [--plugins-dir PLUGINS_DIR]
                                [--target TARGET]
                                [--exclude-plugin PLUGIN]
                                [--dry-run]
                                [--check]
                                [--print-user-section-hash]
                                [--json]
                                [--verbose]
```

| 引数 | 既定 | 意味 |
|---|---|---|
| `--plugins-dir` | `plugins` | plugin を探す directory |
| `--target` | `.claude/settings.json` | 書く settings。target の2つ上の directory を project root とみなし、plugin がその外にあれば exit 3（L399-404・L761） |
| `--exclude-plugin PLUGIN` | なし（繰り返し指定できる） | directory 名で plugin を外す。manifest を読む前に外すので、壊れた plugin も外せる（L337-338、`test_exclude_plugin_is_repeatable_and_removes_managed_source`・`test_excluded_malformed_plugin_is_not_a_managed_source`） |
| `--dry-run` | — | 書かない。plan を出して exit 0 |
| `--check` | — | 書かない。target と desired が同じなら exit 0、違えば exit 1 |
| `--print-user-section-hash` | — | 台帳の値を除いた部分の sha256 を出して exit 0 |
| `--json` | — | plan を JSON で出す。指定しなければ `add=… keep=… dedupe=… conflict=…` の1行を出す |
| `--verbose` | — | `--json` と同じく plan を JSON で出す |

- 終了コード: `0` 成功、`1` drift（`--check`）、`2` 衝突または INV-1 違反、`3` 入力や plugin の形の誤り（`LayoutError`）と `OSError`（L817-825）。
- 判定の順: `--print-user-section-hash` → 衝突（exit 2）→ `--dry-run` → `--check` → 書き込み（L798-816）。衝突のときは、`--dry-run` を付けただけでも plan を JSON で出す。
- plan の key（`build_plan()` L681-717）: `target`・`plugins`・`excluded_plugins`・`management_format`・`namespace`・`conflicts`・`settings`（`hooks` と `permissions`）・`user_values_preserved`・`invariants_checked`・`summary`（`add`・`keep`・`dedupe`・`conflict`）。
- plan の細部: `management_format` は固定の文字列 `"_build_claude_settings.managed_hooks"`、`summary.keep` は常に0。`settings.permissions[].scope` は `deny` か `ask` で、台帳の `scope`（`permissions.deny`）とは書き方が違う。

## §13 hook の Capability 化（2026-05-22 の案。未実装）

2026-05-22 に、23章 § Capability 抽象への拡張 に合わせて、次の案を書いた。hook を `plugins/<name>/capabilities/<hook-name>.manifest.json`（`kind: hook`）として独立に宣言する経路 (B) を足し、builder がそれも読んで、`managed_hooks` に `from_capability` を併記する、という案である。

2026-10-10 時点の実物は次のとおりで、この案は実装されていない。

- builder は `capabilities/` を読まない。`discover_plugins()`（L322-408）が読むのは、`.claude-plugin/plugin.json`、`hooks/*.json`、`settings/permissions.json`、`skills/`・`agents/`・`commands/` だけである。
- repo に `capabilities/` の下のファイルは無い（`git ls-files` で0件）。台帳の `from_capability` は、builder にも、その test（§2 の表の2本）にも無い。
- `kind: hook` の schema（`plugins/harness-creator/skills/run-build-skill/references/capability-manifest.schema.json` の `definitions.kindHook`）はある。

また §1 のとおり、builder は hook を settings へ書かない。そのため案にあった「経路 (B) の hook を settings merge の入力にする」「経路 (A) と (B) の重なりを exit 2 にする」「`managed_hooks` に `from_capability` を足す」は、今の builder の役割と合わない。hook の Capability 化を進める場合も、hook の配り元は plugin の `hooks/hooks.json` のままになる。

### 関連章

- [23章](./23-meta-skill-architecture.md) § Capability 抽象への拡張: kind=hook の三層 contract 写像表
- [33章](./33-change-governance.md) § CapabilityBundle governance: hook 改訂のカテゴリ判定
- [35章](./35-meta-harness-feedback-loop.md): hook が観測する failure_mode の正本連携
