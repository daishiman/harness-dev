# RESOLUTION P05-x-15 — `argument_hint` の正本を決める

対象: `plugin-plans/guide-doc-generator` の slash-command 面 (C07 / C08 / C09)。
起票元: `P05-C07-01` が build 中に発見した canon-conflict (C09 で 1 例目、C07 で 2 例目)。

## 1. 決定

**`argument_hint` の正本は `plugin-plans/guide-doc-generator/briefs/command-brief-<id>.json` の
`argument_hint` フィールドとする。**

- `component-inventory.json#<id>.argument-hint` は **brief からの導出済みの写し (derived-copy)** であり、
  brief を編集したときに一方向 (brief → inventory) で同期する。inventory 側を先に編集してはならない。
- 成果物 frontmatter (`plugins/guide-doc-generator/commands/*.md` の `argument-hint`) も brief からの導出物。
- テスト側の契約定数 (`plugins/guide-doc-generator/tests/<command>/contract_lib.py`) と
  accept fixture (`tests/<command>/fixtures/accept/commands/*.md`) も同様に brief 由来。

この決定は `component-inventory.json` の新設トップレベルキー `canon_rules[0]` に機械可読な形で記録した
(`field` / `canon` / `role_of_this_file` / `sync_direction` / `rationale` / `resolution_ref`)。
値そのものはそこに書いていない (写しを増やさないため)。宣言は 1 箇所だけに置く。

## 2. 実測した突合表 (同期前)

surface の略号:
`B` = `briefs/command-brief-<id>.json#argument_hint` /
`I` = `component-inventory.json#<id>.argument-hint` /
`F` = `plugins/guide-doc-generator/commands/<name>.md` frontmatter の `argument-hint` /
`T` = `plugins/guide-doc-generator/tests/<name>/contract_lib.py` の契約定数 /
`X` = `plugins/guide-doc-generator/tests/<name>/fixtures/accept/commands/<name>.md` frontmatter。

surface は 4 つではなく **5 つ**あった (accept fixture が 5 つ目)。

| id | command | B | I (同期前) | F | T | X | 判定 |
|----|---------|---|-----------|---|---|---|------|
| C07 | handout-build | `[題材] [--config <config.json>] [--doc-type <種別>] [--out-dir <path>] [--theme <preset>] [--date <yyyy/mm/dd>]` | `[題材] [--out-dir <path>] [--theme <preset> (構成データ未指定時のみ)]` | B と一致 | `ARGUMENT_HINT_TOKENS`= 全文字列ではなく token 集合 (`[題材]` / `--config` / `--doc-type` / `--out-dir` / `--theme` / `--date`)。B の全フラグを含み矛盾なし | B と一致 | **不一致 (I のみ古い)** |
| C08 | handout-extract | `<html-path> [--out <config.json>]` | B と一致 | B と一致 | `ARGUMENT_HINT` = B と同一の完全文字列リテラル | B と一致 | 一致 (5 surface 全一致) |
| C09 | handout-verify | `<html-path> [--config <config.json>] [--out-dir <path>] [--only <gate,...>] [--json-report <dir>]` | `<html-path> [--config <config.json>]` | B と一致 | `ARGUMENT_HINT_TOKENS` = token 集合 (`<html-path>` / `--config` / `--out-dir` / `--only` / `--json-report`)。B の全フラグを含み矛盾なし | B と一致 | **不一致 (I のみ古い)** |

食い違いは **inventory の 2 件 (C07 / C09) のみ**。他の 4 surface は 3 command すべてで brief と一致していた。
つまり「brief が実質的な正本として既に機能しており、inventory だけが追随できていない」という一方向の欠落である。

補足 (AC の対象外だが実測したので記録する): skill 面にも `argument-hint` があるが
(`skills/run-handout-build/SKILL.md` / `skills/run-handout-extract/SKILL.md` /
`skills/assign-handout-readability-evaluator/SKILL.md`)、これらは inventory に対応欄を持たず
`evidence/P05.json` に worker 裁量として記録済み。本 RESOLUTION の同期対象は slash-command 面に限る。

## 3. 正本を brief にした理由

1. **導出可能性が一方向にしか成立しない。** brief は `arguments[]` に
   name / position / required / 既定値 / 上書き規則 / rationale を構造として持っており、
   `argument_hint` はそこから機械的に組み立てられる表示文字列である。
   inventory は 1 本の文字列しか持たず、そこから `arguments[]` は復元できない。
   導出できる側を正本にすると導出元が失われる。
2. **機械検査の入力として既に brief が読まれている。**
   `tests/handout-build/test_handout_build_command.py::test_argument_hint_tokens_come_from_brief` は
   `command-brief-C07.json#argument_hint` をファイルから読んで契約定数と突き合わせている。
   `tests/handout-extract/test_handout_extract_command.py` は inventory 側の値を
   `contract_lib.ARGUMENT_HINT` と突き合わせており、inventory を「検査される側」として扱っている。
   すなわちテスト設計は既に brief=正本 / inventory=被検査側と宣言している。
3. **更新の発生源が brief 側にある。** 引数の追加・既定値・上書き規則の変更は
   `arguments[]` の編集として起き、そのとき `argument_hint` も同時に直る。
   inventory は plan 全体の索引であり、component 単位の詳細設計が確定する前に書かれる。
   構造上つねに後追いになる surface を正本に据えると、今回の 2 件は再発する。
4. **書き換えコストの非対称。** inventory を正本にすると、C07 と C09 の成果物 frontmatter・
   accept fixture・contract_lib の 3 surface × 2 command を同時に旧表記へ戻すことになり、
   `arguments[]` に定義された引数が hint から消えて brief 内部が自己矛盾する。

## 4. 退けた案

| 案 | 退けた理由 |
|----|-----------|
| inventory を正本にし、brief と成果物を inventory へ合わせる | 上記 3-1 / 3-4。`arguments[]` に定義された引数が hint から消え、brief が自己矛盾する。実装 2 本と 2 スイートを同時に壊す |
| どちらも正本とせず「一致していればよい」とする | 今回の欠陥そのもの。方向が決まっていないため、片方だけ更新されたときにどちらへ寄せるかが判断できず、build worker ごとに解釈が割れる (C09 と C07 で実際に割れた) |
| inventory から `argument-hint` フィールドを削除して brief への参照だけを残す | 本タスクの受入基準が「frontmatter が `component-inventory.json#<id>` の `argument_hint` と文字列一致する」を要求しており、削除すると突合対象が消えて基準が検証不能になる。加えて `tests/handout-extract` が `c08["argument-hint"]` を実在キーとして読んでおり、削除は write_scope 外のテストを赤にする |
| inventory の値を brief パスの文字列 (`briefs/command-brief-C07.json#argument_hint`) に置き換える | frontmatter との文字列一致検査が成立しなくなる。同上 |
| 各 brief にも「この brief が正本」と書き足す | 同じ宣言文を 3 ファイルへ複製することになり、「同じ内容を複数箇所へ書き下す」という本件の欠陥を別の形で再生産する。宣言は `component-inventory.json#canon_rules` の 1 箇所だけに置いた |

## 5. 本タスクで実施した同期 (write_scope 内)

`plugin-plans/guide-doc-generator/component-inventory.json`:

- `components[].id=C07` の `argument-hint` を brief 値へ更新。
- `components[].id=C09` の `argument-hint` を brief 値へ更新。
- トップレベルへ `canon_rules` を新設し、`argument-hint` の正本・同期方向・当ファイルの役割を宣言。

C08 は同期前から 5 surface すべて一致しており、変更していない。
`briefs/` 配下は brief が正本であるため変更不要 (1 バイトも触っていない)。

同期後の実測: C07 / C08 / C09 のいずれも B = I = F = X が完全文字列一致
(T は C08 が完全文字列、C07 / C09 は token 集合で B と矛盾なし)。

## 6. write_scope 外に残した必要変更 (未実施 / 提案)

いずれも**本タスクの受入基準の充足には不要**で、再発防止を一段強めるための任意の改善である。
`plugins/guide-doc-generator/` は write_scope 外のため実施していない。担当 leaf を別途立てること。

### 6-1. `tests/handout-extract/contract_lib.py` の完全文字列リテラルを brief 由来にする (推奨)

現状 (該当箇所):

```python
# component-inventory.json #C08 argument-hint (brief の argument_hint と一致している)
ARGUMENT_HINT = "<html-path> [--out <config.json>]"
```

提案する形 (値の写しを持たず brief から読む。assert の強さは変えない —
frontmatter・inventory の両方に対する完全一致検査はそのまま残り、突合の基準が brief に移るだけ):

```python
# argument-hint の正本は briefs/command-brief-C08.json#argument_hint。
# 正本の決定は plugin-plans/guide-doc-generator/RESOLUTION-P05-x-15-argument-hint.md。
# ここでは値を再掲せず正本から読み、frontmatter と inventory の双方を正本へ突き合わせる。
def _brief_argument_hint():
    import json
    return json.loads(
        (plan_root() / "briefs" / "command-brief-C08.json").read_text(encoding="utf-8")
    )["argument_hint"]


ARGUMENT_HINT = _brief_argument_hint()
```

(`plan_root()` に相当するヘルパが `contract_lib` に無い場合は、既存の `plugin_root()` から
`plugin_root().parents[1] / "plugin-plans" / "guide-doc-generator"` を返す私的ヘルパを 1 本足す。
`test_handout_extract_command.py` は既に同じ経路で `PLAN_ROOT` を組み立てているため、
新規の経路知識は増えない。)

これを入れると C08 の完全文字列の写しが 1 つ減り、写しは
「brief (正本) / inventory (derived-copy) / 成果物 frontmatter / accept fixture」の 4 つになる。

### 6-2. accept fixture の位置づけを README へ明記する (任意)

`tests/<command>/fixtures/accept/commands/<name>.md` の `argument-hint` は
「チェッカを通る入力例」であって文言の正本ではない。
`tests/handout-verify/README.md` の gap 1 (「`argument-hint` の正本が 2 つある」) は
本 RESOLUTION で解消したため、当該記述を
「正本は brief。inventory は derived-copy (RESOLUTION-P05-x-15-argument-hint.md)」へ更新するのが望ましい。
`tests/handout-build/README.md` の出典略号表 (`B` = brief (正本) / `I` = inventory) は
本決定と既に整合しているため変更不要。

### 6-3. 成果物 frontmatter

C07 / C08 / C09 のいずれも brief と完全一致しており、**変更は不要**。

## 7. 再発した場合の判定手順

1. 差分が出た surface を特定する。
2. `briefs/command-brief-<id>.json#argument_hint` を正 (canon) とする。
3. brief 側が誤っている場合は、まず `arguments[]` を直し、その帰結として `argument_hint` を直す
   (`argument_hint` だけを直さない — 導出元と表示が乖離する)。
4. `component-inventory.json#<id>.argument-hint` / 成果物 frontmatter / accept fixture を
   brief の値へ合わせる。
5. 各 command の自スイート (`tests/handout-build` / `tests/handout-extract` / `tests/handout-verify`) を回す。
