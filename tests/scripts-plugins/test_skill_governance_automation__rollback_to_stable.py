"""rollback-to-stable.py の計画出力と ceiling の出どころを確かめる。

この script は rubric.json を書き換えず、ceiling 以下の最新版を選んだ計画を JSON で出すだけ
（write-scope: none）。ceiling は --params の governance-params.json から読み、
  - ファイルがある → その値を使い params_source にパスを書く
  - ファイルが無い → 既定 0.05 を使い、stderr に警告し params_source を "default" にする
  - あるのに壊れている・数値の ceiling が無い → exit 2
（以前は無いときも壊れているときも黙って 0.05 にするか traceback で落ちていた。harness-2ix）
--rubric の rubric_version を現行版とし、それより古い版だけを候補にする（rubric が無ければ exit 2）。
rubric-versions.md は見出しの行で節を区切り、日付が無い・値を読めない・値が食い違う版は stderr に
理由を出して候補から外す（独立レビュー FAIL 75 の R1・R3〜R8、FAIL 79 の N1〜N9）。
rubric.json に rubric_id があれば同じ rubric_id の節だけを候補にし、rubric_id の行が無い節は
候補にしない（レビュー A の指摘。以前は別の rubric の版を巻き戻し先に選んでいた）。
network: false。
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "plugins" / "skill-governance-automation" / "scripts" / "rollback-to-stable.py"

_SPEC = importlib.util.spec_from_file_location("rollback_to_stable", SCRIPT)
R = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(R)

VERSIONS_MD = """# rubric versions

## 1.0.0 (2026-01-01)
- violation_rate_avg: 0.03

## 1.1.0 (2026-02-01)
- violation_rate_avg: 0.08

## 1.2.0 (2026-03-01)
- violation-rate-avg 0.04

## 1.3.0 (2026-04-01)
- no measurement yet
"""


def _rubric(tmp_path, current="9.9.9"):
    rubric = tmp_path / "r.json"
    rubric.write_text(json.dumps({"rubric_version": current}), encoding="utf-8")
    return rubric


def _run(tmp_path, *extra, current="1.3.0"):
    versions = tmp_path / "rubric-versions.md"
    versions.write_text(VERSIONS_MD, encoding="utf-8")
    (tmp_path / "rubric.json").write_text(json.dumps({"rubric_version": current}), encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--rubric", str(tmp_path / "rubric.json"),
         "--versions-md", str(versions), *extra],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )


def test_parse_versions_md_reads_both_spellings_and_keeps_unmeasured():
    rows = R.parse_versions_md(VERSIONS_MD)
    assert [(r["version"], r["violation_rate_avg"]) for r in rows] == [
        ("1.0.0", 0.03), ("1.1.0", 0.08), ("1.2.0", 0.04), ("1.3.0", None),
    ]


def test_params_file_sets_ceiling_and_source(tmp_path):
    params = tmp_path / "params.json"
    params.write_text(json.dumps({"freeze": {"violation_rate_ceiling": 0.1}}), encoding="utf-8")
    proc = _run(tmp_path, "--params", str(params))
    assert proc.returncode == 0, proc.stderr
    plan = json.loads(proc.stdout)
    # ceiling 0.1 なら 1.1.0 (0.08) より後の 1.2.0 (0.04) が最新の候補。未計測の 1.3.0 は選ばない
    assert (plan["target_version"], plan["ceiling"], plan["params_source"]) == ("1.2.0", 0.1, str(params))
    assert proc.stderr == ""


def test_missing_params_uses_default_with_warning(tmp_path):
    proc = _run(tmp_path, "--dry-run")
    assert proc.returncode == 0
    plan = json.loads(proc.stdout)
    assert (plan["ceiling"], plan["params_source"], plan["dry_run"]) == (R.DEFAULT_CEILING, "default", True)
    assert plan["target_version"] == "1.2.0"
    assert "warning: params が無い" in proc.stderr


def test_example_params_from_repo_are_accepted(tmp_path):
    proc = _run(tmp_path, "--params", str(ROOT / "references" / "governance-params.json.example"))
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["ceiling"] == 0.05


@pytest.mark.parametrize(
    ("raw", "needle"),
    [
        ("{broken", "params を読めない"),
        ("[]", "freeze.violation_rate_ceiling が無い"),
        ('{"freeze": {"violation_rate_ceiling": "0.1"}}', "freeze.violation_rate_ceiling が無い"),
        ('{"freeze": {"violation_rate_ceiling": true}}', "freeze.violation_rate_ceiling が無い"),
    ],
)
def test_broken_params_exit_2(tmp_path, raw, needle):
    params = tmp_path / "params.json"
    params.write_text(raw, encoding="utf-8")
    proc = _run(tmp_path, "--params", str(params))
    assert proc.returncode == 2
    assert needle in proc.stderr
    assert proc.stdout == "" and "Traceback" not in proc.stderr


def test_no_candidate_or_missing_versions_md_exit_1(tmp_path):
    params = tmp_path / "params.json"
    params.write_text(json.dumps({"freeze": {"violation_rate_ceiling": 0.01}}), encoding="utf-8")
    proc = _run(tmp_path, "--params", str(params))
    assert proc.returncode == 1
    assert proc.stderr.startswith(
        "no stable candidate found: 現行版 1.3.0 より古く violation_rate_avg を読めた版 3 件のうち")

    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--rubric", str(_rubric(tmp_path)), "--versions-md", str(tmp_path / "none.md"),
         "--params", str(params)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 1 and "versions-md not found" in proc.stderr


# --- 独立レビュー (FAIL 76) の指摘の再発防止 ---------------------------------


@pytest.mark.parametrize("ceiling", ["Infinity", "NaN", "-0.1", "1.5"])
def test_non_finite_or_out_of_range_ceiling_exit_2(tmp_path, ceiling):
    params = tmp_path / "params.json"
    params.write_text('{"freeze": {"violation_rate_ceiling": %s}}' % ceiling, encoding="utf-8")
    proc = _run(tmp_path, "--params", str(params))
    assert proc.returncode == 2 and "0〜1 の有限数" in proc.stderr
    assert proc.stdout == ""


def test_params_directory_is_not_treated_as_missing(tmp_path):
    (tmp_path / "params-dir").mkdir()
    proc = _run(tmp_path, "--params", str(tmp_path / "params-dir"))
    assert proc.returncode == 2 and "params がファイルでない" in proc.stderr


def test_unreadable_versions_md_exit_2_without_traceback(tmp_path):
    versions = tmp_path / "v.md"
    versions.write_bytes(b"\xff\xfe## 1.0.0 (2026-01-01)\n")
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--rubric", str(_rubric(tmp_path)), "--versions-md", str(versions)],
        capture_output=True, text=True, cwd=str(tmp_path),
    )
    assert proc.returncode == 2 and "versions-md を読めない" in proc.stderr
    assert "Traceback" not in proc.stderr


def test_trailing_period_or_dots_do_not_crash_the_parser():
    rows = R.parse_versions_md("## 1.0.0 (2026-01-01)\n- violation_rate_avg: 0.03.\n"
                               "## 1.1.0 (2026-02-01)\n- violation_rate_avg: ...\n")
    assert [(r["version"], r["violation_rate_avg"]) for r in rows] == [("1.0.0", 0.03), ("1.1.0", None)]


def test_newest_first_versions_md_still_picks_the_latest(tmp_path):
    versions = tmp_path / "v.md"
    versions.write_text("## 1.2.0 (2026-03-01)\n- violation_rate_avg: 0.04\n"
                        "## 1.0.0 (2026-01-01)\n- violation_rate_avg: 0.03\n", encoding="utf-8")
    _rubric(tmp_path)
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--rubric", "r.json", "--versions-md", str(versions)],
        capture_output=True, text=True, cwd=str(tmp_path),
    )
    assert proc.returncode == 0, proc.stderr
    plan = json.loads(proc.stdout)
    assert (plan["target_version"], plan["rubric"]) == ("1.2.0", "r.json")


# --- 独立レビュー (FAIL 75) の指摘の再発防止 ---------------------------------


def _cli(tmp_path, versions_text, *, ceiling=0.05, current="9.9.9", rubric_id=None):
    versions = tmp_path / "v.md"
    if isinstance(versions_text, bytes):
        versions.write_bytes(versions_text)
    else:
        versions.write_text(versions_text, encoding="utf-8")
    params = tmp_path / "params.json"
    params.write_text(json.dumps({"freeze": {"violation_rate_ceiling": ceiling}}), encoding="utf-8")
    rubric = tmp_path / "rubric.json"
    if current is not None:
        data = {"rubric_version": current}
        if rubric_id is not None:
            data["rubric_id"] = rubric_id
        rubric.write_text(json.dumps(data), encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--rubric", str(rubric), "--versions-md", str(versions),
         "--params", str(params)],
        capture_output=True, text=True, cwd=str(tmp_path),
    )


@pytest.mark.parametrize(
    "heading",
    ["## 1.1.0", "## 1.1.0 (2026-02-01, minor)", "## 1.1.0（2026-02-01）", "# 付録", "## 未リリース"],
)
def test_any_heading_closes_the_previous_section(tmp_path, heading):
    # R1: 以前は厳密な見出しにしか反応せず、後ろの 0.30 が 1.0.0 の 0.01 を上書きして 1.0.0 を選べなかった
    # （逆の並びでは 0.30 の版を安定版として選んでいた）
    text = f"## 1.0.0 (2026-01-01)\n- violation_rate_avg: 0.01\n{heading}\n- violation_rate_avg: 0.30\n"
    rows = R.parse_versions_md(text)
    assert (rows[0]["version"], rows[0]["violation_rate_avg"], rows[0]["issue"]) == ("1.0.0", 0.01, None)
    proc = _cli(tmp_path, text, current="9.9.9")
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["target_version"] == "1.0.0"


def test_versions_without_date_are_reported_and_skipped(tmp_path):
    proc = _cli(tmp_path, "## 1.0.0 (2026-01-01)\n- violation_rate_avg: 0.04\n"
                          "## 1.1.0\n- violation_rate_avg: 0.01\n", current="9.9.9")
    assert proc.returncode == 0
    assert json.loads(proc.stdout)["target_version"] == "1.0.0"
    assert "warning: 1.1.0: 見出しに日付 (YYYY-MM-DD) が無い。この版は候補にしない" in proc.stderr


@pytest.mark.parametrize(
    ("line", "needle"),
    [
        ("- violation_rate_avg: 0,30", "読めない"),
        ("- violation_rate_avg: 3%", "読めない"),
        ("- violation_rate_avg: 0.5%", "読めない"),
        ("- violation_rate_avg: 1.5", "0〜1 の外"),
        ("- violation_rate_avg: 0.01\n- violation_rate_avg: 0.30", "食い違う"),
    ],
)
def test_unreadable_or_conflicting_values_are_not_candidates(tmp_path, line, needle):
    # R3: 以前は「0,30」を 0.0 と読み、安定版として選んでいた
    rows = R.parse_versions_md(f"## 1.0.0 (2026-01-01)\n{line}\n")
    assert needle in rows[0]["issue"]
    proc = _cli(tmp_path, f"## 1.0.0 (2026-01-01)\n{line}\n", current="9.9.9")
    assert proc.returncode == 1 and needle in proc.stderr
    assert "violation_rate_avg を読めた版 0 件" in proc.stderr


def test_trailing_comma_is_tolerated():
    rows = R.parse_versions_md("## 1.0.0 (2026-01-01)\n- violation_rate_avg: 0.03, 3 runs\n")
    assert (rows[0]["violation_rate_avg"], rows[0]["issue"]) == (0.03, None)


def test_subheading_stays_inside_the_version_section():
    rows = R.parse_versions_md("## 1.0.0 (2026-01-01)\n### 計測\n- violation_rate_avg: 0.02\n")
    assert [(r["version"], r["violation_rate_avg"], r["issue"]) for r in rows] == [("1.0.0", 0.02, None)]


@pytest.mark.parametrize("heading", ["### 1.2.0 (2026-03-01)", "#### v1.2.0", "###### 1.2 の計測"])
def test_version_like_subheading_closes_the_section(heading):
    # coverage レビュー: 以前は ### 以下をすべて小見出しとして扱い、版らしい小見出しの下の値を直前の版に数えていた
    warnings: list[str] = []
    text = f"## 1.3.0 (2026-04-01)\n- rubric_id: skill-design\n{heading}\n- violation_rate_avg: 0.01\n"
    rows = R.parse_versions_md(text, warnings)
    assert [(r["version"], r["violation_rate_avg"], r["issue"]) for r in rows] == [("1.3.0", None, None)]
    assert warnings == [f"見出し {heading!r} を版の見出しとして読めない（版の見出しなら `## <版> (YYYY-MM-DD)` で書く。"
                        "1.3.0 の節の小見出しなら、1.3.0 のほかに版の番号や小数を入れない）。この節の値は使わない"]


@pytest.mark.parametrize("heading", ["### 1.3.0 の計測", "#### v1.3 の補足", "### 計測（1.3.0）", "### 1.3.0の計測"])
def test_subheading_with_the_same_version_stays_inside(tmp_path, heading):
    # 評価者の指摘 (b): 以前は今の節と同じ版を含む小見出しでも節を閉じ、下の値を落として 1.0.0 を選び、
    # 「## で書く」と誤って勧めていた。同じ版の番号（1.3 と 1.3.0 は同じ。v が付いてもよい）は数えない
    text = ("## 1.0.0 (2026-01-01)\n- violation_rate_avg: 0.02\n"
            f"## 1.3.0 (2026-04-01)\n{heading}\n- violation_rate_avg: 0.01\n")
    warnings: list[str] = []
    rows = R.parse_versions_md(text, warnings)
    assert [(r["version"], r["violation_rate_avg"], r["issue"]) for r in rows] == [("1.0.0", 0.02, None),
                                                                                  ("1.3.0", 0.01, None)]
    assert warnings == []
    proc = _cli(tmp_path, text, current="1.4.0")
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["target_version"] == "1.3.0"
    assert "見出し" not in proc.stderr


def test_rubric_id_under_a_same_version_subheading_is_read(tmp_path):
    # 評価者の指摘 (c): 以前は「### 1.3.0 の補足」で節を閉じて下の rubric_id を落とし、rubric_id の無い現行の
    # rubric に、別の rubric (other) の 1.3.0 を選んでいた。いまは rubric_id を節に読み、照合できないので外す
    text = ("## 1.3.0 (2026-04-01)\n- violation_rate_avg: 0.01\n### 1.3.0 の補足\n- rubric_id: other\n"
            "## 1.0.0 (2026-01-01)\n- violation_rate_avg: 0.02\n")
    proc = _cli(tmp_path, text, current="1.4.0")
    assert proc.returncode == 0, proc.stderr
    assert (json.loads(proc.stdout)["target_version"], json.loads(proc.stdout)["rubric_id"]) == ("1.0.0", None)
    assert "rubric_id other を、rubric_id の無い現行の rubric と照合できない" in proc.stderr


@pytest.mark.parametrize("heading", ["### 1.3.0-rc.1 (2026-03-01)", "### 1.3.0 と 1.2.0 の比較", "### 1.3.0.1"])
def test_subheading_with_another_version_still_closes_the_section(heading):
    # 同じ版の番号のほかに、別の版（プレリリースや、1.3.0 に続く桁を含む）があれば、これまでどおり閉じる
    text = f"## 1.3.0 (2026-04-01)\n{heading}\n- violation_rate_avg: 0.01\n"
    warnings: list[str] = []
    rows = R.parse_versions_md(text, warnings)
    assert [(r["version"], r["violation_rate_avg"], r["issue"]) for r in rows] == [("1.3.0", None, None)]
    assert len(warnings) == 1 and warnings[0].startswith(f"見出し {heading!r} を版の見出しとして読めない")


def test_version_like_subheading_does_not_lend_its_value_to_the_previous_version(tmp_path):
    # 以前は 1.2.0 の 0.01 を 1.3.0 の値に読み、1.3.0 を安定版に選んでいた。いまは 1.0.0 を選び、見出しを stderr に出す
    text = ("## 1.0.0 (2026-01-01)\n- violation_rate_avg: 0.02\n"
            "## 1.3.0 (2026-04-01)\n### 1.2.0 (2026-03-01)\n- violation_rate_avg: 0.01\n")
    proc = _cli(tmp_path, text)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["target_version"] == "1.0.0"
    assert "見出し '### 1.2.0 (2026-03-01)' を版の見出しとして読めない" in proc.stderr


def test_version_like_subheading_alone_leaves_no_candidate(tmp_path):
    # 値が版らしい小見出しの下にしか無ければ候補なし（exit 1）。exit code の契約は変えない
    proc = _cli(tmp_path, "## 1.3.0 (2026-04-01)\n### 1.2.0 (2026-03-01)\n- violation_rate_avg: 0.01\n")
    assert proc.returncode == 1
    assert "見出し '### 1.2.0 (2026-03-01)' を版の見出しとして読めない" in proc.stderr


def test_plain_subheadings_at_deeper_levels_stay_inside(tmp_path):
    text = "## 1.0.0 (2026-01-01)\n#### 計測の詳細\n###### 補足\n- violation_rate_avg: 0.02\n"
    warnings: list[str] = []
    rows = R.parse_versions_md(text, warnings)
    assert [(r["version"], r["violation_rate_avg"], r["issue"]) for r in rows] == [("1.0.0", 0.02, None)]
    assert warnings == []


def test_heading_inside_code_fence_does_not_close_the_section():
    rows = R.parse_versions_md("## 1.0.0 (2026-01-01)\n```bash\n# run\n```\n- violation_rate_avg: 0.02\n")
    assert [(r["version"], r["violation_rate_avg"]) for r in rows] == [("1.0.0", 0.02)]


def test_template_without_rate_line_explains_what_is_missing(tmp_path):
    # R2: 27章§8.3 のひな形には violation_rate_avg の行が無い。黙って「候補なし」にしない
    proc = _cli(tmp_path, "## 1.3.0 (2026-06-01)\n- rubric_id: skill-design / hash: sha256:abcd\n", current="9.9.9",
                rubric_id="skill-design")
    assert proc.returncode == 1
    assert "`- violation_rate_avg: <0〜1>` の行が要る" in proc.stderr


def test_bom_does_not_hide_the_first_version(tmp_path):
    # R6
    proc = _cli(tmp_path, b"\xef\xbb\xbf## 1.0.0 (2026-01-01)\n- violation_rate_avg: 0.01\n", current="9.9.9")
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["target_version"] == "1.0.0"


def test_release_is_newer_than_its_prerelease_on_the_same_day():
    # R7: 以前は 2.0.0-rc.1 を 2.0.0 より新しいとみなしていた
    day = "2026-01-01"
    order = ["2.0.0-rc.1", "2.0.0-rc.2", "2.0.0", "2.0.1-rc.1"]
    rows = [{"version": v, "date": day} for v in reversed(order)]
    assert [r["version"] for r in sorted(rows, key=R.recency)] == order


def test_versions_md_directory_exit_2(tmp_path):
    # R4: 以前は「not found」で exit 1 だった（不在とディレクトリを区別しない）
    (tmp_path / "vdir").mkdir()
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--rubric", str(_rubric(tmp_path)), "--versions-md", str(tmp_path / "vdir")],
        capture_output=True, text=True, cwd=str(tmp_path),
    )
    assert proc.returncode == 2 and "versions-md がファイルでない" in proc.stderr


def test_huge_integer_ceiling_exit_2_without_traceback(tmp_path):
    # R8: 以前は math.isfinite の OverflowError で traceback（exit 1）になった
    params = tmp_path / "params.json"
    params.write_text('{"freeze": {"violation_rate_ceiling": 1%s}}' % ("0" * 400), encoding="utf-8")
    proc = _run(tmp_path, "--params", str(params))
    assert proc.returncode == 2 and "0〜1 の有限数" in proc.stderr
    assert "Traceback" not in proc.stderr


def test_broken_symlink_params_is_not_treated_as_missing(tmp_path):
    # R5: 以前は壊れた symlink を「無い」とみなし、既定の ceiling で exit 0 になった
    (tmp_path / "params.json").symlink_to(tmp_path / "gone.json")
    proc = _run(tmp_path, "--params", str(tmp_path / "params.json"))
    assert proc.returncode == 2 and "params がファイルでない" in proc.stderr


def test_stat_error_on_params_exit_2(tmp_path, monkeypatch, capsys):
    # R5: 親ディレクトリが読めないと Path.exists() が PermissionError を投げ、traceback になっていた
    real_is_file = Path.is_file

    def is_file(self):
        if self.name == "locked.json":
            raise PermissionError(13, "Permission denied", str(self))
        return real_is_file(self)

    monkeypatch.setattr(Path, "is_file", is_file)
    monkeypatch.setattr(sys, "argv", ["rollback-to-stable.py", "--rubric", "r.json", "--versions-md", "v.md",
                                      "--params", str(tmp_path / "locked.json")])
    assert R.main() == 2
    assert "params を読めない" in capsys.readouterr().err


def test_current_rubric_version_is_not_a_candidate(tmp_path):
    params = tmp_path / "params.json"
    params.write_text(json.dumps({"freeze": {"violation_rate_ceiling": 0.1}}), encoding="utf-8")
    proc = _run(tmp_path, "--params", str(params), current="v1.2.0")
    assert proc.returncode == 0, proc.stderr
    plan = json.loads(proc.stdout)
    # 1.2.0 は現行版なので外し、その前の 1.1.0 (0.08) を選ぶ
    assert (plan["target_version"], plan["current_version"]) == ("1.1.0", "1.2.0")


def test_missing_rubric_exit_2(tmp_path):
    # FAIL 79 の N6: 以前は警告だけで exit 0 にし、現行版を外さない計画を出していた
    proc = _cli(tmp_path, VERSIONS_MD, current=None)
    assert proc.returncode == 2 and "error: rubric が無い" in proc.stderr
    assert proc.stdout == ""


@pytest.mark.parametrize(("raw", "needle"), [("{broken", "rubric を読めない"), ("{}", "rubric_version が無い")])
def test_broken_rubric_exit_2(tmp_path, raw, needle):
    (tmp_path / "rubric.json").write_text(raw, encoding="utf-8")
    versions = tmp_path / "v.md"
    versions.write_text(VERSIONS_MD, encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--rubric", str(tmp_path / "rubric.json"), "--versions-md", str(versions)],
        capture_output=True, text=True, cwd=str(tmp_path),
    )
    assert proc.returncode == 2 and needle in proc.stderr and proc.stdout == ""


# --- 独立レビュー (FAIL 79) の指摘の再発防止 ---------------------------------


def test_versions_newer_than_current_are_not_candidates(tmp_path):
    # N1: 以前は現行 1.2.0 のとき 1.3.0 を巻き戻し先に選んでいた
    text = ("## 1.1.0 (2026-02-01)\n- violation_rate_avg: 0.01\n"
            "## 1.2.0 (2026-03-01)\n- violation_rate_avg: 0.01\n"
            "## 1.3.0 (2026-04-01)\n- violation_rate_avg: 0.01\n")
    proc = _cli(tmp_path, text, current="1.2")
    assert proc.returncode == 0, proc.stderr
    plan = json.loads(proc.stdout)
    assert (plan["target_version"], plan["current_version"]) == ("1.1.0", "1.2")
    assert "warning: 1.3.0: 現行版 1.2 より新しい。この版は候補にしない" in proc.stderr


@pytest.mark.parametrize("current", ["latest", "1.x", "１.２.０"])
def test_unparseable_current_version_exit_2(tmp_path, current):
    proc = _cli(tmp_path, VERSIONS_MD, current=current)
    assert proc.returncode == 2 and "rubric_version を版として読めない" in proc.stderr


@pytest.mark.parametrize(
    "value",
    ["0.01→0.30", "0.01 → 0.30", "0.01〜0.30", "0.01-0.30", "0.01/0.30", "0.0３", "0.01 0.30", "未計測"],
)
def test_value_must_end_at_a_boundary(value):
    # R3 の残り: 以前は数字の後ろを見ず、0.01 や 0.0 と読んで候補にしていた
    rows = R.parse_versions_md(f"## 1.0.0 (2026-01-01)\n- violation_rate_avg: {value}\n")
    assert rows[0]["issue"] is not None and "読めない" in rows[0]["issue"]


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("- violation_rate_avg: 0.02 (10 runs)", 0.02),
        ("- violation_rate_avg: 0.02（10 runs）", 0.02),
        ("- violation_rate_avg: 0.02 # 手で計算", 0.02),
        ("- violation_rate_avg: 0.02 <!-- memo -->", 0.02),
        ("- violation_rate_avg：0.02", 0.02),
        ("- impact: affected=12 / violation_rate_avg: 0.02 / runs: 10", 0.02),
        ("* violation_rate_avg 0.02.", 0.02),
    ],
)
def test_value_with_allowed_tails(line, expected):
    rows = R.parse_versions_md(f"## 1.0.0 (2026-01-01)\n{line}\n")
    assert (rows[0]["violation_rate_avg"], rows[0]["issue"]) == (expected, None)


@pytest.mark.parametrize(
    "line",
    ["- baseline_violation_rate_avg: 0.01", "前回の violation_rate_avg: 0.01 を参考にした", "- violation_rate_avg_old: 0.01"],
)
def test_key_needs_a_left_boundary(line):
    # N3: 以前は本文中の言及や別のキーを、その版の値として読んでいた
    rows = R.parse_versions_md(f"## 1.0.0 (2026-01-01)\n{line}\n")
    assert (rows[0]["violation_rate_avg"], rows[0]["issue"]) == (None, None)


def test_misformatted_version_heading_is_reported(tmp_path):
    # N4: 以前は「## [1.3.0] - …」の後ろの値を警告なしで捨て、古い版を選んでいた
    text = ("## 1.0.0 (2026-01-01)\n- violation_rate_avg: 0.01\n"
            "## [1.3.0] - 2026-04-01\n- violation_rate_avg: 0.01\n# 付録\n")
    proc = _cli(tmp_path, text)
    assert proc.returncode == 0, proc.stderr
    assert "見出し '## [1.3.0] - 2026-04-01' を版の見出しとして読めない" in proc.stderr
    assert "付録" not in proc.stderr


def test_fullwidth_date_is_not_a_date():
    # N5: 以前は全角数字の日付を最新とみなしていた
    rows = R.parse_versions_md("## 1.0.0 (２０２６-０１-０１)\n- violation_rate_avg: 0.01\n")
    assert rows[0]["date"] is None and "日付" in rows[0]["issue"]


def test_html_comment_duplicate_heading_and_fence_variants():
    # N7: 複数行の HTML コメントの中の版、同じ版の見出しが2つ、~~~ と ``` の取り違え
    text = ("## 1.0.0 (2026-01-01)\n- violation_rate_avg: 0.01\n"
            "<!--\n## 1.5.0 (2026-05-01)\n- violation_rate_avg: 0.01\n-->\n"
            "## 1.1.0 (2026-02-01)\n- violation_rate_avg: 0.02\n"
            "~~~\n```\n## 1.6.0 (2026-06-01)\n~~~\n"
            "## 1.1.0 (2026-02-02)\n- violation_rate_avg: 0.02\n")
    rows = R.parse_versions_md(text)
    assert [r["version"] for r in rows] == ["1.0.0", "1.1.0", "1.1.0"]
    assert rows[0]["issue"] is None
    assert all("同じ版の見出しが複数ある" in r["issue"] for r in rows[1:])


def test_symlink_loop_params_and_huge_version_do_not_traceback(tmp_path):
    # N8: 以前は symlink のループで RuntimeError、5001桁の版で int の ValueError になっていた
    loop = tmp_path / "loop"
    loop.symlink_to(loop)
    huge = "## " + "9" * 5001 + ".0.0 (2026-01-01)\n- violation_rate_avg: 0.01\n"
    proc = _cli(tmp_path, "## 1.0.0 (2026-01-01)\n- violation_rate_avg: 0.01\n" + huge)
    assert proc.returncode == 0 and "Traceback" not in proc.stderr
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--rubric", str(_rubric(tmp_path)), "--versions-md", str(tmp_path / "v.md"),
         "--params", str(loop / "params.json")],
        capture_output=True, text=True, cwd=str(tmp_path),
    )
    assert proc.returncode in (0, 2) and "Traceback" not in proc.stderr


def test_plan_restores_content_and_carries_the_recorded_hash(tmp_path):
    # N2: 以前は版の名前を書き戻すだけの計画で、照合する hash も出さなかった
    text = ("## 1.0.0 (2026-01-01)\n- rubric_id: skill-design / hash: sha256:" + "a" * 64 + "\n"
            "- violation_rate_avg: 0.01\n")
    proc = _cli(tmp_path, text, rubric_id="skill-design")
    assert proc.returncode == 0, proc.stderr
    plan = json.loads(proc.stdout)
    assert (plan["target_hash"], plan["rubric_id"]) == ("sha256:" + "a" * 64, "skill-design")
    # run-governance-automation の手順と同じく、派生の rubric.json を一組で戻し、templates/ はあれば戻す
    assert "派生した rubric.json" in plan["steps"][0] and "templates/ があれば" in plan["steps"][0]
    assert plan["target_hash"] in plan["steps"][1]
    # hash の照合は書き込まずに行う。--dry-run が無いと rubric_hash を書き込み、一組で戻した派生の
    # rubric.json と合わなくなる（rubric_hash を持たない版を戻したときに RUBRIC_DRIFT）
    assert "compute-rubric-hash.py --dry-run --rubric" in plan["steps"][1]
    proc = _cli(tmp_path, "## 1.0.0 (2026-01-01)\n- violation_rate_avg: 0.01\n")
    plan = json.loads(proc.stdout)
    assert plan["target_hash"] is None and "hash の記録が無い" in plan["steps"][1]
    assert "compute-rubric-hash.py --dry-run --rubric" in plan["steps"][1]
    # 照合先として、repo に無い rubric.normalized.json を指さない
    assert "rubric.normalized.json" not in plan["steps"][1]


# --- レビュー A の指摘の再発防止 ----------------------------------------------

TWO_RUBRICS = ("## 1.0.0 (2026-01-01)\n- rubric_id: skill-design\n- violation_rate_avg: 0.02\n"
               "## 1.1.0 (2026-02-01)\n- rubric_id: assign-rubric\n- violation_rate_avg: 0.01\n"
               "## 1.1.0 (2026-02-02)\n- rubric_id: skill-design\n- violation_rate_avg: 0.30\n")


def test_only_sections_of_the_current_rubric_are_candidates(tmp_path):
    # 以前は rubric_id を見ず、別の rubric (assign-rubric) の 1.1.0 を巻き戻し先に選んでいた
    proc = _cli(tmp_path, TWO_RUBRICS, current="1.5.0", rubric_id="skill-design")
    assert proc.returncode == 0, proc.stderr
    plan = json.loads(proc.stdout)
    assert (plan["target_version"], plan["rubric_id"]) == ("1.0.0", "skill-design")
    assert "1.1.0: rubric_id assign-rubric は現行の rubric (skill-design) と違う" in proc.stderr
    # rubric が違えば同じ版の番号でも重複ではない
    assert "同じ版の見出しが複数ある" not in proc.stderr


def test_section_without_rubric_id_is_not_a_candidate_when_current_has_one(tmp_path):
    proc = _cli(tmp_path, "## 1.0.0 (2026-01-01)\n- violation_rate_avg: 0.01\n", rubric_id="skill-design")
    assert proc.returncode == 1 and proc.stdout == ""
    assert "1.0.0: rubric_id の行が無く、現行の rubric (skill-design) の版か確かめられない" in proc.stderr
    assert "`- rubric_id: skill-design` の行が要る" in proc.stderr


def test_current_without_rubric_id_skips_sections_that_have_one(tmp_path):
    text = ("## 1.1.0 (2026-02-01)\n- rubric_id: skill-design\n- violation_rate_avg: 0.01\n"
            "## 1.0.0 (2026-01-01)\n- violation_rate_avg: 0.02\n")
    proc = _cli(tmp_path, text)
    assert proc.returncode == 0, proc.stderr
    assert (json.loads(proc.stdout)["target_version"], json.loads(proc.stdout)["rubric_id"]) == ("1.0.0", None)
    assert "rubric_id skill-design を、rubric_id の無い現行の rubric と照合できない" in proc.stderr


@pytest.mark.parametrize("rubric_id", ["", "  ", 3, ["skill-design"]])
def test_non_string_rubric_id_exit_2(tmp_path, rubric_id):
    proc = _cli(tmp_path, TWO_RUBRICS, rubric_id=rubric_id)
    assert proc.returncode == 2 and "rubric_id が空でない文字列でない" in proc.stderr and proc.stdout == ""


@pytest.mark.parametrize(
    ("line", "rubric_id", "hash_"),
    [
        ("- rubric_id: skill-design / hash: sha256:abcd", "skill-design", "sha256:abcd"),
        ("- **rubric_id**: `skill-design` / **hash**: sha256:abcd", "skill-design", "sha256:abcd"),
        ('- impact: none / rubric-id: "skill-design"', "skill-design", None),
    ],
)
def test_template_line_reads_rubric_id_and_hash(line, rubric_id, hash_):
    row = R.parse_versions_md(f"## 1.3.0 (2026-06-01)\n{line}\n")[0]
    assert (row["rubric_id"], row["hash"], row["issue"]) == (rubric_id, hash_, None)


@pytest.mark.parametrize(
    ("lines", "needle"),
    [("- rubric_id: a\n- rubric_id: b", "rubric_id が食い違う: a と b"), ("- rubric_id: ?", "rubric_id を読めない")],
)
def test_conflicting_or_unreadable_rubric_id_is_an_issue(lines, needle):
    row = R.parse_versions_md(f"## 1.0.0 (2026-01-01)\n{lines}\n- violation_rate_avg: 0.01\n")[0]
    assert needle in row["issue"]


@pytest.mark.parametrize("date", ["2026-13-45", "2026-02-30", "2026-00-10"])
def test_date_not_on_the_calendar_is_not_a_candidate(tmp_path, date):
    # 以前は 2026-13-45 を文字列で比べ、最新の版とみなしていた
    text = f"## 1.3.0 ({date})\n- violation_rate_avg: 0.02\n## 1.0.0 (2026-01-01)\n- violation_rate_avg: 0.03\n"
    proc = _cli(tmp_path, text, current="1.4.0")
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["target_version"] == "1.0.0"
    assert f"1.3.0: 見出しの日付 {date} が暦に無い" in proc.stderr


def test_short_and_long_spelling_of_the_same_version_are_duplicates(tmp_path):
    # 以前は 1.3 と 1.3.0 を別の版とみなし、1.3 を選んでいた
    text = ("## 1.3 (2026-04-01)\n- violation_rate_avg: 0.02\n## 1.3.0 (2026-04-02)\n- violation_rate_avg: 0.30\n"
            "## 1.0.0 (2026-01-01)\n- violation_rate_avg: 0.03\n")
    proc = _cli(tmp_path, text, current="1.4.0")
    assert json.loads(proc.stdout)["target_version"] == "1.0.0"
    assert "warning: 1.3: 同じ版の見出しが複数ある" in proc.stderr
    rows = R.parse_versions_md("## 1.3.0-alpha.1 (2026-04-01)\n## 1.3.0-beta.1 (2026-04-02)\n")
    assert [r["issue"] for r in rows] == [None, None]


@pytest.mark.parametrize(("current", "expected"), [("2.0.0", "1.9.0"), ("2.0.0-rc.2", "1.9.0")])
def test_prerelease_is_not_a_stable_candidate(tmp_path, current, expected):
    # 以前は現行 2.0.0 のとき 2.0.0-rc.1 を安定版として選んでいた
    text = ("## 2.0.0-rc.1 (2026-05-01)\n- violation_rate_avg: 0.01\n"
            "## 1.9.0 (2026-04-01)\n- violation_rate_avg: 0.02\n")
    proc = _cli(tmp_path, text, current=current)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["target_version"] == expected
    assert "2.0.0-rc.1: プレリリースは安定版として選ばない" in proc.stderr


@pytest.mark.parametrize(
    "line",
    ["- **violation_rate_avg**: 0.02", "- **violation_rate_avg:** 0.02", "- `violation_rate_avg`: 0.02",
     "- __violation_rate_avg__: 0.02", "- violation_rate_avg: 0.02 / violation_rate_avg: 0.02"],
)
def test_decorated_or_repeated_key_is_read(line):
    # 以前は強調したキーを黙って読み飛ばし、その版を未計測とみなしていた
    row = R.parse_versions_md(f"## 1.0.0 (2026-01-01)\n{line}\n")[0]
    assert (row["violation_rate_avg"], row["issue"]) == (0.02, None)


@pytest.mark.parametrize(
    ("value", "expected"),
    [("0.01, 0.30", None), ("0.01, .30", None), ("0.01, 1", None), ("0.30 / violation_rate_avg: 0.01", None),
     ("0.03, 3 runs", 0.03), ("0.02, 旧値 0.30 から下げた", 0.02)],
)
def test_second_value_after_a_comma_or_key_is_not_silently_dropped(value, expected):
    # 以前は「0.01, 0.30」を 0.01 と読み（「0.01,0.30」は拒んでいた）、同じ行の2つめのキーを無視していた
    row = R.parse_versions_md(f"## 1.0.0 (2026-01-01)\n- violation_rate_avg: {value}\n")[0]
    if expected is None:
        assert row["issue"] is not None
    else:
        assert (row["violation_rate_avg"], row["issue"]) == (expected, None)


def test_latest_date_wins_over_a_higher_version_number(tmp_path):
    # 候補の中から日付が最も新しい版を選ぶ（版の番号は同じ日のときだけ比べる）
    text = ("## 1.2.0 (2026-02-01)\n- violation_rate_avg: 0.02\n"
            "## 1.1.1 (2026-03-01)\n- violation_rate_avg: 0.02\n"
            "## 1.0.0 (2026-03-01)\n- violation_rate_avg: 0.02\n")
    proc = _cli(tmp_path, text, current="1.3.0")
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["target_version"] == "1.1.1"
