"""lint-contract-drift.py のテスト。

(1) 現在の plugin 実体に対し drift ゼロ (回帰ガード: prose↔code の乖離を再導入したら赤)。
(2) 4 チェックの検出能 (合成入力・helper 単体)。
(3) false-positive 非発火 (data-ink 比のような可視化ドメイン用語を属性と誤認しない)。
"""
from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

_PLUGIN_ROOT = Path(__file__).resolve().parent.parent
_SCRIPT = _PLUGIN_ROOT / "scripts" / "lint-contract-drift.py"


def _load():
    spec = importlib.util.spec_from_file_location("lint_contract_drift_mod", _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mod = _load()


# --- (1) 回帰ガード: 現行実体の drift は既知の 1 件だけ ---------------------------

# 既知の未解決 drift。ここは「直せないもの置き場」ではなく**期限付きの台帳**で、
# 完全一致で照合する。新しい drift が増えても、ここの 1 件が直っても落ちる。
# 直したら必ずこの表から消すこと (残すと次の drift をここが吸ってしまう)。
#
# 台帳の鍵は (check, where, 欠けている変数名) まで含める。(check, where) だけだと
# 「同じ文書の別の変数が新たに欠けた」場合に既知エントリが吸ってしまい、
# ここが埋葬地になる。

# 分類 A: 経路ごとに定義の有無が割れている色名変数のカスケード。theme-style.md の §2 が自ら
# 「色相名の 6 変数は現在どこにも定義がない (生成器も生成区間も出していない)」と
# 明記しており、この検査器の指摘はその文書自身の分析と一致する。
#
# 2026-08-14 再測定: exec-visual の theme-style.md 再編で、和名系 (--wave-blue /
# --sakura-pink / --autumn-yellow / --spring-violet / --wave-aqua / --fuji-gray) は
# 全滅した。theme-style.md / icons.md / layout-visual.md / print-layout.md /
# slide-interactions.md / slide-types-basic.md / slide-types-extended.md の 7 本が
# 台帳から消えている (12 件 -> 5 件)。
#
# 残る --accent-*-vivid 5 件の性質を 2026-08-14 に exec-visual が測定した。**変数が
# 存在しないのではない。** 定義は vendor/assets/src/styles/variables.css:61-65 にあり、
# render-report.js:182-186 が 5 つとも var(--ink) へ再定義したうえで多数箇所から参照し、
# render-slide.cjs:484-504 の V8_COLOR_VAR にも写像がある。したがって
# 「文書だけが存在しない変数を規定している」という別種の欠陥ではなく、6 色相と同じ類型。
#
# 欠けているのは **hand-slide 経路の生成器がこの 5 つを :root へ出していない**という
# 一点で、上の 5 エントリは全て経路 hand-slide の指摘。閉じ方は (a) hand-slide の
# 生成器に定義を足す (b) 参照側の .md を var(--x, <実値>) にする のどちらかで、
# 「存在しない変数だから消す」ではない。ここを取り違えると、実コードが使っている
# 変数を文書から削る方向へ働く。
#
# 落とす順序: exec-genome が svg-kit.cjs へ 6 色定義を入れる作業を持っており、同じ形で
# hand-slide 側も片付く見込みがある。ただし**片付く前提で先に消さないこと。**定義が
# 実際に入ったことを測ってから落とす。
#
# 併記 (2026-08-14 時点の観察。統合はしていない): この 5 件は「名前の数と値の数が
# 合っていない」という 1 つの性質の一面で、同じ性質が今日 3 層で独立に出ている。
#   - パレット層: report 経路で --accent-*-vivid 5 名が var(--ink) の 1 値へ潰れている
#   - 面の層: --fg-dim と --fuji-gray がどちらも #6A6A68 (計 1169 件)
#   - 図の層: state-golden#svg1 の D24 (2 名が同じ見た目に落ちる)
# 台帳としては別エントリのままにしてあるが、1 件ずつ潰すと 3 回同じ判断をすることに
# なるので、後で扱うときはここを起点にすること。
#
# 減ったら必ずここも減らすこと。
#
# 2026-08-14 に 1 件減った (5 件 -> 4 件)。agenda-navigation.md:44 が
# `--accent-*-vivid` という**総称の記述**に書き換わり、個別の 5 名を var() で
# 参照しなくなったため。凍結が禁じているのは「片付く見込みを理由に先に消すこと」で、
# 指摘が実際に出なくなったものを残すのは別の話 (残せば台帳が実体と食い違う)。
# 書き換え後の本文は「hand-slide 経路の :root には定義が無い」と記録しており、
# 上の分析と一致する。残る 4 件は測って消えるまで動かさない。
_GAP_PALETTE = {
    ("css-var-fallback", "references/design-quality-guide.md",
     ("--accent-aqua-vivid", "--accent-blue-vivid", "--accent-pink-vivid",
      "--accent-violet-vivid")),
    ("css-var-fallback", "references/slide-design-patterns.md",
     ("--accent-aqua-vivid", "--accent-pink-vivid")),
    ("css-var-fallback", "references/spec-registry.md",
     ("--accent-aqua-vivid",)),
    ("css-var-fallback",
     "skills/run-slide-report-generate/references/ui-quality-checklist.md",
     ("--accent-blue-vivid",)),
}

# 分類 B: 生成器が :root へ流していない変数。2026-08-14 に 2 件とも解消して空。
# どちらも CONST_010 の CSS 例の中にしか無く、repo 内に定義する生成器も読む検査器も
# 無かった。出荷済み deck 58 本を走査しても使用は 0 本で、.qr-img を持つ 2 本は
# CONST_010 が禁じている vh (18vh / 26vh)。すなわち「値が未決定の規範」ではなく
# 「一度も効いたことのない規範」だった。閉じ方が 2 件で違うので両方残す。
#
# --stage-h-mm: 新設不要だった。style-builder.cjs の @media print が
#   :root { --stage-h: 210mm } を出すので、印刷側でも --stage-h がそのまま mm に
#   解決する。足すべきトークンではなく消すべき別名で、CONST_010 の印刷用ブロックごと
#   削除した (画面用の 1 行が両媒体で成立する)。なお frame-contract の print_skeleton
#   節 (stage_height_mm 167.06) と style-builder の @media print (210mm full-bleed) は
#   矛盾ではない。前者の読み手は build-slide-skeleton-css.py /
#   validate-slide-skeleton.py のひな形経路だけで、印刷契約は SR-7-11 / SR-7-12 が
#   言うとおり経路ごとに別物。
# --qr-max-ratio: :root へ出す経路を新設せず、CSS 例を var(--qr-max-ratio, 0.26) の
#   フォールバック形にして閉じた。値の正本は frame-contract の
#   read_image.max_height_ratio 1 箇所で、文書側の 0.26 はその写し。写しが正本から
#   離れたら contract-qr-ratio が落とす (だから写しを許した)。値は勘ではなく出荷実績
#   から読んだ上限で、16:9 では --stage-h == 100vh なので既存 2 本の 18vh / 26vh =
#   比 0.18 / 0.26。下限は端末とカメラの性質で repo の中に無いため持たない。
#
# 空集合を残すのは、次に同種の穴が空いたときの置き場と上の記録のため。
_GAP_UNOWNED: set[tuple] = set()

# 分類 C: 廃止済みの概念への死んだ参照。持ち主を作ってはならない (作れば
# 廃止したものが復活する)。新配色 (インク・オン・ペーパー) で影は使わない方針が
# 確定しており、render-report.js 側は none 化・theme-style.md 側は削除済み。
# 直し方は参照側の削除で、担当は exec-docs。2026-08-14 に削除が入り空になった。
_GAP_DEPRECATED: set[tuple] = set()

# 分類 D: どの経路にも属さない :root 定義 (孤児定義)。2026-08-14 に検査 K を入れて
# 可視化した 3 件。どれも「読んだ人が、どの生成器も出していない第 2 の正本を引く」形。
#
# ここに載せる = 検査が鳴り続ける状態を承知で置く、という意味。黙らせたいなら
# _VAR_ROUTE_SOURCES / _NON_ROUTE_DEFINERS のどちらかへ根拠を書いて移すことになるが、
# **根拠が書けないものを移して黙らせないこと。**その 2 つは登録すれば黙る仕組みなので、
# 中身の無い登録を許すと登録簿自体が埋葬地になる。
#
# print-styles.css (3 個): 孤児で確定 (2026-08-14 実測)。print-layout.md /
#   html-generation-rules.md / full-image-deck-method.md / image-format-guide.md /
#   unit-system.md の 5 本が「これを使う」と読み手に指示しているが、**文書は意図であって
#   実態ではない。**出荷デッキ・goldens・vendor/assets の html/css 143 本を走査して
#   `print-styles` を読み込んでいるものは 0 本、生成器側の参照も 0 だった。
#   共通テンプレート区分 (pagination.css) との違いはここで、pagination.css は
#   style-builder.cjs:913 が styles.css へ結合し、出荷デッキ 3 本に実物が入っている
#   (同じ走査で 7 本ヒット)。theme-style.md 等を経路 hand-slide に入れているのは
#   **文書が実装を兼ねている**からで、別ファイルを指しているだけの本件とは違う。
#   「5 本の文書が指しているのに誰も読み込んでいない」は、読み手が引ける値が実装に
#   存在しない状態そのもので、むしろ鳴らすべき度合いが高い。
# slide-template-single.html (33 個): コードからの参照は digest のみ。
# variables.css (59 個): 旧 Lotus パレット。現行のどの生成器も読まない。--fg: #43436c 等が
#   現行値の第 2 の正本になっている。**扱いは T7 (team-lead 持ち) と重なるので、
#   ここでは鳴らすところまで。消すかどうかはこの台帳の担当ではない。**
_GAP_ORPHAN = {
    ("orphan-var-definer", "vendor/assets/print-styles.css",
     ("--accent", "--ink", "--surface")),
    ("orphan-var-definer", "vendor/assets/slide-template-single.html",
     ("--accent", "--autumn-yellow", "--bg-card", "--bg-dark", "--bg-dim")),
    ("orphan-var-definer", "vendor/assets/src/styles/variables.css",
     ("--accent-aqua-vivid", "--accent-blue-vivid", "--accent-pink-vivid",
      "--accent-violet-vivid", "--accent-yellow-vivid")),
}

_KNOWN_GAPS = _GAP_PALETTE | _GAP_UNOWNED | _GAP_DEPRECATED | _GAP_ORPHAN

_VAR_IN_MSG_RE = re.compile(r"--[a-z0-9-]+")


def _gap_key(f: dict) -> tuple:
    head = f["message"].split("。")[0]
    return (f["check"], f["where"], tuple(sorted(set(_VAR_IN_MSG_RE.findall(head)))))


def test_current_plugin_drift_is_only_the_known_gaps():
    findings = mod.run_checks(_PLUGIN_ROOT)
    got = {_gap_key(f) for f in findings}
    assert got == _KNOWN_GAPS, "contract-drift の増減: " + json.dumps(findings, ensure_ascii=False)


# --- (2) helper: data-* 属性抽出は backtick/属性構文のみ (false-positive 排除) ---

def test_cited_data_attrs_extracts_backtick_and_attr_syntax():
    text = "`data-reading-order` と `data-focal=\"x,y\"` を使い、data-attr=1 も拾う。"
    got = mod._cited_data_attrs(text)
    assert "data-reading-order" in got
    assert "data-focal" in got
    assert "data-attr" in got


def test_cited_data_attrs_ignores_prose_domain_term():
    # 『data-ink 比』(Tufte 用語) は HTML 属性でないので拾わない。
    text = "定量は data-ink 比を意識し過剰装飾を避ける。"
    assert mod._cited_data_attrs(text) == set()


# --- (2) helper: 閾値抽出は DEFAULT_THRESHOLDS と一致 ---------------------------

def test_load_thresholds_matches_validator():
    th = mod._load_thresholds(_PLUGIN_ROOT)
    # 主要キーが抽出できる。
    assert th.get("doc_highlight_budget") == 24
    assert th.get("monotone_block_floor") == 6
    assert "max_visuals_per_section" in th


# --- (2) 検出能: 合成 root で 4 チェックが drift を掴む -------------------------

def _mk_min_plugin(tmp_path: Path) -> Path:
    """render/validator/schema/prose の最小 clean tree を作る (drift ゼロが既定)。"""
    root = tmp_path / "plg"
    (root / "vendor" / "scripts").mkdir(parents=True)
    (root / "scripts").mkdir(parents=True)
    (root / "schemas").mkdir(parents=True)
    (root / "references").mkdir(parents=True)
    (root / "skills" / "run-slide-report-generate" / "references").mkdir(parents=True)
    (root / "skills" / "run-slide-report-generate" / "prompts").mkdir(parents=True)
    # render: data-emphasis のみ emit / report-throughline を生成
    (root / "vendor" / "scripts" / "render-report.js").write_text(
        'const a = ` data-emphasis="${e}" `;\nfunction f(){ return "report-throughline"; }\n// layout.grid layout.emphasisZone\n',
        encoding="utf-8",
    )
    # validator: report-throughline を fidelity 検査 / DEFAULT_THRESHOLDS / role 方針2集合(SSOT)
    (root / "scripts" / "validate-report-visual.py").write_text(
        'DEFAULT_THRESHOLDS = {\n    "doc_highlight_budget": 24,\n}\n'
        '_NARRATIVE_REQUIRED_ROLES = {\n    "analysis", "argument",\n}\n'
        '_NARRATIVE_OPTIONAL_ROLES = {\n    "reference", "summary",\n}\n'
        'x = "report-throughline" not in html\n',
        encoding="utf-8",
    )
    # schema: placement grid(消費) + zones(advisory)
    schema = {"$defs": {"placement": {"properties": {
        "grid": {"type": "string", "description": "レイアウト"},
        "emphasisZone": {"type": "string", "description": "強調"},
        "zones": {"type": "array", "description": "advisory メタ"},
    }}}}
    (root / "schemas" / "report-structure.schema.json").write_text(
        json.dumps(schema, ensure_ascii=False), encoding="utf-8"
    )
    (root / "references" / "report-writing-rules.md").write_text(
        "doc_highlight_budget=24 を守る。`data-emphasis` を使う。\n", encoding="utf-8"
    )
    # references §6.1 role→narrative 表 (validator の2集合と一致させる)
    (root / "references" / "report-narrative-logic.md").write_text(
        "### 6.1 role\n"
        "| 群 | role |\n|---|---|\n"
        "| **期待** | `analysis` `argument` |\n"
        "| **不要** | `reference` |\n"
        "| **文脈依存** | `summary` |\n",
        encoding="utf-8",
    )
    # constant-parity は「作図定数の実体 ↔ 検査器の定数」を突合するので、
    # 合成できない (両者が一致していることに意味がある) 2 ファイルは実物を複製する。
    # 合成 tree に置かないと「対象ファイルが読めない」で陰性対照が赤くなり、
    # 検出能テストの基準線が失われる。
    # check G は経路ごとに :root の正本を読む。1 経路でも欠けると「抽出できない」で
    # 陰性対照が赤くなるので、5 経路すべての正本を実物から複製する。
    for rel in (
        "vendor/scripts/svg-kit.cjs",
        "vendor/scripts/svg-builder.cjs",
        "vendor/scripts/style-builder.cjs",
        "vendor/scripts/html-scaffold.js",
        "scripts/build-slide-skeleton-css.py",
        "scripts/build-slide-skeletons.py",
        "references/theme-style.md",
        "skills/run-slide-report-generate/references/html-generation-rules.md",
        "scripts/validate-svg-diagram.py",
        "scripts/validate-report-layout.js",
        "references/spec-registry.md",
        "assets/slide-templates/frame-contract.json",
    ):
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_bytes((_PLUGIN_ROOT / rel).read_bytes())
    # render-report.js と report-narrative-logic.md は他検査のために合成した実体を
    # 保ちつつ、constant-parity が読む定数だけ実物から足す (追記は phantom 検査を
    # 弱めない: あの検査は「散文が語るのに emit されない属性」を見る片方向)。
    p = root / "vendor" / "scripts" / "render-report.js"
    p.write_text(
        p.read_text(encoding="utf-8") + "\n"
        + (_PLUGIN_ROOT / "vendor" / "scripts" / "render-report.js").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    return root


def test_detects_phantom_data_attr(tmp_path):
    root = _mk_min_plugin(tmp_path)
    (root / "references" / "report-bad.md").write_text("`data-focal-y` を反映する。\n", encoding="utf-8")
    findings = mod.run_checks(root)
    assert any(f["check"] == "data-attr-phantom" and "data-focal-y" in f["message"] for f in findings)


def test_detects_threshold_drift(tmp_path):
    root = _mk_min_plugin(tmp_path)
    (root / "references" / "report-bad.md").write_text("doc_highlight_budget=99 が上限。\n", encoding="utf-8")
    findings = mod.run_checks(root)
    assert any(f["check"] == "threshold-drift" for f in findings)


def test_detects_fidelity_orphan(tmp_path):
    root = _mk_min_plugin(tmp_path)
    src = (root / "scripts" / "validate-report-visual.py").read_text(encoding="utf-8")
    (root / "scripts" / "validate-report-visual.py").write_text(
        src + '\ny = "report-orphan-cls" not in html\n', encoding="utf-8"
    )
    findings = mod.run_checks(root)
    assert any(f["check"] == "fidelity-orphan" and "report-orphan-cls" in f["message"] for f in findings)


def test_detects_placement_dead_field(tmp_path):
    root = _mk_min_plugin(tmp_path)
    schema = json.loads((root / "schemas" / "report-structure.schema.json").read_text(encoding="utf-8"))
    schema["$defs"]["placement"]["properties"]["bogusZone"] = {"type": "string", "description": "未消費"}
    (root / "schemas" / "report-structure.schema.json").write_text(
        json.dumps(schema, ensure_ascii=False), encoding="utf-8"
    )
    findings = mod.run_checks(root)
    assert any(f["check"] == "placement-dead-field" and "bogusZone" in f["message"] for f in findings)


def test_detects_role_policy_drift(tmp_path):
    root = _mk_min_plugin(tmp_path)
    # reference §6.1『期待』群から argument を削除 → validator の REQUIRED と不一致。
    p = root / "references" / "report-narrative-logic.md"
    p.write_text(p.read_text(encoding="utf-8").replace("`analysis` `argument`", "`analysis`"), encoding="utf-8")
    findings = mod.run_checks(root)
    assert any(f["check"] == "role-policy-drift" for f in findings)


def test_role_policy_reference_matches_validator_on_real_plugin():
    req, opt = mod._load_role_sets(_PLUGIN_ROOT)
    groups = mod._reference_role_groups(_PLUGIN_ROOT)
    assert groups.get("expected") == req
    assert (groups.get("optional_strict", set()) | groups.get("context", set())) == opt


def test_min_plugin_is_clean(tmp_path):
    # 合成 clean tree は drift ゼロ (検出能テストの陰性対照)。
    # ただし check G の経路正本 (theme-style.md 等) は実物を複製して持ち込むので、
    # 実物側に残る css-var-fallback はここでは見ない (見ると他所の編集で揺れる)。
    # 実物側は test_current_plugin_drift_is_only_the_known_gap が受け持つ。
    #
    # orphan-var-definer も同じ理由で外す。この検査は _VAR_ROUTE_SOURCES に載る
    # 実ファイルが存在することを見るが、合成 tree はそのうち 2 本しか持たない
    # (constant-parity のために複製した分だけ)。合成 tree に無いのは合成の都合であって
    # 登録簿の欠陥ではない。**この検査の陰性対照は別に置いてある**:
    # 経路登録が実体を伴うことは test_every_registered_route_source_exists_and_emits_on_the_real_plugin、
    # 登録で黙ること・黙らないことは test_registering_as_a_route_silences_it 以下の反例が見る。
    got = [f for f in mod.run_checks(_mk_min_plugin(tmp_path))
           if f["check"] not in ("css-var-fallback", "orphan-var-definer")]
    assert got == [], json.dumps(got, ensure_ascii=False)


# --- (2) H: パレット値の散文↔SPEC.colors 一致 -------------------------------------

def test_detects_palette_drift(tmp_path):
    # --fg-muted は SPEC.colors のキー名 (inkMuted) と綴りが違う。ここを題材にすると
    # 「キー名から変数名を推測する」実装へ戻した瞬間に、このテストが落ちる。
    root = _mk_min_plugin(tmp_path)
    (root / "references" / "palette-note.md").write_text(
        "# 配色\n\n```css\n:root {\n  --fg-muted: #7AA89F;\n}\n```\n", encoding="utf-8"
    )
    findings = mod.run_checks(root)
    assert any(f["check"] == "palette-drift" and "--fg-muted" in f["message"] for f in findings)


def test_palette_variant_marker_suppresses_intentional_difference(tmp_path):
    # 上書き例・別テーマのように「わざと違う値」を載せる面は、理由付きマーカで除外できる。
    root = _mk_min_plugin(tmp_path)
    (root / "references" / "palette-note.md").write_text(
        "# 配色\n\n<!-- palette-variant: 上書き例 -->\n\n"
        "```css\n:root {\n  --fg-muted: #7AA89F;\n}\n```\n", encoding="utf-8"
    )
    assert not [f for f in mod.run_checks(root) if f["check"] == "palette-drift"]


# --- (2) G: CSS 変数の照合は「経路ごとの集合」で行う -------------------------------
#
# 個数照合だった頃は、決定論 slide の font-size 4 種と report の 5 種の和集合が
# ちょうど 7 種になり、ひな形 slide の 7 種と個数が一致して緑になっていた。
# 以下は「名前が入れ替わっても緑」を潰せているかを両方向で見る。

def _g(root: Path, rel: str = "references/route-note.md") -> list[dict]:
    """合成した文書 1 件についての css-var-fallback finding だけを返す。

    合成 tree は経路の正本 (theme-style.md 等) を実物から複製するので、実物側の
    未解決 drift をそのまま持ち込む。検出能テストがそれに引きずられると、
    他所の編集で緑赤が揺れて何を測っているか分からなくなるため、対象文書で絞る。
    実物側の drift は test_current_plugin_drift_is_only_the_known_gap が見る。
    """
    return [f for f in mod.run_checks(root)
            if f["check"] == "css-var-fallback" and f["where"] == rel]


def _doc(root: Path, body: str, rel: str = "references/route-note.md") -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")


def test_var_matched_against_declared_route_only(tmp_path):
    # --fs-lead は決定論 slide にしか無い。手書き経路を名乗る文書が引けば落ちる。
    root = _mk_min_plugin(tmp_path)
    _doc(root, "<!-- css-route: hand-slide -->\n\n`font-size: var(--fs-lead);`\n")
    got = _g(root)
    assert any("--fs-lead" in f["message"] and "hand-slide" in f["message"] for f in got)


def test_same_var_passes_under_its_own_route(tmp_path):
    # 逆方向。同じ --fs-lead でも決定論経路を名乗れば通る。片方向だけの検査だと
    # 「常に赤」を返す実装でも上のテストが通ってしまうので、対で置く。
    root = _mk_min_plugin(tmp_path)
    _doc(root, "<!-- css-route: det-slide -->\n\n`font-size: var(--fs-lead);`\n")
    assert not [f for f in _g(root) if "--fs-lead" in f["message"]]


def test_routes_are_not_merged_into_one_union(tmp_path):
    # --fs-subheading は手書き slide と report にあり、決定論 slide には無い。
    # 全経路を 1 集合へ混ぜた実装だと「どこかにあるので緑」になる。
    root = _mk_min_plugin(tmp_path)
    _doc(root, "<!-- css-route: det-slide -->\n\n`font-size: var(--fs-subheading);`\n")
    assert any("--fs-subheading" in f["message"] for f in _g(root))


def test_undeclared_route_is_fail_closed(tmp_path):
    # 経路が判定できない文書は、和集合へ退避せず落とす。
    root = _mk_min_plugin(tmp_path)
    _doc(root, "# 宣言なし\n\n`color: var(--fs-lead);`\n")
    assert any("経路の宣言が無いまま" in f["message"] for f in _g(root))


def test_unknown_route_name_is_reported(tmp_path):
    root = _mk_min_plugin(tmp_path)
    _doc(root, "<!-- css-route: nonexistent-route -->\n\n`color: var(--fs-lead);`\n")
    assert any("未知の経路名" in f["message"] for f in _g(root))


def test_route_declaration_is_positional(tmp_path):
    # 1 文書に複数経路の実例が載ることがある。宣言は位置で効き、次の宣言まで有効。
    # どの var() も照合先は 1 経路だけ (ここでも和集合は作らない)。
    root = _mk_min_plugin(tmp_path)
    _doc(root,
         "<!-- css-route: det-slide -->\n\n`var(--fs-lead)`\n\n"
         "<!-- css-route: hand-slide -->\n\n`var(--fs-subheading)`\n")
    assert not _g(root)


def test_skills_references_are_in_scope(tmp_path):
    # plugin root の references/*.md しか見ていなかった頃、手書き経路の記述が
    # skills/*/references/ にあるため丸ごと検査圏外だった。
    rel = "skills/run-slide-report-generate/references/deep/nested-rule.md"
    root = _mk_min_plugin(tmp_path)
    _doc(root, "<!-- css-route: det-slide -->\n\n`var(--fs-subheading)`\n", rel=rel)
    assert _g(root, rel)


def test_fallback_form_is_accepted(tmp_path):
    # `var(--x, <実値>)` は未定義でも解決できるので、経路に無くても落とさない。
    root = _mk_min_plugin(tmp_path)
    _doc(root, "<!-- css-route: det-slide -->\n\n`var(--fs-subheading, 1.5rem)`\n")
    assert not _g(root)


def test_palette_check_allows_svg_kit_verbatim_fallback(tmp_path):
    # 図解作例は svg-kit.cjs の綴りをそのまま写す必要がある (D10 が許可色をそこから
    # 実行時抽出するため)。:root 実値との差は vendor 側 1 件の問題で、作例ごとに数える意味がない。
    # 逐語の組は sandbox 側で作る。vendor の現在値を前提にすると、パレット改訂で
    # 「差がある組」が消えた日にこの検査が黙って空振りする (緑のまま無効化)。
    root = _mk_min_plugin(tmp_path)
    kit = root / "vendor" / "scripts" / "svg-kit.cjs"
    kit.write_text(
        kit.read_text(encoding="utf-8") + "\nconst LEGACY = 'var(--fg-muted, #54546D)';\n",
        encoding="utf-8",
    )
    (root / "references" / "palette-note.md").write_text(
        '# 図解\n\n<text fill="var(--fg-muted, #54546D)">x</text>\n', encoding="utf-8"
    )
    assert not [f for f in mod.run_checks(root) if f["check"] == "palette-drift"]


# --- (2) I: 経路専有の契約節を集合外が読んでいないか -------------------------------

def _rogue(root: Path, body: str, rel: str = "scripts/rogue-loader.py") -> list[dict]:
    (root / rel).parent.mkdir(parents=True, exist_ok=True)
    (root / rel).write_text(body, encoding="utf-8")
    return [f for f in mod.section_reader_findings(root) if f["where"] == rel]


def test_out_of_set_reader_of_print_section_fails(tmp_path):
    # print_skeleton 節はひな形経路専有 (297x167.06mm のレターボックス版面)。決定論
    # エンジンの印刷は 297x210mm full-bleed で別物なので、集合外が読んだら落とす。
    root = _mk_min_plugin(tmp_path)
    got = _rogue(root, 'c = load("assets/slide-templates/frame-contract.json")\nh = c["print_skeleton"]["stage_height_mm"]\n')
    assert len(got) == 1, json.dumps(got, ensure_ascii=False)
    assert got[0]["check"] == "contract-section-reader"


def test_out_of_set_reader_is_detected_for_every_declared_section(tmp_path):
    # print_skeleton だけ守って chrome / media が素通りする状態を作らない。
    root = _mk_min_plugin(tmp_path)
    for section in mod._SECTION_READERS:
        got = _rogue(root, f'p = "assets/slide-templates/frame-contract.json"\nv = c["{section}"]\n')
        assert len(got) == 1, f"{section}: " + json.dumps(got, ensure_ascii=False)


def test_section_check_ignores_files_that_do_not_load_the_contract(tmp_path):
    # 契約のパスを綴っていないファイルは節を読めない。ここを広げると chrome のような
    # 普遍名が無関係なコードで大量に当たり、検査が使えなくなる。
    root = _mk_min_plugin(tmp_path)
    assert _rogue(root, 'v = c["print_skeleton"]\n') == []


def test_section_check_ignores_same_named_language_features(tmp_path):
    # print( や @media print は節参照ではない。改名前は print 節がこれと同名で、
    # 名前が普遍的であること自体が偽陽性の温床だった (改名の動機の 1 つ)。
    root = _mk_min_plugin(tmp_path)
    body = ('p = "assets/slide-templates/frame-contract.json"\n'
            'print("done")\n'
            'css = "@media print { .x { display: none } }"\n')
    assert _rogue(root, body) == []


def test_declared_reader_of_print_section_passes(tmp_path):
    # 集合内のファイルは同じ書き方でも通る (集合が効いていることの対照)。
    root = _mk_min_plugin(tmp_path)
    rel = "scripts/build-slide-skeleton-css.py"
    assert rel in mod._SECTION_READERS["print_skeleton"]
    assert [f for f in mod.section_reader_findings(root) if f["where"] == rel] == []


# --- contract-qr-ratio (CONST_010) の検出能 ---------------------------------
#
# この検査は「文書側の写しが正本から離れられない」ことを担保するために入れた。
# 写しを許した以上、離れたときに落ちることを示せないなら、写しを許した理由が消える。

_QR_DOC = "references/qr-note.md"


def _qr(root: Path, body: str, rel: str = _QR_DOC) -> list[dict]:
    _doc(root, body, rel)
    return [f for f in mod.qr_ratio_findings(root) if f["where"] == rel]


def _qr_ratio(root: Path) -> float:
    c = json.loads((root / mod._CONTRACT_PATH).read_text(encoding="utf-8"))
    return float(c["read_image"]["max_height_ratio"])


def test_qr_fallback_that_drifts_from_the_contract_fails(tmp_path):
    root = _mk_min_plugin(tmp_path)
    assert _qr_ratio(root) != 0.4
    got = _qr(root, ".qr-img { width: calc(var(--stage-h) * var(--qr-max-ratio, 0.4)); }\n")
    assert len(got) == 1, json.dumps(got, ensure_ascii=False)
    assert got[0]["check"] == "contract-qr-ratio"


def test_qr_fallback_equal_to_the_contract_passes(tmp_path):
    # 正本を読んで組み立てた写しは通る (上の反例と対になる基準線)。
    root = _mk_min_plugin(tmp_path)
    ratio = _qr_ratio(root)
    assert _qr(root, f".qr-img {{ width: calc(var(--stage-h) * var(--qr-max-ratio, {ratio})); }}\n") == []


def test_qr_vh_unit_fails(tmp_path):
    # CONST_010 が禁じている vh。出荷済み deck 2 本が 18vh / 26vh で書かれており、
    # 実際に起きた形をそのまま反例にする。
    root = _mk_min_plugin(tmp_path)
    got = _qr(root, "```css\n.qr-img { width: 26vh; }\n```\n")
    assert len(got) == 1, json.dumps(got, ensure_ascii=False)
    assert "vh" in got[0]["message"]


def test_qr_vh_check_is_scoped_to_read_image_lines(tmp_path):
    # 文書全体から vh を狩ると無関係な例まで巻き込む。.qr-img を含む行だけを見る。
    root = _mk_min_plugin(tmp_path)
    assert _qr(root, "```css\n.hero { height: 40vh; }\n```\n") == []


def test_qr_vh_in_prose_is_not_a_violation(tmp_path):
    # 「出荷済み deck が 18vh で書かれている」と record した文は違反ではない。
    # ここを落とすと、記録した側が記録を消して緑にする方向へ働く。
    root = _mk_min_plugin(tmp_path)
    assert _qr(root, "出荷済み deck の `.qr-img` 2 本は `18vh` / `26vh` で書かれている。\n") == []


def test_qr_check_is_fail_closed_when_the_contract_key_is_gone(tmp_path):
    # 正本が消えたら「突き合わせる相手が居ない」で落ちる。緑のまま素通りすると、
    # 写しだけが残って誰も見ていない上限を主張し続ける。
    root = _mk_min_plugin(tmp_path)
    p = root / mod._CONTRACT_PATH
    c = json.loads(p.read_text(encoding="utf-8"))
    del c["read_image"]
    p.write_text(json.dumps(c, ensure_ascii=False), encoding="utf-8")
    got = mod.qr_ratio_findings(root)
    assert len(got) == 1 and got[0]["check"] == "contract-qr-ratio", json.dumps(got, ensure_ascii=False)


def test_qr_rule_document_is_covered_by_the_check(tmp_path):
    # 実物の CONST_010 記述が検査対象 (_var_scan_targets) に入っていること。
    # 検出できる検査でも、規範を書いた文書を見ていなければ意味が無い。
    rel = "skills/run-slide-report-generate/references/layout-optimization-rules.md"
    assert rel in [p.relative_to(_PLUGIN_ROOT).as_posix()
                   for p in mod._var_scan_targets(_PLUGIN_ROOT)]
    assert "--qr-max-ratio" in (_PLUGIN_ROOT / rel).read_text(encoding="utf-8")


# --- orphan-var-definer (孤児定義) の検出能 -----------------------------------
#
# この検査は「登録すれば黙る」形をしている。黙らせる手段を足した以上、
#   (a) わざと 1 つずらしたら赤くなること
#   (b) わざと 1 つ揃えたら緑になること
# の両方を示せないなら、登録簿はただの埋葬地になる。
#
# 併せて逆向き (登録だけあって実体が無い / 何も出していない) も反例で押さえる。
# 片側だけだと「登録簿に書けば通る」ことだけが担保され、書いた内容が本当かは
# 誰も見ていない状態になる。

_ORPHAN_REL = "vendor/assets/x-theme.css"


def _orphan(root: Path, rel: str) -> list[dict]:
    return [f for f in mod.orphan_definer_findings(root) if f["where"] == rel]


def _mk_definer(root: Path, body: str, rel: str = _ORPHAN_REL) -> str:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    return rel


def test_unlisted_definer_is_reported(tmp_path):
    # わざとずらす: どの経路にも既知区分にも載せずに :root 定義を置く。
    root = _mk_min_plugin(tmp_path)
    rel = _mk_definer(root, ":root { --foo: #111111; --bar: 2rem; }\n")
    got = _orphan(root, rel)
    assert len(got) == 1, json.dumps(got, ensure_ascii=False)
    assert got[0]["check"] == "orphan-var-definer"
    assert "2 個" in got[0]["message"]


def test_registering_as_a_route_silences_it(tmp_path, monkeypatch):
    # わざと揃える (1): 経路として登録すれば黙る。
    root = _mk_min_plugin(tmp_path)
    rel = _mk_definer(root, ":root { --foo: #111111; }\n")
    monkeypatch.setitem(mod._VAR_ROUTE_SOURCES, "x-route", (rel,))
    assert _orphan(root, rel) == []


def test_recording_as_a_non_route_silences_it(tmp_path, monkeypatch):
    # わざと揃える (2): 生成物・共通テンプレート・検査器として根拠付きで置いても黙る。
    root = _mk_min_plugin(tmp_path)
    rel = _mk_definer(root, ":root { --foo: #111111; }\n")
    monkeypatch.setitem(mod._NON_ROUTE_DEFINERS, rel, "生成物。x-route 経路の出力")
    assert _orphan(root, rel) == []


def test_registered_route_source_that_emits_nothing_is_reported(tmp_path, monkeypatch):
    # 逆向き。登録簿が「出している」と主張しているのに 1 つも出していない。
    # 実際に build-slide-skeletons.py と svg-kit.cjs がこの状態だった (実測 defs=0)。
    root = _mk_min_plugin(tmp_path)
    rel = _mk_definer(root, "// CSS 変数は 1 つも出さない\nconst x = 1;\n",
                      rel="vendor/scripts/x-emitter.js")
    monkeypatch.setitem(mod._VAR_ROUTE_SOURCES, "x-route", (rel,))
    got = _orphan(root, rel)
    assert len(got) == 1, json.dumps(got, ensure_ascii=False)
    assert "1 つも" in got[0]["message"]


def test_registered_route_source_that_is_missing_is_reported(tmp_path, monkeypatch):
    # 逆向き。登録が実体を失っている (ファイルの改名・削除で起きる)。
    root = _mk_min_plugin(tmp_path)
    monkeypatch.setitem(mod._VAR_ROUTE_SOURCES, "x-route", ("vendor/scripts/gone.js",))
    got = _orphan(root, "vendor/scripts/gone.js")
    assert len(got) == 1, json.dumps(got, ensure_ascii=False)
    assert "存在しない" in got[0]["message"]


def test_cli_flag_help_is_not_a_definition(tmp_path):
    # 実測で当たった誤検出その 1。validate-structure.js のフラグ説明。
    # 規約が禁じているのは値がそこで定義されていることであって、
    # `--x:` という並びがファイルに出ることではない。
    root = _mk_min_plugin(tmp_path)
    rel = _mk_definer(root, 'console.log("  --strict : WARN を FAIL に格上げ");\n',
                      rel="vendor/scripts/x-cli.js")
    assert _orphan(root, rel) == []


def test_prose_in_a_comment_is_not_a_definition(tmp_path):
    # 実測で当たった誤検出その 2。pagination.js のコメント散文。
    root = _mk_min_plugin(tmp_path)
    rel = _mk_definer(root, "// --fit-t : 11.00 が消え、見出しが 45.78px から縮む\n",
                      rel="vendor/assets/x-note.js")
    assert _orphan(root, rel) == []


def test_tests_and_goldens_are_out_of_scope(tmp_path):
    # fixture の期待値は「定義」に見えるだけ。ここを見ると、反例テストを書くほど
    # 検査器が赤くなるという逆立ちした形になる。
    root = _mk_min_plugin(tmp_path)
    a = _mk_definer(root, ":root { --foo: #111111; }\n", rel="tests/test_x.py")
    b = _mk_definer(root, ":root { --foo: #111111; }\n",
                    rel="examples/diagram-goldens/x.html")
    assert _orphan(root, a) == []
    assert _orphan(root, b) == []


def test_documents_are_not_scanned_as_definers(tmp_path):
    # 文書は `<!-- css-route: -->` で自分の経路を宣言する別の仕組みに乗っている。
    # 両方で見ると同じ 1 件が 2 回鳴る。
    root = _mk_min_plugin(tmp_path)
    rel = _mk_definer(root, ":root { --foo: #111111; }\n", rel="references/x-theme.md")
    assert _orphan(root, rel) == []


def test_every_registered_route_source_exists_and_emits_on_the_real_plugin():
    # 実物の登録簿が実体を伴っていること。上の反例 2 本が守っている性質を、
    # 合成 tree ではなく出荷する側で確かめる。
    known = {rel for rels in mod._VAR_ROUTE_SOURCES.values() for rel in rels}
    got = [f for f in mod.orphan_definer_findings(_PLUGIN_ROOT) if f["where"] in known]
    assert got == [], json.dumps(got, ensure_ascii=False)


def test_intentional_per_route_value_difference_is_not_reported(tmp_path, monkeypatch):
    # 基準線。同名・異値は欠陥ではない (--fs-body は report で 1.0625rem、slide で
    # vw 基準。読み手は必ず自分の経路の値を引く)。実測でも素直に鳴らすと 205 変数中
    # 99 変数が該当し、そのほとんどが意図した経路差だった。ここが赤くなる実装は、
    # 正しく分けてある経路を 1 つに寄せる方向へ働く。
    root = _mk_min_plugin(tmp_path)
    a = _mk_definer(root, ":root { --fs-body: 1.0625rem; }\n", rel="vendor/scripts/x-a.js")
    b = _mk_definer(root, ":root { --fs-body: max(1.25vw, 14px); }\n",
                    rel="vendor/scripts/x-b.js")
    monkeypatch.setitem(mod._VAR_ROUTE_SOURCES, "x-a", (a,))
    monkeypatch.setitem(mod._VAR_ROUTE_SOURCES, "x-b", (b,))
    assert _orphan(root, a) == [] and _orphan(root, b) == []
