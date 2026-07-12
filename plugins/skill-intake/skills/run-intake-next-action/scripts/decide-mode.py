#!/usr/bin/env python3
"""kickoff/purpose/options/summary から mode を機械判定。LLM は呼ばない。

precondition gate (逸脱B封鎖): skill 生成 (run-skill-create) へ進む handoff を確定する前に、
Notion 公開完了を必須前提として検証する。`output/<hint>/notion-publish-result.json` が存在し、
かつ `notion-log.json.status == "published"` でなければ exit 2 で停止し、未公開のまま skill
生成へ横流れさせない。CI / dry-run 用に `--allow-skip` 明示時のみ gate を緩和する。
"""
import argparse, json, os, re, sys
from pathlib import Path


PUBLISH_RESULT_NAME = "notion-publish-result.json"
NOTION_LOG_NAME = "notion-log.json"
INTAKE_JSON_NAME = "intake.json"


def canonical_notion_id(value):
    if not value:
        return ""
    compact = re.sub(r"[^0-9a-fA-F]", "", str(value)).lower()
    if len(compact) == 32:
        return f"{compact[0:8]}-{compact[8:12]}-{compact[12:16]}-{compact[16:20]}-{compact[20:32]}"
    token = str(value).split("?")[0].rstrip("/").split("/")[-1].split("-")[-1]
    if re.fullmatch(r"[0-9a-fA-F]{32}", token):
        compact = token.lower()
        return f"{compact[0:8]}-{compact[8:12]}-{compact[12:16]}-{compact[16:20]}-{compact[20:32]}"
    return ""


def check_publish_precondition(out_path: Path):
    """skill 生成へ進む前提として Notion 公開完了を検証。
    返り値: (ok: bool, reason: str)。out_path の親 (= output/<hint>/) を SSOT 位置とみなす。"""
    out_dir = out_path.resolve().parent
    result_path = out_dir / PUBLISH_RESULT_NAME
    log_path = out_dir / NOTION_LOG_NAME
    if not result_path.exists():
        return False, f"{result_path} が存在しない (Notion 未公開のまま skill 生成へ進めない)"
    if not log_path.exists():
        return False, f"{log_path} が存在しない (publish ログ未生成)"
    try:
        log = json.loads(log_path.read_text(encoding="utf-8"))
    except Exception as e:
        return False, f"{log_path} 読込失敗: {e}"
    status = log.get("status")
    if status != "published":
        return False, f"notion-log.json.status={status!r} (期待: 'published')"
    try:
        result = json.loads(result_path.read_text(encoding="utf-8"))
    except Exception as e:
        return False, f"{result_path} 読込失敗: {e}"
    if not (result.get("page_id") or result.get("id")):
        return False, f"{result_path} に page_id が無い (公開未確定)"
    result_page_id = result.get("page_id") or result.get("id")
    log_page_id = log.get("page_id")
    if log_page_id and canonical_notion_id(log_page_id) != canonical_notion_id(result_page_id):
        return False, "notion-log.json.page_id と notion-publish-result.json.page_id が一致しない"
    intake_path = out_dir / INTAKE_JSON_NAME
    if intake_path.exists():
        try:
            intake = json.loads(intake_path.read_text(encoding="utf-8"))
        except Exception as e:
            return False, f"{intake_path} 読込失敗: {e}"
        target = intake.get("notion_target") if isinstance(intake, dict) else None
        target_page_id = canonical_notion_id((target or {}).get("page_id") or (target or {}).get("page_url"))
        if target_page_id and canonical_notion_id(result_page_id) != target_page_id:
            return False, (
                "notion_target.page_id と publish result page_id が一致しない "
                f"(target={target_page_id}, result={result_page_id})"
            )
    return True, "Notion 公開完了を確認 (status=published, page_id 有り, target 一致)"


NON_SKILL_COMPONENT_KINDS = {"hook", "command", "slash-command", "agent", "sub-agent", "mcp"}


def detect_plugin_scale(kick, opts, summ):
    """mode P (plugin 規模構想) の決定論判定。正本: references/mode-catalog.md「mode P 判定条件」。
    返り値: (is_p: bool, reason: str)。既存 A-E 判定より先に評価する。"""
    for label, src in (("summary", summ), ("options", opts), ("kickoff", kick)):
        if isinstance(src, dict) and src.get("plugin_scale") is True:
            return True, f"{label}.plugin_scale=true の明示宣言 (mode-catalog P 行: plugin 規模構想)"
    requests = []
    for src in (summ, opts):
        if isinstance(src, dict) and isinstance(src.get("component_requests"), list):
            requests.extend(str(x).strip().lower() for x in src["component_requests"])
    non_skill = sorted({r for r in requests if r in NON_SKILL_COMPONENT_KINDS})
    if non_skill:
        return True, (
            f"component_requests に非 skill コンポーネント {non_skill} の要望 "
            "(mode-catalog P 行: 複数コンポーネント/hook/command 要望)"
        )
    skill_like = [r for r in requests if r not in NON_SKILL_COMPONENT_KINDS]
    if len(skill_like) >= 2:
        return True, (
            f"component_requests に skill 系要素が {len(skill_like)} 件 "
            "(mode-catalog P 行: 複数 skill 分解が濃厚)"
        )
    return False, ""


def load_json_required(path: str, label: str):
    p = Path(path)
    if not p.exists():
        sys.stderr.write(f"[decide-mode] input missing: {label}={p}\n")
        sys.exit(3)
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        sys.stderr.write(f"[decide-mode] input invalid: {label}={p}: {e}\n")
        sys.exit(3)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--kickoff", required=True)
    p.add_argument("--purpose", required=True)
    p.add_argument("--options", required=True)
    p.add_argument("--summary", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--allow-skip", action="store_true",
                   help="CI/dry-run 用: Notion 公開 precondition gate を緩和 (本番では使わない)")
    a = p.parse_args()

    # precondition gate: Notion 公開完了が skill 生成の必須前提 (逸脱B封鎖)。
    ok, reason = check_publish_precondition(Path(a.out))
    if not ok:
        if a.allow_skip:
            if os.environ.get("INTAKE_ALLOW_SKIP_PUBLISH_GATE") != "1":
                sys.stderr.write(
                    "[decide-mode] BLOCK: --allow-skip requires INTAKE_ALLOW_SKIP_PUBLISH_GATE=1 "
                    "(CI/dry-run 以外での迂回を禁止)。\n"
                )
                sys.exit(2)
            sys.stderr.write(
                f"[decide-mode] WARN: publish precondition 未充足だが --allow-skip により続行: {reason}\n"
            )
        else:
            sys.stderr.write(
                f"[decide-mode] BLOCK: Notion 公開完了が skill 生成の必須前提です。{reason}\n"
                f"  先に intake_publish_pipeline.py で Notion 公開を完了させてください。\n"
                f"  (CI/dry-run のみ --allow-skip で緩和可)\n"
            )
            sys.exit(2)
    kick = load_json_required(a.kickoff, "kickoff")
    purp = load_json_required(a.purpose, "purpose")
    _opts = load_json_required(a.options, "options")
    summ = load_json_required(a.summary, "summary")
    verb = purp.get("true_purpose", {}).get("verb_object", "")
    # 簡易判定: plugin 規模徴候 (mode P) を最優先で評価し、無ければ Phase 1 の暫定 pattern を
    # 尊重しつつ、verb 空・分裂検知時のみ E/D に格下げ。
    init = kick.get("pattern", "E")
    mode = init
    reason = f"kickoff.pattern={init} を採用"
    multi = False
    splits = []
    is_p, p_reason = detect_plugin_scale(kick, _opts, summ)
    if is_p:
        mode = "P"
        multi = True
        reason = p_reason
    elif not verb.strip():
        mode = "E"
        reason = "true_purpose.verb_object が空のため判定不能"
    elif " と " in verb or "+" in verb:
        mode = "D"
        multi = True
        reason = "verb_object に複数責務の徴候 (連結語) あり"
    # 右列文言は references/mode-catalog.md の逐語コピー (drift 防止)。
    handoff = {
        "A": "Step 1 (elicit)",
        "B": "Step 1 (elicit --mode update)",
        "C": "Step 1 (elicit --mode update, prompt-only)",
        "D": "Step 1 (elicit, split first)",
        "E": "P1-kickoff (re-intake)",
        "P": "R1 (elicit-goal)",
    }[mode]
    out = {
        "mode": mode,
        "reason": reason,
        "multi_skill_suspicion": multi,
        "split_candidates": splits,
        "confirmed_with_user": False,
        "handoff_target": "plugin-dev-planner" if mode == "P" else "harness-creator",
        "harness_creator_handoff_phase": handoff,
    }
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"mode={mode}")


if __name__ == "__main__":
    main()
