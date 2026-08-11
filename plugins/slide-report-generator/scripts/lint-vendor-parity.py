#!/usr/bin/env python3
# /// script
# name: lint-vendor-parity
# purpose: vendorのsha256 pinと明示local overlay/additive契約を検証する。
# inputs:
#   - argv: none
# outputs:
#   - stdout: parity summary
#   - stderr: missing/mismatch findings
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""lint-vendor-parity.py — vendor integrity ゲート。

vendor/ 配下の byte 携行ツリー (scripts/ assets/ schemas-fixtures/ package.json
package-lock.json) を、plan 同梱の再現性アンカー ``vendor-digest-manifest.json``
(191 files sha256 pin) と照合する。移植元 live tree には依存しない。

additive_new_files (report 新規 Node: render-report.js / mermaid-render.js、
および vendor/tests/ 配下、manifest 自身) と package.json/package-lock.json の
Mermaid依存・実test配線は parity 対象外 (excluded_additive)。package 2ファイルは
byte比較の代わりに依存とtest配線をsemantic検証する。

意図的な plugin-local fork は manifest.local_fork_managed と
ADDITIVE_LOCAL_FORK の集合一致を必須にし、byte 比較の代わりに owner 付きの
semantic contract と回帰試験で検証する。未宣言の pin 不一致は許可しない。

exit 0 = byte-pin と全 managed overlay が一致、exit 1 = 不一致あり。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys

PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(PLUGIN_ROOT, "vendor", "vendor-digest-manifest.json")

# manifest.subtrees[].source -> vendor/ 配下の実 target ディレクトリ/ファイル
SUBTREE_TARGETS = {
    "presentation-slide-generator/scripts/": "vendor/scripts/",
    "presentation-slide-generator/assets/": "vendor/assets/",
    "presentation-slide-generator/schemas/": "vendor/schemas-fixtures/",
    "presentation-slide-generator/schemas/ (example fixtures + README のみ)": "vendor/schemas-fixtures/",
    "presentation-slide-generator/package.json": "vendor/",
    "presentation-slide-generator/package-lock.json": "vendor/",
}
ADDITIVE_PACKAGE_FILES = {"package.json", "package-lock.json"}
_EXACT_SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
# Mermaid <=11.14.0 は既知の injection / DoS advisories の対象。
_MIN_SAFE_MERMAID = (11, 15, 0)
# 図解品質のためにローカルで意図的に fork した vendor ファイル。
# byte pin を書き換えて差分を消すと「vendor は移植元そのまま」という主張が
# 静かに崩れるため、package/runtime 契約と同じく semantic gate へ退避させる。
# 各値は (必須トークン..., ) で、fork の要点が残っているかだけを検査する。
ADDITIVE_LOCAL_FORK = {
    "scripts/svg-builder.cjs": (
        "require('./svg-kit.cjs')",
        "function svgTextFit",
        "function colorOf",
    ),
    # svg-builder が依存する土台。単独では manifest に存在しない新規ファイル。
    "scripts/svg-kit.cjs": (
        "function wrapText",
        "function fitText",
        "FORBID_LINE_START",
        "const LAYOUTS",
        # 線幅の語彙。消えても図は描けてしまう (リテラルへ戻るだけ) ため、
        # 存在をここで縛らないと upstream 上書きで静かに退行する。
        "const STROKE",
        "hairline: 1.25",
        # D6 (4px グリッド) を「描いてから直す」のではなく寸法の作り方で満たす
        # ための一群。snapUp/snapDown が消えると矩形が 1-2px ずれて戻り、
        # goldens が一斉に warning へ落ちる。
        "function snapUp",
        "function snapDown",
        "const floorW = snapUp(minW);",
        "const sw = snapUp(fontSize - 2);",
        # 折れ線の可視性。どちらも消えても図は描けてしまうが、描けた図が壊れる。
        # trunkY を落とすと分岐の横走りが宛先の上辺と重なって線が枠へ溶け、
        # opts.mid を落とすと同じ段間を走る複数本が全部同じ高さで重なる。
        "function trunkPaths(srcPort, dstPorts, trunkX, trunkY)",
        # 幹を 1 本だけ引く分解。これを戻すと宛先ごとのフルパスが共有区間へ
        # n 本重なり、重なった区間で本数が数えられなくなる (D20)。
        "out.push({ d: `M${num(minX)},${num(trunkY)} H${num(maxX)}`, arrow: false });",
        "const mid = opts.mid != null ? opts.mid : (y1 + y2) / 2;",
        # 行内で間のノードを跨ぐ遷移の迂回路。消すと elbowPath の水平 1 本へ
        # 戻り、途中の箱を線が貫いて「その箱を経由する」と誤読される (D21)。
        "function detourPath(x1, y1, x2, y2, level, opts = {})",
        # ラベルの画布内クランプ。消すと辺の端に着いた取付点でラベルが
        # viewBox を越え、文字が切れて読めなくなる (D1 error)。
        "if (opts.canvasW) rx = clamp(rx, GRID, opts.canvasW - w - GRID);",
        # 凡例であることの構造的な印。消えても図は同じに見えるが、I3 が
        # 見本の塗りを語彙に数え直し「凡例を描くほど凡例を要求される」
        # 自己敗北ループへ静かに戻る。
        '<rect data-legend="1"',
        # 線種の凡例。線で意味を分けた図 (実線=同期 / 破線=非同期) を
        # 色の四角だけで説明する形へ戻ると、凡例があるのに読み解けない。
        "function legendSwatch(it, x, y, sw) {",
    ),
    # 構造図 10 タイプ。配置戦略 × ノード語彙 × コネクタ語彙 の組合せで組む。
    "scripts/svg-structures.cjs": (
        "function buildArchitecture",
        "function buildSwimlane",
        "function buildDpIntegration",
        "function connector",
        # ビルダー固有の寸法定数も 4px グリッド上に置く (D6)。
        # 代表として ER のカード寸法を縛る (cardH = 48 + 24n を保証する組)。
        "const headH = 36, fieldH = 24;",
        # 段間リンクは入力が宣言したときだけ引く。この分岐が消えると
        # below[Math.min(i, below.length - 1)] の添字代用へ戻り、入力に無い
        # 依存を図が断言する (情報が欠ける欠陥より重い)。
        "const refs = Array.isArray(to) ? to : (to == null ? null : [to]);",
        # 上下同位置の慣行は「入力の実件数」で判定する。クランプ後の描画件数で
        # 比べる形へ戻すと、溢れた段どうしが同じ上限値へ丸められただけで一致と
        # 判定され、存在しない 1:1 対応を LEVEL_ITEMS 本の線が断言する。
        "const rawCounts = list.map((l) => ((l && l.items) || []).filter(Boolean).length);",
        "rawCounts[li] === rawCounts[li + 1]",
        # 引けないメッセージを先に落とす。入力の添字で y を決める形へ戻すと、
        # 落ちたぶんだけ空行が残り、行間に意味があるように読めてしまう。
        ".filter((e) => e.a >= 0 && e.b >= 0 && e.a !== e.b);",
        # レーン図の線は宣言 (links / order / 同一レーンの列順) からしか引かない。
        # 位置の連番を既定の order にする形へ戻すと、order を書いていない入力
        # (表からの起こし・svgSpec の射影) で「レーン 1 の全工程 → レーン 2 の
        # 全工程」という受け渡しを図が断言する。
        "function swimlanePairs(placed, links) {",
        # 帯をまたぐ線の上に「何を渡したか」を書く (契約 §2.4)。消えると
        # 受け渡しの中身が読めず、待ちの理由も差し戻しの単位も分からない。
        "if (l.label && !l.sameLane) {",
        # 出所行と明示凡例は既存レイアウトの**外**へ帯として足す。builder の
        # 領域計算へ押し込む形へ戻すと、凡例が伸びた図で重なりが起きる (D1)。
        "const prov = provenanceBand(width, height + legend.height, opts);",
        # 辺への取付を本数で散らす一群。どれが消えても、同じ辺の中央へ複数本が
        # 着いて重なり、入出力の本数が読めなくなる (D20)。
        "const skipsABox = (a, b) => {",
        "const fanOf = (k) => {",
        "const archFan = (name, side) => {",
    ),
    # 構造図を slideType から呼べるようにした dispatch と、白 fill の役割別置換。
    "scripts/render-slide.cjs": (
        "require('./svg-structures.cjs')",
        "diagram-architecture",
        "diagram-dp-integration",
        "/^(text|tspan)$/i.test(tag)",
        # buildEr が読むのは opts.relations。links で渡すと ER の関連線が
        # 例外も出さずに全部消えるので、キー名をここで縛る。
        "relations: c.relations || c.links || []",
        # 作図宣言を成果物へ運び、slideでも参照整合を厳密検査する。
        "const referentialTypes = new Set([",
        "data-srg-declaration=",
        # 未知型をplausibleなmessage面へ落とさない。
        "unknown slideType or missing template:",
    ),
    # schemaが受理するD3型を汎用placeholderへ落とさないinline runtime。
    "scripts/d3-bootstrap.cjs": (
        "case 'radial-bar':",
        "case 'pyramid':",
        "case 'funnel':",
        "case 'waterfall':",
        "case 'roadmap':",
        "case 'vertical-timeline':",
        "case 'wordcloud':",
        "case 'chevron':",
        "data-d3-fallback",
        "unsupported component:",
    ),
    # 仕様確定ゲートの schema 解決。vendor/schemas/ に structure.schema.json が
    # 同梱されない配布形態では plugin 直下 schemas/ が正本になるため、候補列で
    # 解決する。この候補列が消えると legacy 59 種への silent fallback に戻り、
    # 構造図 10 種 (diagram-er 等) がゲートを通れなくなる。
    "scripts/validate-structure.js": (
        "SCHEMA_PATH_CANDIDATES",
        'resolve(SKILL_ROOT, "..", "schemas", "structure.schema.json")',
    ),
    # report 側から構造図 10 種を呼べるようにした dispatch と射影群。manifest に
    # 存在しない新規ファイルなので byte pin が効かず、退行しても静かに
    # fallbackVisual (図なしの理由テキスト) に落ちるだけで気付けない。
    "scripts/render-report.js": (
        "require('./svg-structures.cjs')",
        "const VARIANT_STRUCT",
        # 射影が消えると variant は enum に残ったまま描けなくなる。10 種のうち
        # 引数形の異なる代表 3 つ (1 引数+opts / 2 引数 / groups 依存) を縛る。
        "function projectEntities",
        "function projectSequence",
        "function projectHubSpokes",
        # edges[] の id を表示名へ解決する層。builder は名前で端点を突合するため、
        # これを飛ばすと関連線だけが例外なく消える。
        "function edgesByName",
        # 参照検査 (I-ER-REF / I-REL-ISO) が読む宣言の運搬。消えると .html は
        # 参照を素通りするが、検査は「指摘なし」で緑を返すので欠落が見えない。
        "function declarationAttr",
        'data-srg-declaration="${escapeHtml(JSON.stringify(decl))}"',
    ),
    # ビジュアルの縦寸を vh 固定でなく flex の残余割当で決める上書き。
    "scripts/style-builder.cjs": (
        'class*="slide-diagram"',
        "min-height: 0;",
        ".slider__content > h2,",
    ),
}
ADDITIVE_RUNTIME_CONTRACT = {
    "scripts/playwright-runtime.js": (
        "pluginLocalBrowsersPath",
        "PLAYWRIGHT_BROWSERS_PATH",
    ),
    "scripts/install-playwright-browser.js": (
        "configurePluginLocalPlaywright",
        "'install', 'chromium'",
    ),
    "scripts/verify-report-runtime.js": (
        "configurePluginLocalPlaywright",
        "./playwright-runtime.js",
    ),
    "scripts/verify-slides.js": (
        "verify-slides-playwright.js",
        "configurePluginLocalPlaywright",
    ),
    "scripts/verify-slides-playwright.js": (
        "configurePluginLocalPlaywright",
        "await import('playwright')",
        "[data-d3-fallback]",
    ),
}


def _validate_mermaid_pin(version: object, filename: str) -> list[str]:
    """Mermaid が range でなく安全床以上の exact SemVer pin か検査する。"""
    if not isinstance(version, str):
        return [f"{filename}: mermaid dependency missing"]
    match = _EXACT_SEMVER_RE.fullmatch(version)
    if not match:
        return [f"{filename}: mermaid must use an exact SemVer pin (got {version!r})"]
    if tuple(map(int, match.groups())) < _MIN_SAFE_MERMAID:
        floor = ".".join(map(str, _MIN_SAFE_MERMAID))
        return [f"{filename}: mermaid {version} is below security floor {floor}"]
    return []


def _validate_playwright_pin(version: object, filename: str) -> list[str]:
    """Playwright と対応 Chromium revision を決定論的に固定する。"""
    if not isinstance(version, str):
        return [f"{filename}: playwright dependency missing"]
    if not _EXACT_SEMVER_RE.fullmatch(version):
        return [
            f"{filename}: playwright must use an exact SemVer pin (got {version!r})"
        ]
    return []


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_additive_package(path: str, filename: str) -> list[str]:
    """C19 parity_scope.excluded_additive のsemantic gate。"""
    try:
        data = json.load(open(path, encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"{filename}: JSON invalid ({exc})"]
    if filename == "package.json":
        deps = data.get("dependencies", {})
        scripts = data.get("scripts", {})
        test = scripts.get("test", "")
        errors = _validate_mermaid_pin(deps.get("mermaid"), "package.json")
        errors.extend(_validate_playwright_pin(deps.get("playwright"), "package.json"))
        if not test or "no test specified" in test or "test-render-report.js" not in test or "test-mermaid-render.js" not in test:
            errors.append("package.json: npm test must execute real report/mermaid suites")
        if "test-playwright-runtime.js" not in test:
            errors.append("package.json: npm test must verify plugin-local Playwright")
        if "test-verify-slides.js" not in test:
            errors.append("package.json: npm test must verify Node Playwright slide capture")
        if scripts.get("postinstall") != "node scripts/install-playwright-browser.js":
            errors.append(
                "package.json: postinstall must restore plugin-local Playwright Chromium"
            )
        return errors
    root = data.get("packages", {}).get("", {}).get("dependencies", {})
    errors = _validate_mermaid_pin(root.get("mermaid"), "package-lock.json")
    mermaid_package = data.get("packages", {}).get("node_modules/mermaid")
    if not isinstance(mermaid_package, dict):
        errors.append("package-lock.json: node_modules/mermaid entry missing")
    elif mermaid_package.get("version") != root.get("mermaid"):
        errors.append(
            "package-lock.json: root mermaid pin and node_modules/mermaid version differ"
        )
    errors.extend(_validate_playwright_pin(root.get("playwright"), "package-lock.json"))
    playwright_package = data.get("packages", {}).get("node_modules/playwright")
    if not isinstance(playwright_package, dict):
        errors.append("package-lock.json: node_modules/playwright entry missing")
    elif playwright_package.get("version") != root.get("playwright"):
        errors.append(
            "package-lock.json: root playwright pin and node_modules/playwright version differ"
        )
    return errors


def _validate_token_contract(contract: dict[str, tuple[str, ...]], kind: str) -> list[str]:
    """指定ファイル群に必須トークンが残っているかだけを検査する共通 gate。"""
    errors: list[str] = []
    vendor = os.path.join(PLUGIN_ROOT, "vendor")
    for relpath, required_tokens in contract.items():
        path = os.path.join(vendor, relpath)
        if not os.path.isfile(path):
            errors.append(f"vendor/{relpath}: required {kind} file missing")
            continue
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        for token in required_tokens:
            if token not in text:
                errors.append(f"vendor/{relpath}: {kind} contract token missing: {token}")
    return errors


def validate_local_fork() -> list[str]:
    """図解品質のための意図的ローカル fork の semantic gate。"""
    return _validate_token_contract(ADDITIVE_LOCAL_FORK, "local fork")


def validate_local_fork_manifest(manifest: dict[str, object]) -> list[str]:
    """実装側のlocal fork集合がmanifestの宣言から増減していないか検査する。"""
    declared = manifest.get("local_fork_managed")
    if not isinstance(declared, dict):
        return ["vendor-digest-manifest.json: local_fork_managed object missing"]
    declared_paths = {key.removeprefix("vendor/") for key in declared if key != "note"}
    implemented_paths = set(ADDITIVE_LOCAL_FORK)
    errors: list[str] = []
    for path in sorted(implemented_paths - declared_paths):
        errors.append(f"vendor/{path}: local fork missing from manifest")
    for path in sorted(declared_paths - implemented_paths):
        errors.append(f"vendor/{path}: manifest local fork has no semantic contract")
    for key, entry in declared.items():
        if key == "note":
            continue
        if not isinstance(entry, dict) or not entry.get("owner") or not entry.get("gates"):
            errors.append(f"{key}: local fork requires owner and gates")
    return errors


def validate_additive_runtime() -> list[str]:
    """Plugin-local browser bootstrap/runtime wiring の semantic gate。"""
    errors: list[str] = []
    vendor = os.path.join(PLUGIN_ROOT, "vendor")
    for relpath, required_tokens in ADDITIVE_RUNTIME_CONTRACT.items():
        path = os.path.join(vendor, relpath)
        if not os.path.isfile(path):
            errors.append(f"vendor/{relpath}: required additive runtime file missing")
            continue
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        for token in required_tokens:
            if token not in text:
                errors.append(f"vendor/{relpath}: runtime contract token missing: {token}")
    return errors


def main() -> int:
    if not os.path.exists(MANIFEST):
        print(f"FAIL: manifest not found: {MANIFEST}", file=sys.stderr)
        return 1
    manifest = json.load(open(MANIFEST, encoding="utf-8"))

    total = ok = missing = mismatch = additive = forked = 0
    # ADDITIVE_LOCAL_FORK の key は vendor/ 相対。manifest 側の display と突合する
    fork_targets = {f"vendor/{relpath}" for relpath in ADDITIVE_LOCAL_FORK}
    for subtree in manifest.get("subtrees", []):
        target = SUBTREE_TARGETS.get(subtree["source"])
        if target is None:
            print(f"FAIL: unmapped manifest subtree source: {subtree['source']}", file=sys.stderr)
            return 1
        for filename, digest in subtree.get("files", {}).items():
            total += 1
            path = os.path.join(PLUGIN_ROOT, target, filename)
            display = f"{target}{filename}"
            if not os.path.exists(path):
                missing += 1
                print(f"MISSING {display}", file=sys.stderr)
            elif display in fork_targets:
                # byte 比較の対象外。実体の検査は validate_local_fork がまとめて行う
                ok += 1
                forked += 1
            elif filename in ADDITIVE_PACKAGE_FILES:
                errors = validate_additive_package(path, filename)
                if errors:
                    mismatch += 1
                    for error in errors:
                        print(f"MISMATCH {display}: {error}", file=sys.stderr)
                else:
                    ok += 1
                    additive += 1
            elif sha256(path) != digest:
                mismatch += 1
                print(f"MISMATCH {display}", file=sys.stderr)
            else:
                ok += 1

    for error in (
        validate_local_fork_manifest(manifest)
        + validate_local_fork()
        + validate_additive_runtime()
    ):
        mismatch += 1
        print(f"MISMATCH {error}", file=sys.stderr)

    result = "PASS" if (missing == 0 and mismatch == 0) else "FAIL"
    print(
        f"vendor integrity: pinned={total} ok={ok} "
        f"additive-package={additive} additive-runtime={len(ADDITIVE_RUNTIME_CONTRACT)} "
        f"local-fork={len(ADDITIVE_LOCAL_FORK)}(pinned-entries={forked}) "
        f"missing={missing} mismatch={mismatch} -> {result}"
    )
    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
