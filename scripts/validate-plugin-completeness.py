#!/usr/bin/env python3
"""validate-plugin-completeness.py — plugin が「丸ごとインストール」可能かを検査する。

Claude Code の /plugin install <name> は plugin ディレクトリ配下の
skills/ agents/ commands/ hooks/ をまとめて配布する。本スクリプトは:

  1. plugin ディレクトリに含まれる SKILL.md / agents/*.md / commands/*.md /
     hooks 定義 を列挙
  2. .claude-plugin/plugin.json の hooks 宣言と実体ファイルの整合
  3. ルート .claude-plugin/marketplace.json plugins[] への登録 (MK-001..003) と
     .claude-plugin/bundles.json への登録 (BD-001) を「実体ディレクトリ起点」で検査

を行い、配布時に欠落するアセットがないこと・マーケットプレイス/バンドル登録漏れが
ないことを保証する。

``references/package-contract.json`` の ``distribution.distributable`` (後方互換では
manifest 直下の ``distributable``) に false を宣言した plugin は「実体は保持するが
marketplace/bundle には非登録 (社内専用)」を意味する。この場合 MK-001/BD-001 の
登録漏れ検査は適用せず、逆に登録が残っていれば MK-004 (marketplace に登録残存) /
BD-002 (bundle に登録残存) を違反として検出する (放置すると意図せず配布される)。
``--fix`` も非配布 plugin の自動登録を skip する。未宣言は True 扱い (fail-closed)。

さらに恒久非配布 (社内専用) の plugin は固有名 denylist ``NEVER_DISTRIBUTE`` で
二重に固定する。フラグ駆動の MK-004 逆ガードは ``distributable`` フラグが true へ
漂流/欠落すると無効化されるため、固有名検査が「フラグの値に依存せず "distributable":
false の明示宣言が無ければ fail-closed で違反」とすることで漂流時も再配布を阻止する
多層防御。``--fix`` もこの固有名を自動登録対象から除外する。

二層防御:
  - 既定 (引数なし): 検出のみ。未登録があれば exit 1 で fail-closed (CI の最後の砦)。
  - ``--fix``: 予防。未登録 plugin を marketplace.json / bundles.json へ
    **append-only** (既存エントリの値を一切書き換えず追記のみ) で自動登録し、書込後に
    自分の検出を再実行して exit 0 を保証する。harness-creator の生成フロー
    (build-steps Phase G / workflow-manifest step3.5) から呼ばれ、「作るたびに必ず
    登録される」を機械保証する。既登録なら no-op (冪等)。最終的な登録是非は人間が
    PR diff で承認する。
    なお append の実装は2ファイルで非対称: marketplace.json は tags インライン整形を
    保つため**バイト単位のテキスト挿入** (既存バイトを 1 byte も触らない)、bundles.json は
    元から標準 2-space 整形なので ``json.dumps(indent=2)`` で round-trip 再シリアライズ
    する (既存 plugin 名の集合は不変=値レベル append-only、整形は再正規化されうる)。

検出 (validate) と予防 (--fix) を同一ファイルに同居させ、両者が単一 SSOT として
drift しないようにしている。
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import shlex
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
PLUGINS_DIR = ROOT / "plugins"
BUNDLES_JSON = ROOT / ".claude-plugin" / "bundles.json"
MARKETPLACE_JSON = ROOT / ".claude-plugin" / "marketplace.json"

# 恒久非配布 (社内専用・層 A-internal) の固有名 denylist。これらは distributable
# フラグの値に関わらず marketplace/bundle へ出てはならない。フラグが誤って true 化/
# 削除されても (= フラグ駆動の MK-004 逆ガードが無効化されても) この固有名検査が
# fail-closed で再配布を阻止する多層防御。配布化する正当な決定が出た場合のみ本集合から外す。
NEVER_DISTRIBUTE = frozenset({"harness-creator", "prompt-creator", "plugin-dev-planner"})


def load_bundle_members() -> set[str]:
    if not BUNDLES_JSON.exists():
        return set()
    data = json.loads(BUNDLES_JSON.read_text())
    members: set[str] = set()
    for b in data.get("bundles", []):
        for p in b.get("plugins", []):
            members.add(p)
    return members


def load_marketplace_entries() -> dict[str, str]:
    """marketplace.json plugins[] を {name: source} の dict で返す。

    bundles loader と対称的に、ルート .claude-plugin/marketplace.json を
    SSOT として読む。name -> source のマップを返すことで、登録漏れ (MK-001) /
    source 実在 (MK-002) / source basename 一致 (MK-003) の各検査に供する。
    """
    if not MARKETPLACE_JSON.exists():
        return {}
    data = json.loads(MARKETPLACE_JSON.read_text())
    entries: dict[str, str] = {}
    for p in data.get("plugins", []):
        name = p.get("name")
        if name is not None:
            entries[name] = p.get("source", "")
    return entries


def load_package_contract(plugin_dir: pathlib.Path) -> tuple[dict | None, str | None]:
    """Harness-only package metadata sidecar を読む。

    公式 Claude plugin manifest の schema には entry_points / distribution /
    depends_on を混在させない。sidecar が無い既存 plugin は後方互換の
    manifest fallback を使うが、sidecar が存在するのに壊れている場合は
    fail-closed でエラーを返す。
    """
    path = plugin_dir / "references" / "package-contract.json"
    if not path.exists():
        return None, None
    try:
        contract = json.loads(path.read_text())
        if not isinstance(contract, dict):
            raise ValueError("top level must be an object")
        return contract, None
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return None, f"{path}: {exc}"


def harness_metadata(manifest: dict, contract: dict | None) -> dict:
    """sidecar-first で harness 固有の配布メタデータを正規化する。"""
    distribution = contract.get("distribution", {}) if isinstance(contract, dict) else {}
    if not isinstance(distribution, dict):
        distribution = {}
    return {
        "distributable": distribution.get(
            "distributable", manifest.get("distributable", True)
        ),
        "bundle_targets": distribution.get(
            "bundle_targets", manifest.get("bundle_targets") or manifest.get("bundles") or []
        ),
        "category": distribution.get("category", manifest.get("category")),
        "tags": distribution.get(
            "tags", manifest.get("tags") or manifest.get("keywords") or []
        ),
    }


def collect(plugin_dir: pathlib.Path) -> dict:
    out = {
        "skills": sorted(p.parent.name for p in plugin_dir.glob("skills/*/SKILL.md")),
        "agents": sorted(p.name for p in plugin_dir.glob("agents/*.md")),
        "commands": sorted(p.name for p in plugin_dir.glob("commands/*.md")),
        "hooks": sorted(p.name for p in plugin_dir.glob("hooks/*") if p.suffix in {".sh", ".py"}),
        "scripts": sorted(p.name for p in plugin_dir.rglob("scripts/**/*.py")),
        "config": sorted(p.name for p in plugin_dir.glob("config/*.json")),
    }
    manifest_path = plugin_dir / ".claude-plugin" / "plugin.json"
    out["manifest"] = json.loads(manifest_path.read_text()) if manifest_path.exists() else None
    out["package_contract"], out["package_contract_error"] = load_package_contract(plugin_dir)
    out["manifest_hook_error"] = None
    # Claude Code plugin manifests may keep hook wiring in a plugin-relative
    # hooks.json and reference it with ``"hooks": "./hooks/hooks.json"``.
    # Normalize that official single-SSOT form for the same validation below
    # instead of assuming the manifest always embeds the event map inline.
    manifest = out["manifest"]
    if isinstance(manifest, dict) and isinstance(manifest.get("hooks"), str):
        hook_ref = manifest["hooks"]
        hook_path = (plugin_dir / hook_ref).resolve()
        try:
            hook_path.relative_to(plugin_dir.resolve())
            hook_doc = json.loads(hook_path.read_text())
            event_map = hook_doc.get("hooks") if isinstance(hook_doc, dict) else None
            if not isinstance(event_map, dict):
                raise ValueError("referenced hook config must contain a hooks object")
            normalized = dict(manifest)
            normalized["hooks"] = event_map
            out["manifest"] = normalized
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            out["manifest_hook_error"] = f"{hook_ref}: {exc}"
    return out


def validate(
    plugin_name: str,
    data: dict,
    bundle_members: set[str],
    marketplace_entries: dict[str, str],
) -> list[str]:
    errs: list[str] = []
    m = data["manifest"]
    if m is None:
        errs.append(f"{plugin_name}: .claude-plugin/plugin.json missing")
        return errs

    if data.get("manifest_hook_error"):
        errs.append(
            f"{plugin_name}: manifest hook reference invalid: "
            f"{data['manifest_hook_error']}"
        )

    if data.get("package_contract_error"):
        errs.append(
            f"{plugin_name}: package contract invalid: "
            f"{data['package_contract_error']}"
        )

    contract = data.get("package_contract")
    if isinstance(contract, dict):
        contract_name = contract.get("plugin_name")
        if contract_name is not None and contract_name != plugin_name:
            errs.append(
                f"{plugin_name}: package-contract.plugin_name "
                f"'{contract_name}' != directory name"
            )

        entry_points = contract.get("entry_points", {})
        if isinstance(entry_points, dict):
            actual_entry_points = {
                "skills": set(data["skills"]),
                "agents": {pathlib.Path(name).stem for name in data["agents"]},
                "commands": {pathlib.Path(name).stem for name in data["commands"]},
                "hooks": {pathlib.Path(name).stem for name in data["hooks"]},
            }
            for kind, actual in actual_entry_points.items():
                declared_raw = entry_points.get(kind, [])
                if not isinstance(declared_raw, list) or not all(
                    isinstance(name, str) for name in declared_raw
                ):
                    errs.append(
                        f"{plugin_name}: package-contract entry_points.{kind} "
                        "must be string[]"
                    )
                    continue
                declared = {
                    pathlib.Path(name).stem if kind != "skills" else name
                    for name in declared_raw
                }
                missing_entry_points = declared - actual
                if missing_entry_points:
                    errs.append(
                        f"{plugin_name}: package-contract declares {kind} not on disk: "
                        f"{sorted(missing_entry_points)}"
                    )

    for required in ("name", "version", "description"):
        if required not in m:
            errs.append(f"{plugin_name}: manifest missing '{required}'")

    if m.get("name") != plugin_name:
        errs.append(f"{plugin_name}: manifest.name '{m.get('name')}' != directory name")

    declared_hooks = set()
    hook_map = m.get("hooks") or {}
    if not isinstance(hook_map, dict):
        # collect() records the actionable path/parse error for referenced
        # configs.  Keep validation fail-closed without crashing on that
        # malformed value.
        hook_map = {}
    for hook_event, entries in hook_map.items():
        for entry in entries:
            for h in entry.get("hooks", []):
                cmd = h.get("command", "")
                try:
                    tokens = shlex.split(cmd)
                except ValueError:
                    tokens = cmd.split()
                for token in tokens:
                    if "CLAUDE_PLUGIN_ROOT" in token and "/hooks/" in token:
                        declared_hooks.add(token.split("/hooks/", 1)[1])
    on_disk_hooks = set(data["hooks"])
    missing = declared_hooks - on_disk_hooks
    if missing:
        errs.append(f"{plugin_name}: manifest declares hooks not on disk: {sorted(missing)}")

    has_any_asset = any(data[k] for k in ("skills", "agents", "commands", "hooks", "scripts", "config"))
    if not has_any_asset:
        errs.append(f"{plugin_name}: plugin contains no assets — empty distribution")

    # distributable:false = 実体は保持するが marketplace/bundle へは非登録 (社内専用)。
    # 未宣言は True 扱い (fail-closed): 登録漏れを既定で違反にする。
    metadata = harness_metadata(m, contract)
    distributable = metadata["distributable"]

    # NEVER_DISTRIBUTE 固有名不変条件 (フラグ漂流の最後の砦)。distributable フラグの
    # 値に依存せず、恒久非配布 plugin が "distributable": false を明示宣言していなければ
    # fail-closed で違反にする。is not False により true / キー欠落(None) / その他を全て捕捉。
    if plugin_name in NEVER_DISTRIBUTE and distributable is not False:
        errs.append(
            f"{plugin_name}: internal-only plugin must explicitly declare "
            f'"distributable": false but got distributable='
            f"{distributable!r} (NEVER-DISTRIBUTE)"
        )

    if distributable:
        if plugin_name not in bundle_members:
            errs.append(f"{plugin_name}: not registered in any .claude-plugin/bundles.json bundle (BD-001/BND-001)")

        # MK-001: 実体ディレクトリがあるのに marketplace.json plugins[].name に未登録 →
        # /plugin install のマーケットプレイス一覧に出ない (表示漏れの直接原因)。
        if plugin_name not in marketplace_entries:
            errs.append(f"{plugin_name}: not registered in .claude-plugin/marketplace.json plugins[] (MK-001)")
        else:
            source = marketplace_entries[plugin_name]
            # MK-002: marketplace エントリの source が実ディレクトリとして存在するか。
            source_dir = (ROOT / source).resolve() if source else None
            if not source or source_dir is None or not source_dir.is_dir():
                errs.append(f"{plugin_name}: marketplace.json source '{source}' is not an existing directory (MK-002)")
            # MK-003: source パスの basename が directory 名と一致するか (独立検査)。
            # name フィールド == directory 名 は上の汎用検査 (manifest.name != directory)
            # と marketplace_entries の引き方で既に担保されるため、ここは source が
            # 別ディレクトリを指す取り違えを捕捉する。
            src_base = pathlib.PurePosixPath(source.rstrip("/")).name if source else ""
            if src_base != plugin_name:
                errs.append(
                    f"{plugin_name}: marketplace.json source basename '{src_base}' != directory name (MK-003)"
                )
    else:
        # 逆ガード: 非配布宣言なのに登録が残っている = ドリフト (放置すると配布される)。
        # MK-004: marketplace.json plugins[] に登録が残存している。
        if plugin_name in marketplace_entries:
            errs.append(f"{plugin_name}: distributable:false but registered in marketplace.json plugins[] (MK-004)")
        # BD-002: いずれかの bundle に登録が残存している。
        if plugin_name in bundle_members:
            errs.append(f"{plugin_name}: distributable:false but registered in a bundle (BD-002)")

    return errs


# --- 予防層: --fix (append-only 自動登録) ------------------------------------

def _marketplace_entry_block(name: str, manifest: dict) -> str:
    """marketplace.json plugins[] へ挿入する 1 エントリを既存スタイル
    (indent 4 / tags インライン) のテキストで生成する。値は json.dumps で
    エスケープし、ensure_ascii=False で日本語をそのまま残す。
    """
    desc = manifest.get("description", "")
    ver = manifest.get("version", "0.0.0")
    cat = manifest.get("category", "productivity")
    tags = manifest.get("tags") or manifest.get("keywords") or []
    j = lambda v: json.dumps(v, ensure_ascii=False)
    return "\n".join([
        "    {",
        f'      "name": {j(name)},',
        f'      "source": {j(f"./plugins/{name}")},',
        f'      "description": {j(desc)},',
        f'      "version": {j(ver)},',
        f'      "category": {j(cat)},',
        f'      "tags": {j(tags)}',
        "    }",
    ])


def _insert_marketplace_entry(text: str, block: str) -> tuple[str, bool]:
    """plugins[] の閉じ括弧 (``\\n  ]``) の直前に block を append する。
    既存バイトを一切書き換えない真の append-only。marker 不在なら (text, False)。

    非空 plugins[] (多行整形) は閉じ ``\\n  ]`` の直前へ挿入する。空 plugins[]
    (``"plugins": []``、新規 marketplace.json 等) は配列を展開して最初の要素にする。
    """
    marker = "\n  ]"
    idx = text.rfind(marker)
    if idx != -1:
        return text[:idx] + ",\n" + block + text[idx:], True
    m = re.search(r'"plugins"\s*:\s*\[\s*\]', text)
    if m:
        return text[:m.start()] + '"plugins": [\n' + block + "\n  ]" + text[m.end():], True
    return text, False


def register_missing() -> tuple[list[str], bool]:
    """実体ディレクトリ起点で未登録 plugin を marketplace.json / bundles.json へ
    append-only 登録する。戻り値 (actions, changed)。
    既存エントリは不変更・既登録は no-op (冪等)。
    """
    actions: list[str] = []
    mk_entries = load_marketplace_entries()
    mk_text = MARKETPLACE_JSON.read_text() if MARKETPLACE_JSON.exists() else None
    bundles_data = json.loads(BUNDLES_JSON.read_text()) if BUNDLES_JSON.exists() else {"bundles": []}
    changed_mk = False
    changed_bd = False

    for plugin_dir in sorted(PLUGINS_DIR.iterdir()):
        if not plugin_dir.is_dir() or plugin_dir.name.startswith("."):
            continue
        name = plugin_dir.name
        manifest_path = plugin_dir / ".claude-plugin" / "plugin.json"
        if not manifest_path.exists():
            continue
        manifest = json.loads(manifest_path.read_text())
        contract, contract_error = load_package_contract(plugin_dir)
        if contract_error:
            actions.append(f"package-contract.json: ! {name} の解析失敗、自動登録を skip")
            continue
        metadata = harness_metadata(manifest, contract)

        # 非配布 plugin (distributable:false) は marketplace/bundle へ自動登録しない。
        # --fix が逆ガード (MK-004/BD-002) を踏む登録を生まないための断ち切り。
        # NEVER_DISTRIBUTE は フラグが漂流 (true 化/欠落) しても --fix が自動再登録しない
        # belt-and-suspenders: 固有名で恒久非配布を担保する。
        if metadata["distributable"] is False or name in NEVER_DISTRIBUTE:
            continue

        # marketplace.json (テキスト挿入で append-only)
        if mk_text is not None and name not in mk_entries:
            marketplace_metadata = dict(manifest)
            marketplace_metadata.update({
                "category": metadata["category"],
                "tags": metadata["tags"],
            })
            block = _marketplace_entry_block(name, marketplace_metadata)
            mk_text, ok = _insert_marketplace_entry(mk_text, block)
            if ok:
                mk_entries[name] = f"./plugins/{name}"
                changed_mk = True
                default_note = (
                    "" if (metadata["category"] and metadata["tags"])
                    else "  [category/tags はデフォルト値。PR で要確認]"
                )
                actions.append(f"marketplace.json: + {name}{default_note}")

        # bundles.json (bundle_targets を真実源として該当 bundle へ append)
        targets = metadata["bundle_targets"]
        for bundle_name in targets:
            bundle = next(
                (b for b in bundles_data.get("bundles", []) if b.get("name") == bundle_name),
                None,
            )
            if bundle is None:
                actions.append(
                    f"bundles.json: ! bundle '{bundle_name}' が存在せず {name} を登録不可 (手動で bundle 作成要)"
                )
                continue
            if name not in bundle.get("plugins", []):
                bundle.setdefault("plugins", []).append(name)
                changed_bd = True
                actions.append(f"bundles.json[{bundle_name}]: + {name}")

    if changed_mk and mk_text is not None:
        MARKETPLACE_JSON.write_text(mk_text)
    if changed_bd:
        BUNDLES_JSON.write_text(json.dumps(bundles_data, ensure_ascii=False, indent=2) + "\n")
    return actions, (changed_mk or changed_bd)


def run_check() -> tuple[list[str], list[str]]:
    """全 plugin を走査し (summary_lines, all_errs) を返す。検出のみ・副作用なし。"""
    bundle_members = load_bundle_members()
    marketplace_entries = load_marketplace_entries()
    all_errs: list[str] = []
    summary: list[str] = []
    for plugin_dir in sorted(PLUGINS_DIR.iterdir()):
        if not plugin_dir.is_dir() or plugin_dir.name.startswith("."):
            continue
        data = collect(plugin_dir)
        all_errs.extend(validate(plugin_dir.name, data, bundle_members, marketplace_entries))
        summary.append(
            f"{plugin_dir.name}: skills={len(data['skills'])} "
            f"agents={len(data['agents'])} commands={len(data['commands'])} "
            f"hooks={len(data['hooks'])} scripts={len(data['scripts'])} config={len(data['config'])}"
        )
    return summary, all_errs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fix",
        action="store_true",
        help="未登録 plugin を marketplace.json / bundles.json へ append-only 自動登録し、書込後に再検証する (予防層)。",
    )
    args = parser.parse_args(argv)

    if not PLUGINS_DIR.exists():
        print(f"ERROR: {PLUGINS_DIR} not found", file=sys.stderr)
        return 2

    if args.fix:
        actions, changed = register_missing()
        if actions:
            print("--fix actions (append-only):")
            for a in actions:
                print(f"  {a}")
        else:
            print("--fix: 登録漏れなし (no-op)")
        # 書込後に必ず自己再検証して exit 0 を保証する。残違反があれば surface。
        summary, all_errs = run_check()
        if all_errs:
            for e in all_errs:
                print(f"VIOLATION {e}", file=sys.stderr)
            print(
                f"--fix 後も残違反あり (VIOLATION={len(all_errs)})。"
                "登録不可 (bundle 不在等) を手動解決すること。",
                file=sys.stderr,
            )
            return 1
        print(f"--fix OK: {len(summary)} plugin(s) complete"
              + (" (変更あり)" if changed else " (変更なし)"))
        return 0

    summary, all_errs = run_check()
    for line in summary:
        print(line)
    print("---")
    if all_errs:
        for e in all_errs:
            print(f"VIOLATION {e}", file=sys.stderr)
        print(f"summary: VIOLATION={len(all_errs)}", file=sys.stderr)
        return 1
    print(f"OK: {len(summary)} plugin(s) complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
