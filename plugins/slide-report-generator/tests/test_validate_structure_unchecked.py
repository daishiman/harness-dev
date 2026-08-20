"""validate-structure.js の「未検査」の扱いを固定する。

未検査（どの工程にも判定する実行体が無い規則）を PASS に混ぜると、緑が何を
保証しているのか読めなくなる。ここで固定するのは 4 点。

  1. 未検査が 0 件なら従来どおり PASS / exit 0（PASS_WITH_UNCHECKED を足した
     ことで通常経路の合否が変わっていないこと）
  2. 未検査が 1 件でもあれば PASS_WITH_UNCHECKED / exit 2 になり、「合格」と
     表示されないこと
  3. 常設の未検査が 0 件であること（下記）
  4. skip の kind が 3 種（deferred / not-applicable / no-checker）に分かれ、
     後段でも永久に見ないものが deferred へ溜まらないこと

2 を陰性対照だけで書くと「常に落ちる実装」と見分けが付かないので、未検査を 0 に
した骨格（陽性対照）も走らせて 1 と対にしている。

常設の未検査について: 現在は **0 件** である。2026-08-14 の午前に V-001（SR-4-03）を
deferred から no-checker へ移したが、同日中に scripts/validate-compare-ratio.mjs が
実行体として入り、deferred へ戻した。3 はその 0 件を固定する。

「実行体がある」を名前で書くと腐るので、ここでは**実体と 2 つの配線が揃っていること**を
見る（test_v001_has_a_wired_checker）。実行体が消えたり配線が外れたりしたら、V-001 は
また誰も見ていない規則へ戻るので、そのときに落ちる。
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
VALIDATOR = PLUGIN_ROOT / "vendor" / "scripts" / "validate-structure.js"
UTILS = PLUGIN_ROOT / "vendor" / "scripts" / "utils.js"
SCHEMA = PLUGIN_ROOT / "schemas" / "structure.schema.json"
FIXTURE = PLUGIN_ROOT / "vendor" / "schemas-fixtures" / "example-full.structure.json"

# 未検査を 1 件注入する差し込み位置。ここが動いたらテストを追随させる。
#
# 注入 ID は実在しない合成 ID を使う。実在 ID を借りると、その ID に実行体が付いた
# ときにテストの意味が「未検査の扱い」から「その規則の検査」へすり替わる。skip() は
# 未知 ID でも { sr: "?", desc: vid } へフォールバックするので、合成 ID で成立する。
ANCHOR = "  // ----- v8 拡張検証 -----"
INJECT = '  report.skip("V-TEST-UNCHECKED", "注入した未検査", "no-checker");\n' + ANCHOR

# 常設の未検査。実行体がどこにも無い規則をここへ足すのは最後の手段で、足したら
# 「誰も見ていない規則を抱えたまま出荷している」状態が始まる。空であること自体が
# 意味を持つので、空のまま定数として残す。
BASELINE_UNCHECKED: tuple[str, ...] = ()

# V-001 の実行体と、その 2 つの配線。片方だけだと「作ったが実行されない」または
# 「実行されるが存在が宣言されていない」になる。
CHECKER = PLUGIN_ROOT / "scripts" / "validate-compare-ratio.mjs"
SKILL_MD = PLUGIN_ROOT / "skills" / "run-slide-report-generate" / "SKILL.md"
COMPOSITION = PLUGIN_ROOT / "plugin-composition.yaml"

# V-001 が該当する slideType（比較レイアウトの面）。validate-structure.js の
# COMPARE_TYPES と同じ集合で、こちらは検査対象を外した入力を作るために持つ。
COMPARE_TYPES = ("compare", "slide-compare")


def _fixture_without_compare(tmp_path: Path) -> Path:
    """比較レイアウトの面を持たない構成を fixture から作る。

    V-001 が非該当になる入力。fixture 全体から該当面だけを外して作るので、
    他の検査は fixture と同じ条件で走る（最小構成を手で書くと、落ちた原因が
    未検査の扱いなのか構成の不備なのか切り分けられなくなる）。
    """
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    before = len(data["slides"])
    data["slides"] = [
        s for s in data["slides"]
        if (s.get("slideType") or s.get("type")) not in COMPARE_TYPES
    ]
    assert len(data["slides"]) < before, "fixture に比較レイアウトの面が無い（対照が成立しない）"
    path = tmp_path / "no-compare.structure.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def _skeleton(tmp_path: Path, *, inject: bool) -> Path:
    """プラグイン配下の実ファイルは触らず、tmp に最小の骨格を組む。

    validate-structure.js は schema を <plugin>/schemas/ から読み、無いと legacy の
    slideType 表へフォールバックして fixture が全面 FAIL する。骨格に schemas を
    含めないと、この test が「未検査の検査」ではなく「FAIL の検査」になる。
    """
    scripts = tmp_path / "vendor" / "scripts"
    scripts.mkdir(parents=True)
    (tmp_path / "vendor" / "package.json").write_text('{"type":"module"}', encoding="utf-8")
    shutil.copy(UTILS, scripts / "utils.js")
    (tmp_path / "schemas").mkdir()
    shutil.copy(SCHEMA, tmp_path / "schemas" / "structure.schema.json")

    source = VALIDATOR.read_text(encoding="utf-8")
    if inject:
        assert ANCHOR in source, "注入位置の目印が変わった"
        source = source.replace(ANCHOR, INJECT, 1)
    target = scripts / "validate-structure.js"
    target.write_text(source, encoding="utf-8")
    return target


def _unchecked_line(stdout: str) -> int:
    """集計行から未検査の件数を読む。

    ラベルの空白詰めまで文字列で書くと、行を 1 本足しただけで落ちる。ここで
    見たいのは件数なので、桁揃えは数えない。
    """
    got = re.search(r"未検査:\s*(\d+)", stdout)
    assert got, f"集計行に未検査が出ていない:\n{stdout}"
    return int(got.group(1))


def _run(script: Path, structure: Path = FIXTURE) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["node", str(script), str(structure)],
        capture_output=True,
        text=True,
        check=False,
    )


def _report_for(tmp_path: Path, structure: Path, name: str) -> dict:
    script = _skeleton(tmp_path / name, inject=False)
    out = tmp_path / f"{name}.json"
    subprocess.run(
        ["node", str(script), str(structure), "--report", str(out)],
        capture_output=True,
        text=True,
        check=False,
    )
    return json.loads(out.read_text(encoding="utf-8"))


def test_no_unchecked_stays_pass(tmp_path: Path) -> None:
    """陽性対照。未検査 0 件なら PASS / exit 0。

    検査器へ細工をせず、実際に通る入力で 0 件を出せることが、この対照の値打ち。
    """
    got = _run(_skeleton(tmp_path, inject=False))
    assert got.returncode == 0, got.stdout + got.stderr
    assert "PASS_WITH_UNCHECKED" not in got.stdout
    assert _unchecked_line(got.stdout) == 0
    assert "合格" in got.stdout


def test_v001_separates_not_applicable_from_deferred(tmp_path: Path) -> None:
    """V-001 の skip が、非該当と後段送りで kind まで別であること。

    どちらも未検査には数えないが、理由文だけを分けても機械は数えられない。
    「対象がそもそも無い」（not-applicable）と「対象はあるが構成段階では判定
    できない」（deferred）は別の事実なので、kind と理由文の両方で分ける。
    """
    hit = _report_for(tmp_path, FIXTURE, "hit")
    miss = _report_for(tmp_path, _fixture_without_compare(tmp_path), "miss")

    def v001(report: dict) -> dict:
        got = [e for e in report["skipped"] if e["vid"] == "V-001"]
        assert len(got) == 1, f"V-001 の skip が 1 件でない: {got}"
        return got[0]

    hit_v001, miss_v001 = v001(hit), v001(miss)
    assert hit_v001["kind"] == "deferred", "実行体があるのに後段送りとして出していない"
    assert miss_v001["kind"] == "not-applicable", "対象が無い構成を非該当として出していない"
    assert "非該当" in miss_v001["reason"]
    assert "非該当" not in hit_v001["reason"]
    assert hit_v001["reason"] != miss_v001["reason"]


def test_not_applicable_is_not_counted_as_deferred(tmp_path: Path) -> None:
    """後段でも永久に見ないものが deferred に溜まっていないこと。

    kind を足す前は「対象が無い」も既定の deferred に入っており、1 つの語が
    「後段が見る」と「誰も見ない」の 2 つを指していた。滞留している deferred を
    洗い出す検査を書けば、その瞬間に非該当が全部引っかかる状態だった。

    非該当の構成（比較レイアウトの面が無い）で測り、V-030 / V-043 / V-044 の
    ような「未使用なら skip」の項目が deferred 側に現れないことを見る。
    """
    report = _report_for(tmp_path, _fixture_without_compare(tmp_path), "kinds")
    kinds = {e["kind"] for e in report["skipped"]}
    assert kinds <= {"deferred", "not-applicable", "no-checker"}, f"未知の kind: {kinds}"

    deferred = {e["vid"] for e in report["skipped"] if e["kind"] == "deferred"}
    not_applicable = {e["vid"] for e in report["skipped"] if e["kind"] == "not-applicable"}
    assert not_applicable, "非該当が 1 件も出ていない（対照が成立しない）"
    assert not deferred & not_applicable, "同じ vid が両方に出ている"
    # 「未使用なら skip」の項目。この構成で実際に skip されたものだけを見る
    # （V-044 のように対象を使っていれば skip 自体が出ず、pass か fail になる）。
    skipped_vids = {e["vid"] for e in report["skipped"]}
    for vid in ("V-001", "V-030", "V-043", "V-044"):
        if vid in skipped_vids:
            assert vid in not_applicable, \
                f"{vid} が skip されたのに非該当として出ていない: deferred={sorted(deferred)}"
    assert {"V-001", "V-030"} <= not_applicable, "対照にしている 2 件が非該当に出ていない"


def test_no_baseline_unchecked(tmp_path: Path) -> None:
    """常設の未検査が 0 件であること。

    未検査は「誰も見ていない規則」の一覧なので、増えたことに気付けないと
    exit 2 が通常扱いになり、一覧ごと読まれなくなる。ここで件数を固定する。

    入力は比較レイアウトの面を持つ fixture。非該当の構成で測ると V-001 の分岐が
    そもそも走らず、この対照が中身のないまま緑になる。
    """
    slide_types = {
        (s.get("slideType") or s.get("type"))
        for s in json.loads(FIXTURE.read_text(encoding="utf-8"))["slides"]
    }
    assert slide_types & set(COMPARE_TYPES), "fixture に比較レイアウトの面が無い（対照が成立しない）"
    report = _report_for(tmp_path, FIXTURE, "baseline")
    unchecked = tuple(
        e["vid"] for e in report["skipped"] if e.get("kind") == "no-checker"
    )
    assert unchecked == BASELINE_UNCHECKED, f"常設の未検査が変わった: {unchecked}"


def test_v001_has_a_wired_checker() -> None:
    """V-001 を deferred にしておける根拠（実行体と 2 つの配線）を固定する。

    deferred は「後段に判定する実行体がある」の意味なので、実体が消えたり配線が
    外れたりすれば、V-001 は誰も見ていない規則へ戻る。そのときに黙って緑のまま
    にしないための対照。名前を skip の理由文へ書き込む代わりにここで縛る
    （理由文の名指しは検査器を動かすたびに腐り、腐っても誰も気付かない）。
    """
    assert CHECKER.exists(), f"V-001 の実行体が無い: {CHECKER}"
    assert CHECKER.name in SKILL_MD.read_text(encoding="utf-8"), \
        "SKILL.md の検査コマンド一覧に無い（存在するが実行されない）"
    assert f"scripts/{CHECKER.name}" in COMPOSITION.read_text(encoding="utf-8"), \
        "plugin-composition.yaml に宣言が無い（実行されるが存在が宣言されていない）"


def test_unchecked_blocks_plain_pass(tmp_path: Path) -> None:
    """未検査が 1 件増えれば PASS を名乗らず、exit 2（承認を求める経路）へ回る。"""
    got = _run(_skeleton(tmp_path, inject=True))
    assert got.returncode == 2, got.stdout + got.stderr
    assert "PASS_WITH_UNCHECKED" in got.stdout
    assert _unchecked_line(got.stdout) == len(BASELINE_UNCHECKED) + 1
    # 未検査の中身が出ること。件数だけだと何が見られていないのか伝わらない。
    assert "--- 未検査（実行体なし）---" in got.stdout
    assert "注入した未検査" in got.stdout
    # printReport の else に落ちて「合格」と出ていないこと（偽緑の移動）。
    assert "Phase 3 (html-generator) に進行可能" not in got.stdout


def test_v021_is_a_position_rule_not_a_character_count() -> None:
    """SR-3-09 は位置規則。20 文字の閾値を復活させない。

    V-021 自体は生きている（`<br>` の位置を見る検査が別にある）。禁じたいのは
    文字数へ戻すことだけなので、ID の有無ではなく desc の中身で縛る。
    """
    source = VALIDATOR.read_text(encoding="utf-8")
    assert '"V-021": { sr: "SR-3-09"' in source, "V-021 は欠番ではない"
    assert "文節の切れ目" in source
    assert "20文字超" not in source, "文字数規則へ戻さない"


# --------------------------------------------------------------------------
# 下流の消費者（phase-gate / evaluate-deck）が未検査を握り潰さないこと。
#
# 常設の未検査が 0 件になったので、実在の規則では陽性対照が作れない。合成の
# 未検査を注入した plugin の複製を作り、そこから消費者を走らせる。消費者は
# validate-structure.js を自分の __dirname から解決するので、複製側の注入が効く。
# 陰性対照は同じ複製を注入なしで走らせる（差分が注入だけになる）。
# --------------------------------------------------------------------------


def _plugin_copy(tmp_path: Path, name: str, *, inject: bool) -> Path:
    """vendor/scripts 一式と schemas を複製した plugin root を作る。"""
    root = tmp_path / name
    (root / "vendor").mkdir(parents=True)
    shutil.copytree(VALIDATOR.parent, root / "vendor" / "scripts")
    shutil.copy(PLUGIN_ROOT / "vendor" / "package.json", root / "vendor" / "package.json")
    shutil.copytree(PLUGIN_ROOT / "schemas", root / "schemas")
    if inject:
        target = root / "vendor" / "scripts" / "validate-structure.js"
        source = target.read_text(encoding="utf-8")
        assert ANCHOR in source, "注入位置の目印が変わった"
        target.write_text(source.replace(ANCHOR, INJECT, 1), encoding="utf-8")
    return root


def _project_dir(root: Path) -> Path:
    """structure.json を持つ作業ディレクトリを作る。"""
    d = root / "deck"
    d.mkdir()
    shutil.copy(FIXTURE, d / "structure.json")
    return d


def _phase_gate(root: Path) -> dict:
    project = _project_dir(root)
    (project / ".approved").write_text("test", encoding="utf-8")
    out = project / "gate.json"
    subprocess.run(
        ["node", str(root / "vendor" / "scripts" / "phase-gate.js"),
         str(project), "--from", "P2", "--to", "P3", "--report", str(out)],
        capture_output=True, text=True, check=False,
    )
    report = json.loads(out.read_text(encoding="utf-8"))
    checks = {c["name"]: c for c in report["gates"][0]["checks"]} if "gates" in report \
        else {c["name"]: c for c in report["checks"]}
    return checks["validate-structure.js"]


def test_phase_gate_names_unchecked_instead_of_warn(tmp_path: Path) -> None:
    """phase-gate は exit 2 を「WARN項目あり」に丸めない。

    exit 2 は WARN と PASS_WITH_UNCHECKED の両方で返る。丸めると、目視で確認
    できる指摘が 1 つも無いのに「要目視確認」と表示され、読者は探しても何も
    見つからない。何が未検査なのかを名指しすることを固定する。
    """
    check = _phase_gate(_plugin_copy(tmp_path, "hit", inject=True))
    assert check["status"] == "WARN", check
    assert "未検査" in check["detail"], check["detail"]
    assert "V-TEST-UNCHECKED" in check["detail"], check["detail"]


def test_phase_gate_passes_without_unchecked(tmp_path: Path) -> None:
    """陰性対照。未検査が無ければ未検査に触れず PASS。

    これが無いと「常に未検査と書く実装」でも上のテストが通る。
    """
    check = _phase_gate(_plugin_copy(tmp_path, "miss", inject=False))
    assert check["status"] == "PASS", check
    assert "未検査なし" in check["detail"], check["detail"]


def _evaluate_deck(root: Path) -> list[dict]:
    project = _project_dir(root)
    # index.html の中身はここでは問われない（見たいのは D4 の構造仕様まわりだけ）。
    # 他次元の finding は出るが、check 名で絞るので混ざらない。
    (project / "index.html").write_text(
        '<html><body><div class="slide"></div></body></html>', encoding="utf-8")
    out = project / "eval.json"
    subprocess.run(
        ["node", str(root / "vendor" / "scripts" / "evaluate-deck.js"),
         str(project), "--report", str(out)],
        capture_output=True, text=True, check=False,
    )
    return json.loads(out.read_text(encoding="utf-8"))["findings"]


def test_evaluate_deck_surfaces_unchecked(tmp_path: Path) -> None:
    """evaluate-deck は failed/warned だけを読まない。

    未検査を読まないと「構造仕様 PASS」と出る。誰も見ていない規則を抱えた
    まま緑になるので、ここで拾われることを固定する。
    """
    findings = _evaluate_deck(_plugin_copy(tmp_path, "hit", inject=True))
    unchecked = [f for f in findings if f.get("check") == "spec.unchecked"]
    assert unchecked, [f.get("check") for f in findings]
    assert any("V-TEST-UNCHECKED" in (f.get("title") or "") for f in unchecked), unchecked
    assert not [f for f in findings
                if f.get("check") == "spec.validate" and f.get("title") == "構造仕様 PASS"]


def test_evaluate_deck_still_passes_without_unchecked(tmp_path: Path) -> None:
    """陰性対照。未検査が無ければ従来どおり「構造仕様 PASS」。"""
    findings = _evaluate_deck(_plugin_copy(tmp_path, "miss", inject=False))
    assert not [f for f in findings if f.get("check") == "spec.unchecked"]
    assert [f for f in findings
            if f.get("check") == "spec.validate" and f.get("title") == "構造仕様 PASS"]


def test_report_json_carries_unchecked(tmp_path: Path) -> None:
    """--report の JSON にも未検査が出ること（読み手が画面だけとは限らない）。"""
    script = _skeleton(tmp_path, inject=True)
    out = tmp_path / "validation-report.json"
    subprocess.run(
        ["node", str(script), str(FIXTURE), "--report", str(out)],
        capture_output=True,
        text=True,
        check=False,
    )
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["status"] == "PASS_WITH_UNCHECKED"
