#!/usr/bin/env python3
"""feedback_protocol SSOT 整合 lint (オフライン、NOTION_TOKEN 不要)。

検証:
  R1. skill-list.schema.json#feedback_protocol が必須キーを満たす
  R2. page_body_sections に id=feedback (renderer_ref=feedback_protocol) が含まれる
  R3. run-skill-feedback/SKILL.md が schema を SSOT として参照している
  R4. run-skill-feedback/SKILL.md の triggers が firing_conditions を包含する近似 (各 firing_condition の主要キーワードが triggers のいずれかに含まれる)
  R5. notion-upsert-plugin.py が _load_feedback_protocol() を経由している
  R6. 量産プラグイン (plugins/*/plugin.json 保持) の README/plugin.json/commands/agents に run-skill-feedback 発火経路が周知されている
      (default warn / --strict で exit 1)
  R7. 量産プラグイン (生成器自身=feedback_contract_ssot.is_feedback_deploy_exempt で除外) の skills/run-skill-feedback/ が symlink/実体で配備されている
      (default warn / --strict で exit 1)
  R8. notion-submit-improvement.py が token/DB ID を CLI 引数で受けず notion_config 経由でのみ解決し
      token を argv (Authorization ヘッダ) にも出力呼び出し (print/write/logging, AST 走査) にも載せず、
      notion_config の解決順 (token=Keychain 既定/env は明示許可時のみ, DB ID=key 別 env > config) を挙動で満たす
      (SKILL.md feedback_contract IN2 の verify_by:lint の実体)

Usage:
  python3 scripts/lint-feedback-protocol.py [--strict]
"""
import argparse, ast, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# dogfooding 除外境界は SSOT (FC.is_feedback_deploy_exempt) が単一正本。
sys.path.insert(0, str(ROOT / "scripts"))
import feedback_contract_ssot as FC  # noqa: E402
SCHEMA = ROOT / "doc" / "notion-schema" / "skill-list.schema.json"
SKILL_MD = ROOT / "plugins" / "harness-creator" / "skills" / "run-skill-feedback" / "SKILL.md"
UPSERT = ROOT / "scripts" / "notion-upsert-plugin.py"
SUBMIT = ROOT / "scripts" / "notion-submit-improvement.py"


PLUGINS_DIR = ROOT / "plugins"
FEEDBACK_KEYWORD = "run-skill-feedback"


def _target_plugins():
    """検査対象 plugin (manifest を持ち、生成器自身=配備除外プラグインは除外)。

    除外境界は SSOT 述語 (FC.is_feedback_deploy_exempt) に委譲する。
    """
    if not PLUGINS_DIR.exists():
        return []
    out = []
    for plugin_dir in sorted(PLUGINS_DIR.iterdir()):
        if not plugin_dir.is_dir():
            continue
        if FC.is_feedback_deploy_exempt(plugin_dir.name):
            continue
        manifests = [
            plugin_dir / ".claude-plugin" / "plugin.json",
            plugin_dir / "plugin.json",
            plugin_dir / "plugin-composition.yaml",
        ]
        if not any(p.exists() for p in manifests):
            continue
        out.append(plugin_dir)
    return out


def check_plugin_awareness():
    """R6: 量産プラグイン側に発火経路 (run-skill-feedback) の周知文言があるか。

    haystack: manifest (plugin.json / .claude-plugin/plugin.json / plugin-composition.yaml)
              + README.md + commands/*.md + agents/*.md
    """
    warnings = []
    for plugin_dir in _target_plugins():
        haystack = ""
        candidates = [
            plugin_dir / ".claude-plugin" / "plugin.json",
            plugin_dir / "plugin.json",
            plugin_dir / "plugin-composition.yaml",
            plugin_dir / "README.md",
        ]
        for sub in ("commands", "agents"):
            d = plugin_dir / sub
            if d.is_dir():
                candidates.extend(sorted(d.glob("*.md")))
        for p in candidates:
            if p.exists():
                try:
                    haystack += p.read_text()
                except Exception:
                    pass
        if FEEDBACK_KEYWORD not in haystack:
            warnings.append(f"R6: {plugin_dir.name} に '{FEEDBACK_KEYWORD}' 発火経路の周知記載が無い (manifest/README/commands/agents)")
    return warnings


def check_plugin_deployment():
    """R7: 量産プラグインに skills/run-skill-feedback/ が symlink/実体で配備されているか。"""
    warnings = []
    for plugin_dir in _target_plugins():
        target = plugin_dir / "skills" / "run-skill-feedback"
        # symlink でも実体でも存在すれば OK (broken symlink は exists() が False)
        if not (target.exists() or target.is_symlink()):
            warnings.append(f"R7: {plugin_dir.name} に skills/run-skill-feedback/ 配備なし")
            continue
        if target.is_symlink() and not target.exists():
            warnings.append(f"R7: {plugin_dir.name}/skills/run-skill-feedback/ が broken symlink")
    return warnings


def check_secret_resolution():
    """R8: token / DB ID の解決が notion_config へ一元化され、CLI・log へ露出しないか。

    SKILL.md の feedback_contract IN2 は「Keychain 既定 / key 別 env > .notion-config.json の順で
    notion_config 経由でのみ解決され、応答・log・context に一切露出しない」を `verify_by: lint` と
    宣言している。宣言先の lint が実際には何も見ていないと、契約が空写像になり
    「lint 緑 = 秘密が漏れていない」と読み替えられる。ここで機械的に確認できる 5 点を押さえる。
    ただし押さえるのは **script のソース側**だけで、実行時に Claude が応答へ書き写す経路は
    依然として機械検査の外にある (SKILL.md Gotcha 3 に明記)。
    """
    out = []
    src = SUBMIT.read_text() if SUBMIT.exists() else ""
    if not src:
        return ["R8: scripts/notion-submit-improvement.py が見つからない"]

    # (1) token / DB ID を CLI 引数で渡す経路が無い (渡せると shell 履歴と ps に残る)
    for opt in re.findall(r"add_argument\(\s*[\"'](--[a-z0-9-]+)[\"']", src):
        if re.search(r"token|secret|db-id|database-id", opt):
            out.append(f"R8: notion-submit-improvement.py に秘密を受け取る CLI 引数 '{opt}' がある")

    # (2) 解決は notion_config 経由のみ。script が直に env を読むと解決順の SSOT が二重化する
    if "notion_config.require_or_skip" not in src or "notion_config.get_db_id" not in src:
        out.append("R8: notion-submit-improvement.py が notion_config の解決経路 "
                   "(require_or_skip / get_db_id) を経由していない")
    direct_env = re.findall(r"os\.(?:environ(?:\.get)?|getenv)\s*[\(\[]\s*[\"']([A-Z_]+)[\"']", src)
    leaked = [k for k in direct_env if k.startswith("NOTION")]
    if leaked:
        out.append(f"R8: notion-submit-improvement.py が NOTION_* env を直接読んでいる: {sorted(set(leaked))}")

    # (3) token を subprocess の argv に載せない。argv は ps から読めるうえ、
    #     CalledProcessError.__str__() が cmd 全体を含むため、例外を整形する print が
    #     一つあるだけで token が stdout へ出る (実際に踏んだ経路)。出力側を塞ぐ
    #     アプローチは列挙漏れが避けられないので、載せないことを直接検査する。
    if re.search(r"[\"']-{1,2}(?:H|header)[\"']\s*,\s*f?[\"']Authorization", src):
        out.append("R8: notion-submit-improvement.py が Authorization ヘッダを argv "
                   "(-H/--header の直後) に載せている — ps と CalledProcessError 経由で漏れる。"
                   "stdin (curl --config -) 等で渡すこと")

    # (4) token の「値」を出力関数へ渡さない。行単位の正規表現だと複数行 print や
    #     stderr/logging を取り逃すので、AST で「出力呼び出しの引数部分木に token が現れるか」を見る。
    #     散文に token という語が出るだけの文字列 (復旧手順の案内) は Name/FormattedValue でないため対象外。
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return out + [f"R8: notion-submit-improvement.py が parse できない: {e}"]

    def _emits(func):
        """print / *.write / logging.* / *.log(...) を出力呼び出しとみなす。"""
        if isinstance(func, ast.Name):
            return func.id == "print"
        if isinstance(func, ast.Attribute):
            if func.attr in ("write", "writelines"):
                return True
            if func.attr in ("debug", "info", "warning", "error", "exception", "critical", "log"):
                return True
        return False

    def _mentions_token(node):
        return any(isinstance(n, ast.Name) and n.id == "token" for n in ast.walk(node))

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _emits(node.func):
            if any(_mentions_token(a) for a in list(node.args) + [k.value for k in node.keywords]):
                out.append(f"R8: notion-submit-improvement.py:{node.lineno} が "
                           "出力呼び出しへ token の値を渡している")

    out.extend(_check_resolution_order())
    return out


def _check_resolution_order():
    """R8 (5): notion_config の解決順そのものを **挙動** で pin する。

    IN2 は解決順 (token=Keychain 既定 / env は INTAKE_ALLOW_ENV_TOKEN=1 明示時のみ /
    DB ID=key 別 env > .notion-config.json) まで verify_by:lint と宣言している。
    submit script が require_or_skip / get_db_id を「呼んでいる」ことだけ見ても、
    呼び先が順序を入れ替えたら宣言は静かに偽になる。AST で実装の形を照合する手もあるが、
    等価な書き換え (早期 return / ヘルパ抽出) で壊れる割に順序の逆転は捕まえられない。
    そこで env を仕込んで実際に呼び、返り値で順序を確定させる。
    """
    out = []
    ncdir = ROOT / "plugins" / "harness-creator" / "scripts"
    if not (ncdir / "notion_config.py").exists():
        return ["R8: notion_config.py が見つからない (解決順を検証できない)"]
    import importlib, os
    sys.path.insert(0, str(ncdir))
    try:
        nc = importlib.import_module("notion_config")
    except Exception as e:  # noqa: BLE001
        return [f"R8: notion_config を import できない: {e}"]

    CANARY = "lint-canary-not-a-real-secret"
    saved = {k: os.environ.get(k) for k in ("NOTION_TOKEN", "INTAKE_ALLOW_ENV_TOKEN",
                                            "NOTION_DB_SKILL_LIST")}
    # Keychain へ問い合わせさせない (実 token を掴まないため、存在しない service/account を与える)
    bogus_cfg = {"keychain_service": "lint-canary-absent-service",
                 "keychain_account": "lint-canary-absent-account"}
    try:
        os.environ["NOTION_TOKEN"] = CANARY
        os.environ.pop("INTAKE_ALLOW_ENV_TOKEN", None)
        if nc.get_token(bogus_cfg) == CANARY:
            out.append("R8: notion_config.get_token が INTAKE_ALLOW_ENV_TOKEN 無しで "
                       "env NOTION_TOKEN を採用している (IN2 は明示許可時のみと宣言)")
        os.environ["INTAKE_ALLOW_ENV_TOKEN"] = "1"
        if nc.get_token(bogus_cfg) != CANARY:
            out.append("R8: notion_config.get_token が INTAKE_ALLOW_ENV_TOKEN=1 でも "
                       "env NOTION_TOKEN を採用しない (IN2 の escape hatch が機能していない)")
        os.environ["NOTION_DB_SKILL_LIST"] = CANARY
        if nc.get_db_id("skill-list") != CANARY:
            out.append("R8: notion_config.get_db_id が key 別 env を "
                       ".notion-config.json より優先していない")
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true", help="R6/R7 を fail (exit 1) として扱う")
    args = ap.parse_args()
    violations = []
    sc = json.loads(SCHEMA.read_text())

    # R1
    fp = sc.get("feedback_protocol")
    required = {"command", "firing_conditions", "intake_fields", "status_lifecycle",
                "open_statuses", "promise_to_reporter", "callout_summary"}
    if not fp:
        violations.append("R1: skill-list.schema.json に feedback_protocol が無い")
    else:
        missing = required - set(fp.keys())
        if missing:
            violations.append(f"R1: feedback_protocol に必須キー欠落: {sorted(missing)}")

    # R2
    sections = sc.get("page_body_sections", [])
    fb_sec = next((s for s in sections if s.get("id") == "feedback"), None)
    if not fb_sec:
        violations.append("R2: page_body_sections に id=feedback が無い")
    elif fb_sec.get("renderer_ref") != "feedback_protocol":
        violations.append("R2: feedback section の renderer_ref が feedback_protocol を指していない")

    # R3
    md = SKILL_MD.read_text() if SKILL_MD.exists() else ""
    if "feedback_protocol" not in md or "skill-list.schema.json" not in md:
        violations.append("R3: run-skill-feedback/SKILL.md が schema feedback_protocol を参照していない")

    # R4: firing_conditions の主要語が triggers に存在
    if fp:
        tr_match = re.search(r"^triggers:\s*\n((?:\s+-.*\n)+)", md, re.M)
        triggers_blob = tr_match.group(1) if tr_match else ""
        keywords = ["分かりにくい", "直してほしい", "バグ", "改善", "要望"]
        missing_kw = [k for k in keywords if k not in triggers_blob and k not in md]
        if missing_kw:
            violations.append(f"R4: SKILL.md triggers/本文に発火キーワード欠落: {missing_kw}")

    # R5
    src = UPSERT.read_text() if UPSERT.exists() else ""
    if "_load_feedback_protocol" not in src:
        violations.append("R5: notion-upsert-plugin.py が _load_feedback_protocol() を未使用")

    # R8
    violations.extend(check_secret_resolution())

    if violations:
        print(f"[FAIL] feedback_protocol SSOT lint: {len(violations)} violation(s)")
        for v in violations:
            print(f"  - {v}")
        sys.exit(1)

    r6_warnings = check_plugin_awareness()
    r7_warnings = check_plugin_deployment()
    has_warn = bool(r6_warnings or r7_warnings)
    label = "FAIL" if args.strict else "WARN"
    if r6_warnings:
        print(f"[{label}] R6 周知 lint: {len(r6_warnings)} 件")
        for w in r6_warnings:
            print(f"  - {w}")
    if r7_warnings:
        print(f"[{label}] R7 配備 lint: {len(r7_warnings)} 件")
        for w in r7_warnings:
            print(f"  - {w}")
    if has_warn and args.strict:
        sys.exit(1)

    print("[OK] feedback_protocol SSOT lint: all checks passed")


if __name__ == "__main__":
    main()
