#!/usr/bin/env python3
# /// script
# name: lint-config-ssot
# purpose: 設定まわりの SSOT 整合を機械検証する。XDG 設定移行で実際に発生したドリフト4種(party_a 宙吊りキー / party_a-readme 二重実体 / 設定名のドット表記散在 / run-tests 段数の文書不一致)を再発防止する。
# inputs:
#   - argv: --plugin-root <path>(未指定はこのファイルから2階層上)
# outputs:
#   - stdout: 各チェックの OK/FAIL
#   - exit: 0=全 PASS / 1=違反あり
# contexts: [C]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.11"
# ///
"""責務: lint-config-ssot — contract-generator の設定 SSOT ドリフト検出。

WHY: 設定の事実(置き場所・優先順位・ファイル名・テスト段数)を複数文書が複製する構造は、
1 箇所の変更で残りがずれる正のフィードバックループを生む。コード層の SSOT
(config_auth.load_party_a / xdg_config_dir)は守られていても、表現層(docs/json)の
整合は手作業頼みだった。本 lint がその層間整合を CI で機械担保する(elegant-review 2026-05-31)。

検査(実際に壊れた事例からの帰納・誤検知を避け4点に限定):
  C-A party_a 宙吊りキー: template-mapping.json common.fixed_values の {{party_a.X}} を参照する
       甲列キーが、両 type の fields[] か「準拠法/管轄」等の非 party_a 固定値のいずれにも
       対応しない=差込経路の無い死にキーを検出。
  C-B party_a-readme 二重実体: skill 側 party_a-readme.md が正本(plugin 直下)への
       スタブ参照になっているか(全文複製に戻っていないか)。
  C-C 設定名ドット表記: ユーザー可視文書で `.google-config.json`(旧ドット名)が
       「後方互換」注記なしに使われていないか(正本名は google-config.json)。
  C-D run-tests 段数: run-tests.sh の実段数([N/M])と README-setup.md の段数記述が一致するか。
"""

import argparse
import json
import os
import re
import sys


def _plugin_root(explicit):
    if explicit:
        return os.path.abspath(explicit)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def check_party_a_dangling(root, fails):
    """C-A: fixed_values の party_a 参照キーに差込経路があるか。"""
    mp = os.path.join(root, "skills", "run-contract-generate", "references", "template-mapping.json")
    if not os.path.isfile(mp):
        fails.append(f"C-A: template-mapping.json が見つかりません ({mp})")
        return
    data = json.load(open(mp, encoding="utf-8"))
    common = data.get("common", {})
    fixed = common.get("fixed_values", {})
    # party_a を参照する固定値キー(甲名称など)
    party_cols = {k for k, v in fixed.items() if isinstance(v, str) and v.startswith("{{party_a.")}
    # 各 type の fields[] に column として現れる甲列
    filled = set()
    for t in ("individual", "corporate"):
        for f in data.get(t, {}).get("fields", []):
            filled.add(f.get("column"))
    dangling = sorted(c for c in party_cols if c not in filled)
    if dangling:
        fails.append(
            f"C-A: party_a 宙吊りキー(fixed_values に {{party_a.*}} があるが fields[] に差込経路なし): "
            f"{dangling}。fields[] に追加するか fixed_values から削除して整合させてください"
        )
    else:
        print(f"  C-A party_a 宙吊りキー: OK(fixed_values の甲列 {sorted(party_cols)} は全て fields[] に差込経路あり)")


def check_party_a_readme_stub(root, fails):
    """C-B: skill 側 party_a-readme.md が正本へのスタブ参照か。"""
    stub = os.path.join(root, "skills", "run-contract-generate", "references", "party_a-readme.md")
    canon = os.path.join(root, "references", "party_a-readme.md")
    if not os.path.isfile(canon):
        fails.append(f"C-B: 正本 references/party_a-readme.md が見つかりません ({canon})")
        return
    if not os.path.isfile(stub):
        print("  C-B party_a-readme 二重実体: OK(skill 側ファイルなし=複製なし)")
        return
    text = open(stub, encoding="utf-8").read()
    # スタブは正本を参照しているはず。優先順位表(4層)を全文複製していたら違反。
    has_ref = "party_a-readme.md" in text and ("正本" in text or "スタブ" in text)
    duplicates_table = text.count("party_a.json") >= 3 and "優先" in text
    if duplicates_table and not has_ref:
        fails.append(
            "C-B: skill 側 party_a-readme.md が正本の優先順位表を複製しています。"
            "正本(references/party_a-readme.md)へのスタブ参照に縮約してください"
        )
    else:
        print("  C-B party_a-readme 二重実体: OK(skill 側は正本へのスタブ参照)")


_DOC_GLOBS = [
    "README.md",
    "skills/run-contract-generate/references/README-setup.md",
    "skills/run-contract-generate/references/concept.md",
    "references/party_a-readme.md",
    # ユーザー可視のスキル定義・索引も監視(設定名の旧ドット表記がここに逃げないように)
    "skills/run-contract-generate/SKILL.md",
    "skills/run-contract-finalize/SKILL.md",
    "skills/run-template-sync/SKILL.md",
    "skills/run-contract-generate/references/resource-map.yaml",
]


def check_dot_config_name(root, fails):
    """C-C: ユーザー可視文書で旧ドット名が後方互換注記なしに使われていないか。"""
    offenders = []
    for rel in _DOC_GLOBS:
        p = os.path.join(root, rel)
        if not os.path.isfile(p):
            continue
        for i, line in enumerate(open(p, encoding="utf-8"), 1):
            if ".google-config.json" not in line:
                continue
            if "後方互換" in line or "旧" in line:
                continue  # 後方互換を説明する文脈は許容
            offenders.append(f"{rel}:{i}")
    if offenders:
        fails.append(
            "C-C: 旧ドット名 .google-config.json が後方互換注記なしで使われています(正本名 google-config.json に統一を): "
            + ", ".join(offenders)
        )
    else:
        print("  C-C 設定名ドット表記: OK(旧ドット名は後方互換文脈のみ)")


def check_runtests_stage_count(root, fails):
    """C-D: run-tests.sh の実段数と README-setup.md の段数記述が一致するか。"""
    sh = os.path.join(root, "scripts", "run-tests.sh")
    doc = os.path.join(root, "skills", "run-contract-generate", "references", "README-setup.md")
    if not os.path.isfile(sh):
        fails.append(f"C-D: run-tests.sh が見つかりません ({sh})")
        return
    sh_text = open(sh, encoding="utf-8").read()
    # [N/M] の M(総段数)を集める
    totals = set(int(m) for m in re.findall(r"\[\d+/(\d+)\]", sh_text))
    if len(totals) != 1:
        fails.append(f"C-D: run-tests.sh の段数表記 [N/M] の M が不統一です: {sorted(totals)}")
        return
    sh_stages = totals.pop()
    if not os.path.isfile(doc):
        print(f"  C-D run-tests 段数: OK(run-tests.sh={sh_stages}段・README-setup.md なし)")
        return
    doc_text = open(doc, encoding="utf-8").read()
    # 「N 段」記述を拾い、run-tests.sh を指す文の段数が実体と一致するか
    m = re.search(r"run-tests\.sh[^\n]*?(\d+)\s*段", doc_text)
    if m and int(m.group(1)) != sh_stages:
        fails.append(
            f"C-D: run-tests.sh は {sh_stages} 段ですが README-setup.md は {m.group(1)} 段と記述しています。一致させてください"
        )
    else:
        print(f"  C-D run-tests 段数: OK(run-tests.sh={sh_stages}段・文書記述と一致)")


# C-E: 導入後に存在しないプレースホルダパスを cron/cd 例に残していないか。
# WHY: マーケットプレイス導入後 plugin の実体は ~/.claude 配下にあり、開発リポジトリの
# `<repo>/plugins/contract-generator` や `<plugin>` 等のプレースホルダを cron にそのまま
# 貼ると cd 失敗で無言で動かない(README:443 で実際に発生した実害)。日常運用は対話駆動が
# 主で cwd 非依存だが、cron(手動自動化)だけは実パスが要るためここを機械検査する。
_CMD_DOCS = [
    "README.md",
    "skills/run-contract-generate/references/README-setup.md",
    "skills/run-contract-generate/SKILL.md",
    "skills/run-contract-finalize/SKILL.md",
    "skills/run-template-sync/SKILL.md",
]
_PLACEHOLDER_RE = re.compile(r"cd\s+<(repo|plugin)[^>]*>")


def check_install_paths(root, fails):
    """C-E: cron/cd 例に導入後不在のプレースホルダ(<repo>/<plugin>)が残っていないか。"""
    offenders = []
    for rel in _CMD_DOCS:
        p = os.path.join(root, rel)
        if not os.path.isfile(p):
            continue
        for i, line in enumerate(open(p, encoding="utf-8"), 1):
            if _PLACEHOLDER_RE.search(line):
                # 「開発リポジトリから動かす場合のみ」等の注記が同一行にあれば許容(意図的明示)
                if "開発リポジトリ" in line or "自動検出" in line:
                    continue
                offenders.append(f"{rel}:{i}")
    if offenders:
        fails.append(
            "C-E: cron/cd 例に導入後存在しないプレースホルダパス(<repo>/<plugin>)が残っています"
            "(find で実体を自動検出する形に直すか『開発リポジトリから動かす場合のみ』と注記を): "
            + ", ".join(offenders)
        )
    else:
        print("  C-E 導入後パス: OK(cron/cd 例に <repo>/<plugin> プレースホルダ残存なし)")


def main():
    ap = argparse.ArgumentParser(description="contract-generator 設定 SSOT 整合 lint")
    ap.add_argument("--plugin-root")
    a = ap.parse_args()
    root = _plugin_root(a.plugin_root)

    print("lint-config-ssot — 設定 SSOT 整合検査")
    fails = []
    check_party_a_dangling(root, fails)
    check_party_a_readme_stub(root, fails)
    check_dot_config_name(root, fails)
    check_runtests_stage_count(root, fails)
    check_install_paths(root, fails)

    if fails:
        print("\nFAIL: 設定 SSOT 整合違反")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("\nOK: 設定 SSOT 整合(party_a 経路 / readme スタブ / 設定名 / 段数 / 導入後パス すべて一致)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
