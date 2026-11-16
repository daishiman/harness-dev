#!/usr/bin/env python3
"""live-trial 実走 acceptance 証拠 (verdict.json) を機械検査する (offline, tmux/LLM 不実行)。

役割境界 (D9: lint-content-review 同型の最終強制層):
  - 機械層: 受理証跡 1 件の schema 適合 / skill_dir_tree_sha 再計算突合 /
            overall.verdict=PASS / tier 降格・denylist 被験体の除外 を検査。
            criteria receipt が live-trial PASS を指すときはその verdict を受理証跡にする。
            辞書順で新しい BLOCKED/DEGRADED/FAIL は、receipt が採用した current PASS を
            隠さない。receipt が無い skill だけ最新 run-id を見る。
  - 実走層 (本 lint の対象外): trial 実行はローカル claude + tmux で run-skill-live-trial
            を起動して行う (リモート CI での LLM/tmux 実行は D14 で却下済み)

検証実装は run-skill-live-trial 同梱の validate_schema / skill_dir_tree_sha を
importlib で再利用する (SSOT: 生成側と検査側の実装乖離を排除)。

D13 パイロットゲート: verdict **不在** は FAIL にしない (record-only WARN + 件数出力)。
--enforce (P3 常設化 go/no-go で昇格するまで既定 OFF) 指定時のみ不在も FAIL。
verdict が **存在する** 場合の schema 不適合 / FAIL verdict / downgrade / denylist は
パイロット中も exit 1 (存在する証拠の偽装は soft にしない)。
stale-sha (古い挙動閉包に対する PASS) は既定で「要再実走」WARN に留める。CI では
実走できない (D14) ため、FAIL にすると変更のたびに手元で再実走ループが走る。
--enforce か LIVE_TRIAL_ENFORCE_FRESHNESS=1 のとき FAIL (方針の正本は
live-trial-verdict.py の freshness_enforced)。WARN でも sha の手書き更新はしない。
stale-sha は、verdict を commit したツリーと今の挙動閉包を比べ、挙動投影が
変わったファイル名を同じ行に出す。manifest の version だけが動いたファイルは
出さない。
Codex verdict の本文照合 (native-skill-source/activation-unproven) は、閉包が古いと
今の SKILL.md とは必ず合わない。受領 commit の閉包を展開して digest が記録と一致し、
その本文で照合し直して通るときだけ、stale-sha の行へ畳んで WARN にする。通らない・
受領 commit が無い・展開できないときは FAIL のまま (起動の証明が無い verdict を
古さの陰に隠さない)。

Usage:
  python3 scripts/lint-live-trial-verdict.py --all [--enforce]
  LIVE_TRIAL_ENFORCE_FRESHNESS=1 python3 scripts/lint-live-trial-verdict.py --all
  python3 scripts/lint-live-trial-verdict.py --plugin harness-creator [--enforce]
  python3 scripts/lint-live-trial-verdict.py --self-test
"""
import argparse
import importlib.util
import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGINS_DIR = ROOT / "plugins"
EVAL_LOG = ROOT / "eval-log"
# harness 正本の所在は PLUGINS_DIR と独立に固定する (テストが PLUGINS_DIR を
# tmp へ差し替えても SSOT 実装のロード元は実 repo のまま)
HARNESS_SKILL_DIR = (
    Path(__file__).resolve().parent.parent
    / "plugins" / "harness-creator" / "skills" / "run-skill-live-trial"
)
EVIDENCE_SELECTION = (
    Path(__file__).resolve().parent.parent
    / "plugins" / "dev-graph" / "lib" / "live_trial_evidence_selection.py"
)

sys.path.insert(0, str(ROOT / "scripts"))
import feedback_contract_ssot as FC  # noqa: E402


def _load_module(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem.replace("-", "_"), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_harness():
    """(verdict_mod, backend_mod, schema_dict) — 生成側実装の再利用が SSOT。"""
    verdict_mod = _load_module(HARNESS_SKILL_DIR / "scripts" / "live-trial-verdict.py")
    backend_mod = _load_module(HARNESS_SKILL_DIR / "scripts" / "live-trial-backend.py")
    schema = json.loads(
        (HARNESS_SKILL_DIR / "schemas" / "live-trial-verdict.schema.json").read_text(encoding="utf-8")
    )
    return verdict_mod, backend_mod, schema


def _all_skills(plugin_filter=None):
    skills = set()
    if not PLUGINS_DIR.exists():
        return skills
    for plugin_dir in PLUGINS_DIR.iterdir():
        if not plugin_dir.is_dir():
            continue
        if plugin_filter and plugin_dir.name != plugin_filter:
            continue
        sk_dir = plugin_dir / "skills"
        if not sk_dir.is_dir():
            continue
        for s in sk_dir.iterdir():
            if s.is_symlink() or FC.is_vendored_feedback_skill(s, plugins_dir=PLUGINS_DIR):
                continue
            if (s / "SKILL.md").is_file():
                skills.add((plugin_dir.name, s.name))
    return skills


def _declares_live_trial(plugin, skill):
    """frontmatter feedback_contract の criteria に verify_by: live-trial があるか。"""
    md = PLUGINS_DIR / plugin / "skills" / skill / "SKILL.md"
    try:
        fc = FC.extract_frontmatter_feedback_contract(md.read_text(encoding="utf-8"))
    except OSError:
        return False
    criteria = fc.get("criteria") if isinstance(fc, dict) else None
    if not isinstance(criteria, list):
        return False
    return any(
        isinstance(c, dict) and c.get("verify_by") == "live-trial" for c in criteria
    )


def _evidence_selection():
    """criteria receipt の受理選択。PLUGINS_DIR を差し替えても実装元は repo に固定する。"""
    return _load_module(EVIDENCE_SELECTION)


def acceptance_verdict_path(plugin, skill):
    """受理証跡。receipt の PASS を優先し、receipt が無いときだけ最新 run-id。

    戻り値は (path, error)。error があるとき path は使わない (壊れた receipt を
    新しい FAIL/PASS へ読み替えない)。
    """
    selected, error = _evidence_selection().verdict_selection_from_criteria_receipt(
        EVAL_LOG.parent, plugin, skill,
    )
    if error:
        return None, error
    if selected is not None:
        return selected, None
    return latest_verdict_path(plugin, skill), None


def latest_verdict_path(plugin, skill):
    """最新 run-id (辞書順最大) の verdict.json。無ければ None。"""
    base = EVAL_LOG / plugin / skill / "live-trial"
    if not base.is_dir():
        return None
    candidates = sorted(
        (d for d in base.iterdir() if d.is_dir() and (d / "verdict.json").is_file()),
        key=lambda d: d.name,
    )
    return (candidates[-1] / "verdict.json") if candidates else None


# 挙動閉包が古い Codex verdict で、transcript が読んだ本文が今の SKILL.md と
# 合わないことから出る誤り (extract-codex-transcript.py の本文照合)。
STALE_SOURCE_ERRORS = ("native-skill-source-unproven", "native-skill-activation-unproven")


def _closure_roots(labels):
    """閉包 label を、受領 commit から展開する単位 (plugin dir か単独ファイル) にまとめる。"""
    roots = set()
    for label in labels:
        parts = label.split("/")
        roots.add("/".join(parts[:2]) if parts[0] == "plugins" and len(parts) > 2 else label)
    return sorted(roots)


_STDLIB_LINK_CHECK_SOUND = None


def _stdlib_link_check_sound():
    """stdlib の data filter が、symlink の行き先を link 自身の dir から計算するか。

    Python 3.11.4 の data filter は行き先を展開先の根から計算し、下位 dir にある
    中を指す相対 link を外と誤って拒む (gh-107845)。版の番号ではなく、その link を
    1 件判定させた結果で見分ける。結果は process の中で使い回す。
    """
    global _STDLIB_LINK_CHECK_SOUND
    if _STDLIB_LINK_CHECK_SOUND is None:
        probe = tarfile.TarInfo("probe/link")
        probe.type = tarfile.SYMTYPE
        probe.linkname = "../target"
        with tempfile.TemporaryDirectory() as tmp:
            try:
                tarfile.data_filter(probe, tmp)
                _STDLIB_LINK_CHECK_SOUND = True
            except tarfile.LinkOutsideDestinationError:
                _STDLIB_LINK_CHECK_SOUND = False
    return _STDLIB_LINK_CHECK_SOUND


def _member_filter(member, dest_path):
    """展開に使う filter。stdlib の data filter が正しく判定できる版では、それをそのまま使う。

    gh-107845 を抱える版でだけ、symlink の行き先の検査を差し替える。行き先は upstream の
    修正と同じく link 自身の dir から realpath で求める。realpath は先に展開した link を
    ディスク上でたどるので、link を経由する連鎖 (p/x -> . の後の p/x/y -> ../..) と、
    大文字小文字を区別しない FS での衝突 (p/X -> . と p/x/y) も外を指すとして拒む。
    絶対 path の link も拒む。
    """
    if not member.issym() or _stdlib_link_check_sound():
        return tarfile.data_filter(member, dest_path)
    if os.path.isabs(member.linkname):
        raise tarfile.AbsoluteLinkError(member)
    base = os.path.realpath(dest_path)
    target = os.path.realpath(os.path.join(base, os.path.dirname(member.name), member.linkname))
    if os.path.commonpath([base, target]) != base:
        raise tarfile.LinkOutsideDestinationError(member, target)
    return tarfile.tar_filter(member, dest_path)


def _extract_baseline(commit, roots, dest):
    """``commit`` の ``roots`` を dest へ展開する。

    git が無い・読めない、または展開が安全でないときは False。
    """
    try:
        present = [
            root for root in roots
            if subprocess.run(["git", "cat-file", "-e", f"{commit}:{root}"],
                              cwd=ROOT, capture_output=True).returncode == 0
        ]
        if not present:
            return False
        proc = subprocess.run(["git", "archive", "--format=tar", commit, "--", *present],
                              cwd=ROOT, capture_output=True)
    except OSError:
        return False
    if proc.returncode != 0:
        return False
    try:
        with tarfile.open(fileobj=io.BytesIO(proc.stdout)) as archive:
            archive.extractall(dest, filter=_member_filter)
    except (tarfile.TarError, OSError):
        return False
    return True


def stale_source_explained(verdict_mod, data, path, skill_dir, runtime_errors, commit):
    """本文照合の誤りが「閉包が古い」だけで説明できるか。

    受領 commit (verdict を最後に commit した revision) の閉包を一時展開し、次の 2 つが
    そろうときだけ説明できるとみなす。そろわないときは FAIL のまま残す (fail-closed)。
      1. 展開したツリーで計算した閉包 digest が verdict の skill_dir_tree_sha と一致する
      2. そのツリーを基準に検査し直した誤りが、今のツリーで出ている本文照合以外の誤りに
         すべて含まれる。本文照合の誤りは「以外」に入らないので、受領 commit の本文で
         照合しても外れるなら、この条件で落ちる。新しい誤りが出たときも落ちる
    commit は verdict_baseline_commit の値。未追跡の verdict (commit が None)・git が
    無い・読めない環境・展開の失敗・閉包に symlink の輪がある (3.11/3.12 の
    RuntimeError) ときは、どれも False になる。
    """
    if not commit:
        return False
    try:
        relative = skill_dir.resolve().relative_to(ROOT.resolve())
        labels = [label for label, _ in verdict_mod.behavior_closure_files(skill_dir, runtime="codex")]
    except ValueError:
        return False
    others = {error for error in runtime_errors if not error.startswith(STALE_SOURCE_ERRORS)}
    with tempfile.TemporaryDirectory() as tmp:
        if not _extract_baseline(commit, _closure_roots(labels), tmp):
            return False
        baseline_dir = Path(tmp) / relative
        try:
            if verdict_mod.skill_dir_tree_sha(baseline_dir, runtime="codex") != data.get("skill_dir_tree_sha"):
                return False
            baseline_errors = verdict_mod.validate_runtime_evidence(
                data, path.parent / "transcript.jsonl", baseline_dir,
            )
        except (OSError, ValueError, RuntimeError):
            return False
    return set(baseline_errors) <= others


def check_verdict(path, plugin, skill, verdict_mod, backend_mod, schema):
    """verdict 1 件の違反リストを返す (空 = 合格)。"""
    errs = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"invalid-json: {exc}"]
    schema_errs = verdict_mod.validate_schema(data, schema)
    if schema_errs:
        return [f"schema: {e}" for e in schema_errs]

    target = str(data.get("target_skill", ""))
    if target.rsplit(":", 1)[-1] != skill:
        errs.append(f"target-mismatch: target_skill={target!r} が置き場所 {plugin}/{skill} と不一致")
    if backend_mod.deny_target_skill(target):
        errs.append(
            f"denylist-subject: {target} は再帰遮断対象 — この証拠は存在してはならない "
            f"({sorted(backend_mod.DENY_TARGET_SKILLS)})"
        )

    skill_dir = PLUGINS_DIR / plugin / "skills" / skill
    runtime = data.get("environment", {}).get("runtime", "claude")
    if (skill_dir / "SKILL.md").is_file():
        current_sha = (verdict_mod.skill_dir_tree_sha(skill_dir, runtime=runtime)
                       if runtime == "codex" else verdict_mod.skill_dir_tree_sha(skill_dir))
        stale_line = commit = None
        if data.get("skill_dir_tree_sha") != current_sha:
            used_runtime = runtime if runtime == "codex" else "claude"
            labels = None
            commit = verdict_mod.verdict_baseline_commit(ROOT, path)
            if commit:
                labels = verdict_mod.closure_drift_labels(
                    ROOT, skill_dir, commit, runtime=used_runtime,
                )
            stale_line = verdict_mod.format_stale_sha(
                data.get("skill_dir_tree_sha"), current_sha, labels,
            )
        runtime_errors = []
        if runtime == "codex":
            runtime_errors = verdict_mod.validate_runtime_evidence(
                data, path.parent / "transcript.jsonl", skill_dir,
            )
            source_errors = [e for e in runtime_errors if e.startswith(STALE_SOURCE_ERRORS)]
            # 古い閉包では、今の本文との照合は必ず外れる。受領 commit の本文で
            # 照合し直して通るときだけ、その誤りを stale-sha の行へ畳む (同じ古さを
            # 二重に FAIL にしない)。通らないときは起動の証明が無いので FAIL のまま。
            if stale_line and source_errors and stale_source_explained(
                verdict_mod, data, path, skill_dir, runtime_errors, commit,
            ):
                runtime_errors = [e for e in runtime_errors if e not in source_errors]
                stale_line += (
                    f" / 本文照合 {', '.join(source_errors)} は受領 commit {commit[:12]}"
                    " の本文では通る (今の SKILL.md と違うのは閉包が古いため)"
                )
        if stale_line:
            errs.append(stale_line)
        for error in runtime_errors:
            errs.append(f"runtime-evidence: {error}")

    # 降格除外: tier が live 未満 or downgrade_reason 有りは PASS 扱い禁止 (D13)
    if data.get("tier") != "live" or data.get("downgrade_reason") is not None:
        errs.append(
            f"downgraded: tier={data.get('tier')} reason={data.get('downgrade_reason')!r} "
            "— live 受け入れ証拠として無効 → human_review で降格理由の妥当性を人間判断すること"
        )
    v = (data.get("overall") or {}).get("verdict")
    if v != "PASS":
        errs.append(f"verdict={v} (PASS のみ受理。DEGRADED/FAIL/BLOCKED は再 trial 要)")
    # 免除の接地を verdict 単体で検査する。live-trial-verdict.py は根拠なき
    # contractual を exit 2 で拒否するが、lint 側でも見ないと手書き verdict が
    # CLI を迂回して免除を主張できてしまう (自己申告での降格回避)。
    if (data.get("gate_response_count") or 0) > 0 and data.get("gate_kind") == "contractual":
        if not data.get("gate_contract_evidence"):
            errs.append(
                "gate_kind=contractual だが gate_contract_evidence が空 — 免除が被験 skill の"
                " 宣言 (external_mutation_guard / allowed-tools の AskUserQuestion|ExitPlanMode)"
                " へ接地していない。live-trial-verdict.py 経由で再生成すること"
            )
    return errs


def contractual_exemption(path):
    """契約 gate で自走未達降格を免除された verdict の注記。免除がなければ None。"""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    gate = data.get("gate_response_count") or 0
    if gate > 0 and data.get("gate_kind") == "contractual":
        evidence = data.get("gate_contract_evidence") or []
        return (f"gate_kind=contractual により gate 応答 {gate} 回が自走未達降格から免除された"
                f" (接地根拠: {', '.join(evidence) or 'なし'})"
                " — 被験 skill が契約上その gate を要求することを人間が確認すること")
    return None


def is_advisory(err: str) -> bool:
    """check_verdict のエラーのうち、既定で WARN (要再実走) に留めるものか。

    True を返したエラーは、鮮度強制 (--enforce か LIVE_TRIAL_ENFORCE_FRESHNESS=1)
    が無いとき exit 1 にしない。False のエラーは常に exit 1。

    err の先頭語 (check_verdict が付ける): invalid-json / schema / target-mismatch /
    denylist-subject / stale-sha / runtime-evidence / downgraded / verdict= /
    gate_kind=contractual
    """
    return err.startswith("stale-sha:")


def run_lint(plugin_filter=None, enforce=False):
    verdict_mod, backend_mod, schema = load_harness()
    skills = sorted(_all_skills(plugin_filter))
    strict_freshness = verdict_mod.freshness_enforced(enforce)

    violations = []  # 存在する verdict の違反 (常に exit 1)
    stale = []  # 古い挙動閉包に対する証跡 (既定 WARN、鮮度強制時は violations へ)
    missing = []  # verdict 不在 (D13 パイロットゲート: record-only WARN、--enforce で FAIL)
    exempted = []  # 契約 gate による自走未達免除 (合格だが黙って通さない)
    checked = 0
    for plugin, skill in skills:
        required = (
            _declares_live_trial(plugin, skill)
            and not backend_mod.deny_target_skill(skill)
        )
        latest, selection_error = acceptance_verdict_path(plugin, skill)
        if selection_error:
            violations.append(f"{plugin}/{skill}: {selection_error}")
            continue
        if latest is None:
            if required:
                missing.append(
                    f"{plugin}/{skill}: feedback_contract が verify_by: live-trial を宣言するが"
                    " eval-log/<plugin>/<skill>/live-trial/<run-id>/verdict.json が無い"
                )
            continue
        checked += 1
        for err in check_verdict(latest, plugin, skill, verdict_mod, backend_mod, schema):
            line = f"{plugin}/{skill}: {latest.parent.name}/verdict.json {err}"
            (stale if is_advisory(err) and not strict_freshness else violations).append(line)
        # 契約 gate 免除は「降格しない」だけで「無かったこと」ではない。
        # 免除が黙って通ると、rescue を contractual と申告するだけで自走未達を消せる。
        note = contractual_exemption(latest)
        if note:
            exempted.append(f"{plugin}/{skill}: {latest.parent.name}/verdict.json {note}")

    if missing:
        level = "FAIL" if enforce else "WARN"
        print(f"[{level}] live-trial verdict 不在: {len(missing)} skill(s)"
              + ("" if enforce else " (D13 パイロットゲート中 record-only。P3 常設化で --enforce に昇格)"))
        for m in missing:
            print(f"  - {m}")
    if exempted:
        print(f"[NOTE] 契約 gate による自走未達免除: {len(exempted)} verdict(s)")
        for e in exempted:
            print(f"  - {e}")
    if stale:
        print(f"[WARN] live-trial verdict 要再実走: {len(stale)} verdict(s)"
              " (挙動閉包が verdict 後に変わった。release 前・定期再取得では"
              f" --enforce か {verdict_mod.FRESHNESS_ENFORCE_ENV}=1 で FAIL にする)")
        for s in stale:
            print(f"  - {s}")
    if violations:
        print(f"[FAIL] live-trial verdict lint: {len(violations)} violation(s)")
        for v in violations:
            print(f"  - {v}")
        print()
        print("Fix: 違反行の挙動差分 path に対し、指定 runtime（Claude Code / Codex）で")
        print("     run-skill-live-trial を実行し、その PASS の verdict.json を保存する。")
        print("     criteria receipt の ref はその run へ更新する。sha の手書きは証拠の偽装になる。")
        return 1
    if enforce and missing:
        return 1
    print(f"[OK] live-trial verdict lint: {checked} verdict(s) verified, {len(stale)} stale (re-trial advised),"
          f" {len(missing)} missing (record-only)")
    return 0


def self_test():
    """合成 fixture で 正 (合格) / 負 (各違反) / 不在 の検出を自己検査する。"""
    global PLUGINS_DIR, EVAL_LOG
    verdict_mod, backend_mod, schema = load_harness()
    orig = (PLUGINS_DIR, EVAL_LOG)
    failures = []
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        PLUGINS_DIR = root / "plugins"
        EVAL_LOG = root / "eval-log"
        skill_dir = PLUGINS_DIR / "demo-plugin" / "skills" / "run-demo"
        (skill_dir / "scripts").mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("---\nname: run-demo\n---\nbody\n", encoding="utf-8")
        (skill_dir / "scripts" / "x.py").write_text("print('x')\n", encoding="utf-8")

        doc = {
            "target_skill": "demo-plugin:run-demo",
            "args": "",
            "requested_model": "",
            "actual_model": ["claude-sonnet-5"],
            "nudge_count": 0,
            "gate_response_count": 0,
            "gate_kind": "rescue",
            "goal_verdict": {"result": "PASS", "blockers": []},
            "overall": {"launch": "PASS", "completion": "PASS", "goal_fit": "PASS", "verdict": "PASS"},
            "skill_dir_tree_sha": verdict_mod.skill_dir_tree_sha(skill_dir),
            "transcript_sha256": None,
            "scenario_origin": "synthetic",
            "environment": {
                "claude_version": "2.0.0",
                "tmux": True,
                "transcript_layer": "jsonl",
                "permissions_mode": "bypassPermissions",
            },
            "tier": "live",
            "downgrade_reason": None,
            "timeline": {"boot_s": 3.0, "poll_exit": "DONE", "wall_clock_s": 60.0},
        }
        vpath = EVAL_LOG / "demo-plugin" / "run-demo" / "live-trial" / "20260702T000000" / "verdict.json"
        vpath.parent.mkdir(parents=True)

        def write(d):
            vpath.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")

        def expect(name, mutate, needle):
            d = json.loads(json.dumps(doc))
            mutate(d)
            write(d)
            errs = check_verdict(vpath, "demo-plugin", "run-demo", verdict_mod, backend_mod, schema)
            hit = (not errs) if needle is None else any(needle in e for e in errs)
            if not hit:
                failures.append(f"{name}: expected {needle!r}, got {errs}")

        expect("valid-pass", lambda d: None, None)
        expect("non-pass", lambda d: d["overall"].__setitem__("verdict", "DEGRADED"), "verdict=DEGRADED")
        expect("stale-sha", lambda d: d.__setitem__("skill_dir_tree_sha", "0" * 64), "stale-sha")
        expect("downgraded", lambda d: (d.__setitem__("tier", "fork"),
                                        d.__setitem__("downgrade_reason", "tmux 不在")), "downgraded")
        expect("extra-key", lambda d: d.__setitem__("score", 95), "schema")
        expect("deny-subject", lambda d: d.__setitem__("target_skill", "x:run-skill-iter-improve"),
               "denylist-subject")
        vpath.write_text("{broken", encoding="utf-8")
        errs = check_verdict(vpath, "demo-plugin", "run-demo", verdict_mod, backend_mod, schema)
        if not any("invalid-json" in e for e in errs):
            failures.append(f"invalid-json: got {errs}")
        if latest_verdict_path("demo-plugin", "no-such-skill") is not None:
            failures.append("missing: 不在 skill で verdict が返った")

    PLUGINS_DIR, EVAL_LOG = orig
    if failures:
        print(f"[FAIL] self-test: {len(failures)} failure(s)")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("[OK] self-test: 8 case(s) passed")
    return 0


def main():
    ap = argparse.ArgumentParser(description="live-trial verdict の機械検査 (D9/D13)")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--all", action="store_true", help="全 plugin を走査")
    g.add_argument("--plugin", help="対象 plugin を限定")
    g.add_argument("--self-test", action="store_true", help="合成 fixture で自己検査")
    ap.add_argument("--enforce", action="store_true",
                    help="verdict 不在と stale-sha も FAIL (exit 1) にする。既定は WARN")
    args = ap.parse_args()

    if args.self_test:
        return self_test()
    return run_lint(plugin_filter=args.plugin, enforce=args.enforce)


if __name__ == "__main__":
    sys.exit(main())
