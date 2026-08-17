"""lint-marketplace-install-docs.py の検出ロジック回帰テスト。

README の install 導線が実体からズレる事故 (リポジトリ改名で
`manju/skills` が取り残された / plugin 改名で `skill-creator` が実体を失った)
を捕捉する lint 自身が腐らないよう、検出/許容の各分岐を機械保証する。

検証する不変条件:
  M1 リポジトリ名不一致 → 検出 / 一致・ローカル手順の絶対パス・プレースホルダ → 許容
  M2 実在しない marketplace 名 → 検出
  M3 marketplace 未登録の plugin を install 案内 → 検出 (非配布ならヒントを添える)
  M4 実在しない plugin のスラッシュコマンド → 検出
  M5 実在しない skill のスラッシュコマンド → 検出
  走査範囲は既定で全行。opt-out は `lint-ignore` マーカーと HTML コメントだけ
  実 repo の README が PASS し、かつ壊すと落ちること (統合・非恒真)

import 経路: dash 入り script のため importlib.util.spec_from_file_location
(test_lint_readme_plugin_root_portability.py のパターンに倣う)。
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "lint-marketplace-install-docs.py"
SPEC = importlib.util.spec_from_file_location("lint_marketplace_install_docs", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)

REPO = "owner/repo"
CATALOGS = {
    "skills": {"alpha", "beta", "skills-full"},
    "harness-local": {"alpha", "beta", "internal-only"},
}
ON_DISK = {"alpha", "beta", "internal-only"}
SKILLS = {"alpha": {"run-something"}, "beta": {"run-beta"}, "internal-only": set()}


def check(text: str) -> list[str]:
    return MOD.check_install_docs(text, REPO, CATALOGS, ON_DISK, SKILLS)


def codes(text: str) -> list[str]:
    """違反メッセージから M1..M4 のコードだけ取り出す。"""
    out = []
    for e in check(text):
        for c in ("M1", "M2", "M3", "M4", "M5"):
            if f" {c} " in e:
                out.append(c)
    return out


# --- M1: marketplace add のリポジトリ名 -----------------------------------


def test_m1_detects_stale_repository_name():
    assert codes("/plugin marketplace add manju/skills") == ["M1"]


def test_m1_allows_matching_repository_name():
    assert check(f"/plugin marketplace add {REPO}") == []


def test_m1_allows_marketplace_name_for_update_and_remove():
    # `marketplace update skills` は marketplace 名指定であってリポジトリ名ではない
    assert check("/plugin marketplace update skills\n/plugin marketplace remove skills") == []


def test_m1_ignores_local_marketplace_absolute_path_and_placeholder():
    text = (
        "/plugin marketplace add /Users/me/harness/marketplaces/local\n"
        "/plugin marketplace add <出力された絶対パス>\n"
        "/plugin marketplace add harness-local\n"
    )
    assert check(text) == []


def test_m1_strips_surrounding_backticks():
    assert codes("`/plugin marketplace add manju/skills`") == ["M1"]


# --- M2/M3: install 対象 ---------------------------------------------------


def test_m2_detects_unknown_marketplace_name():
    assert codes("/plugin install alpha@nosuchmarket") == ["M2"]


def test_m3_detects_plugin_not_registered_in_marketplace():
    assert codes("/plugin install nonexistent@skills") == ["M3"]


def test_m3_hints_local_route_for_non_distributable_plugin():
    """実体はあるが公開 marketplace に無い = 非配布。ローカル経路のヒントを出す。"""
    errs = check("/plugin install internal-only@skills")
    assert len(errs) == 1
    assert "ローカル marketplace 経由" in errs[0]


def test_m3_allows_bundle_name():
    assert check("/plugin install skills-full@skills") == []


def test_m3_allows_plugin_from_local_marketplace():
    assert check("/plugin install internal-only@harness-local") == []


def test_install_update_uninstall_are_all_checked():
    text = (
        "/plugin install nonexistent@skills\n"
        "/plugin update nonexistent@skills\n"
        "/plugin uninstall nonexistent@skills\n"
    )
    assert codes(text) == ["M3", "M3", "M3"]


# --- M4: スラッシュコマンドの plugin 名 -------------------------------------


def test_m4_detects_slash_command_for_missing_plugin():
    assert codes("/skill-creator:run-skill-create") == ["M4"]


def test_m4_allows_slash_command_for_existing_plugin():
    assert check("/alpha:run-something") == []


def test_m4_matches_slash_command_anywhere_in_prose():
    """行頭に限ると、実際に README で使われる書き方をほぼ全て取りこぼす。

    `/skill-creator:run-skill-create` が README:329 に生きた壊れ参照として
    残っていたのは、行頭アンカーがインラインコードも散文も見なかったためである。
    """
    for text in (
        "詳細は /nosuch:run-x を参照",
        "詳細は `/nosuch:run-x` を参照",
        "**/nosuch:run-x** を実行",
        "| 手順 | `/nosuch:run-x` で開始 |",
    ):
        assert codes(text) == ["M4"], text


# --- 走査範囲: 既定は全行、opt-out は明示マーカーのみ ----------------------


def test_code_fence_is_in_scope():
    """README の install 手順はほぼ全てフェンスの中にある。

    除外すると M2/M3 の検査対象行が 0 になり、docstring が「防ぐ」と明言した
    事故を実 README 上で再現しても 1 件も検出できない (実測済み)。
    """
    assert codes("```bash\n/plugin install nonexistent@skills\n```") == ["M3"]
    assert codes("```\n/nosuch:run-x\n```") == ["M4"]


def test_html_comment_is_out_of_scope():
    """レンダリング後に読者へ表示されない = 実行手順ではない。"""
    assert check("<!-- 旧手順: `/nosuch:run-x` -->") == []


def test_fence_info_string_lint_ignore_excludes_whole_block():
    """壊れた例を「壊れている」と示すための正規手段。"""
    assert check("```text lint-ignore\n/plugin marketplace add manju/skills\n```") == []
    # マーカーが無ければ同じ内容が検出される (opt-out が恒真でないことの保証)
    assert codes("```text\n/plugin marketplace add manju/skills\n```") == ["M1"]


def test_inline_lint_ignore_excludes_single_line():
    assert check("`/nosuch:run-x` <!-- 反例 --> lint-ignore") == []
    assert codes("`/nosuch:run-x`") == ["M4"]


def test_fence_opt_out_does_not_leak_past_closing_fence():
    """除外はブロック内で閉じる。閉じフェンスの後まで漏れると穴になる。"""
    text = "```text lint-ignore\n/nosuch:run-a\n```\n`/nosuch:run-b`\n"
    assert codes(text) == ["M4"]


def test_unclosed_ignore_fence_is_reported():
    """閉じ忘れた除外フェンスは以降の全行を無言で検査対象から外す。

    「検査が消えたのに緑」は最悪の失敗様式なので、opt-out の使い方自体を検査する。
    """
    text = "```text lint-ignore\n/nosuch:run-a\n"
    errs = check(text)
    assert any("lint-ignore" in e and "閉じられて" in e for e in errs), errs


def test_ignore_fence_is_not_closed_by_a_nested_opening_fence():
    """除外ブロック内に現れたフェンス行で除外が早期終了すると、以降が意図せず戻る。"""
    text = "````text lint-ignore\n```\n/nosuch:run-a\n````\n`/nosuch:run-b`\n"
    assert codes(text) == ["M4"]


def test_local_marketplace_without_name_is_input_error(tmp_path: Path):
    """公開側と同じ扱いにする。飛ばすと正しい @harness-local が濡れ衣の M2 になる。"""
    broken, ok = tmp_path / "broken", tmp_path / "ok"
    broken.mkdir()
    ok.mkdir()
    assert _rc(_skeleton(broken, local={"plugins": [{"name": "alpha"}]})) == 2
    assert _rc(_skeleton(ok, local={"name": "harness-local", "plugins": []})) == 0


def test_slash_command_regex_ignores_urls_and_dates():
    """URL を 1 本書いただけで CI が赤くなるなら検査対象の取り違え。"""
    for text in (
        "参考: https://example.com/foo:bar",
        "記録: 2026/08:17 に実施",
        "パス: ./docs/plugin:note を参照",
    ):
        assert check(text) == [], text


def test_m5_detects_renamed_skill():
    """plugin 改名と skill 改名は同じ事故クラス。片方だけ守らない。"""
    assert codes("`/alpha:no-such-skill`") == ["M5"]
    assert check("`/alpha:run-something`") == []


def test_m1_does_not_trip_on_japanese_punctuation():
    """正しい repo 名を書いていても句読点が続くだけで赤くなるのは検査対象の取り違え。"""
    for text in (
        f"/plugin marketplace add {REPO}。次に",
        f"/plugin marketplace add {REPO}、それから",
        f"（/plugin marketplace add {REPO}）",
    ):
        assert check(text) == [], text


def test_slash_command_violations_carry_line_numbers():
    """M1-M3 が README.md:<行> を出すのに M4/M5 だけ出さないのは粒度の不揃い。"""
    errs = check("ok\nok\n`/nosuch:run-x`")
    assert errs and errs[0].startswith("README.md:3:"), errs


# --- 統合: 実 repo の README -----------------------------------------------


def test_real_readme_passes():
    proc = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def _real_inputs() -> tuple[str, str, dict, set, dict]:
    """実 repo の marketplace / plugins を読み、check_install_docs の引数一式を返す。"""
    public = MOD.load_json(MOD.PUBLIC_MK)
    bundles = MOD.load_json(MOD.BUNDLES)
    local = MOD.load_json(MOD.LOCAL_MK)
    catalogs = {
        public["name"]: MOD.catalog_names(public["plugins"], "p")
        | MOD.catalog_names(bundles["bundles"], "b"),
        local["name"]: MOD.catalog_names(local["plugins"], "l"),
    }
    on_disk = {d.name for d in MOD.PLUGINS_DIR.iterdir() if d.is_dir() and not d.name.startswith(".")}
    skills = {
        n: {s.name for s in (MOD.PLUGINS_DIR / n / "skills").iterdir() if (s / "SKILL.md").is_file()}
        for n in on_disk
        if (MOD.PLUGINS_DIR / n / "skills").is_dir()
    }
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    return text, public["metadata"]["repository"], catalogs, on_disk, skills


def test_real_readme_check_is_not_vacuous():
    """「実 README が緑」だけでは検査が働いているかを何も言えない。

    実 README の実在行を 1 箇所ずつ壊し、5 事故クラスすべてが検出されることを
    確認する。ここが緑のままなら走査範囲が実手順を素通りしている。
    """
    text, repository, catalogs, on_disk, skills = _real_inputs()
    base = MOD.check_install_docs(text, repository, catalogs, on_disk, skills)
    assert base == [], base

    mutations = [
        ("M1", "/plugin marketplace add daishiman/harness-dev", "/plugin marketplace add manju/skills"),
        ("M2", "/plugin install skill-intake@skills", "/plugin install skill-intake@nosuchmarket"),
        ("M3", "/plugin install skill-intake@skills", "/plugin install skill-creator@skills"),
        ("M4", "/skill-intake:run-skill-intake", "/nosuchplugin:run-skill-intake"),
        ("M5", "/skill-intake:run-skill-intake", "/skill-intake:run-nosuch-skill"),
    ]
    for code, needle, repl in mutations:
        assert needle in text, f"{needle!r} が README から消えた。変異テストの対象を更新すること"
        errs = MOD.check_install_docs(
            text.replace(needle, repl, 1), repository, catalogs, on_disk, skills
        )
        assert [e for e in errs if f" {code} " in e], f"{code} を壊しても検出されない: {errs}"


def test_repository_is_declared_in_marketplace_metadata():
    """SSOT である metadata.repository が欠けたら lint は exit 2 (入力不備) になる契約。"""
    import json

    mk = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    repository = mk.get("metadata", {}).get("repository")
    assert repository, "metadata.repository が install 導線の正本として必要"
    assert "/" in repository, f"<owner>/<repo> 形式であること: {repository!r}"


# --- 入力不備は宣言どおり exit 2 か (traceback で exit 1 に化けないか) ------


def _skeleton(
    tmp_path: Path, *, plugins: bool = True, mk: dict | None = None, local: dict | None = None
) -> Path:
    """script を複製した最小 repo を作り、その複製パスを返す。"""
    (tmp_path / "scripts").mkdir()
    copy = tmp_path / "scripts" / SCRIPT.name
    copy.write_text(SCRIPT.read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "README.md").write_text("# readme\n", encoding="utf-8")
    (tmp_path / ".claude-plugin").mkdir()
    default = {"name": "skills", "metadata": {"repository": REPO}, "plugins": [{"name": "alpha"}]}
    (tmp_path / ".claude-plugin" / "marketplace.json").write_text(
        json.dumps(mk if mk is not None else default), encoding="utf-8"
    )
    (tmp_path / ".claude-plugin" / "bundles.json").write_text('{"bundles": []}', encoding="utf-8")
    if local is not None:
        d = tmp_path / "marketplaces" / "local" / ".claude-plugin"
        d.mkdir(parents=True)
        (d / "marketplace.json").write_text(json.dumps(local), encoding="utf-8")
    if plugins:
        (tmp_path / "plugins" / "alpha").mkdir(parents=True)
    return copy


def _rc(copy: Path) -> int:
    return subprocess.run([sys.executable, str(copy)], capture_output=True, text=True).returncode


def test_missing_plugins_dir_is_input_error(tmp_path: Path):
    assert _rc(_skeleton(tmp_path, plugins=False)) == 2


def test_marketplace_entry_without_name_is_input_error(tmp_path: Path):
    """JSON としては妥当だが契約違反。KeyError の traceback (exit 1) にしない。"""
    broken = {"name": "skills", "metadata": {"repository": REPO}, "plugins": [{"source": "./x"}]}
    assert _rc(_skeleton(tmp_path, mk=broken)) == 2


def test_non_object_marketplace_is_input_error(tmp_path: Path):
    assert _rc(_skeleton(tmp_path, mk=["not", "an", "object"])) == 2


def test_marketplace_without_name_is_input_error(tmp_path: Path):
    """name が欠けると catalogs が空になり、M2 が全 install 行を誤検出するか、

    install 行が無ければ静かに緑になる。どちらも検査として意味を成さない。
    """
    broken = {"metadata": {"repository": REPO}, "plugins": [{"name": "alpha"}]}
    assert _rc(_skeleton(tmp_path, mk=broken)) == 2
