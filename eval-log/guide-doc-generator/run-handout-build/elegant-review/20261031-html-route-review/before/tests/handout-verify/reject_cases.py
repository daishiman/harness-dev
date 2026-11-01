"""非受入例 (reject fixture) の定義。

受入例 `fixtures/accept/commands/handout-verify.md` に対して 1 箇所だけ契約違反を
注入した固定入力を作る。各ケースは「どの契約 id が落ちるべきか」を明示的に持ち、
チェッカが常時 PASS する空ゲートになっていないことを固定する。
"""

# (case_name, 置換前, 置換後, 落ちるべき契約 id)
REJECT_CASES = [
    # --- frontmatter ------------------------------------------------------
    (
        "allowed-tools-has-write",
        "allowed-tools: [Read, Bash]",
        "allowed-tools: [Read, Bash, Write]",
        "AC-C09-1",
    ),
    (
        "allowed-tools-has-skill",
        "allowed-tools: [Read, Bash]",
        "allowed-tools: [Read, Bash, Skill]",
        "AC-C09-1",
    ),
    (
        "description-drops-c22-face",
        "・語りの一貫性 (C22) の 4 ゲート",
        "の 3 ゲート",
        "AC-C09-1",
    ),
    (
        "argument-hint-drops-only",
        " [--only <gate,...>]",
        "",
        "AC-C09-1",
    ),
    (
        "disable-model-invocation-true",
        "disable-model-invocation: false",
        "disable-model-invocation: true",
        "AC-C09-1",
    ),
    # --- 参照 script ------------------------------------------------------
    (
        "narrative-script-unreferenced",
        "`verify-handout-narrative.py` | `--html` `--config` `--json-report`",
        "(未定) | `--html` `--config` `--json-report`",
        "AC-C09-2",
    ),
    (
        "plugin-root-resolution-dropped",
        "`${HB_ROOT:-$CLAUDE_PLUGIN_ROOT}/scripts/<script>.py`",
        "`./scripts/<script>.py`",
        "AC-C09-2",
    ),
    # --- 集約規則 ---------------------------------------------------------
    (
        "not-run-folded-into-pass",
        '{"when": {"any_state": ["not-run"]}, "verdict": "incomplete"}',
        '{"when": {"any_state": ["not-run"]}, "verdict": "pass"}',
        "AC-C09-AGG-2",
    ),
    (
        "error-not-failing-closed",
        '{"when": {"any_state": ["fail", "error"]}, "verdict": "fail"}',
        '{"when": {"any_state": ["fail"]}, "verdict": "fail"}',
        "AC-C09-AGG-2",
    ),
    (
        "only-run-claims-pass",
        '{"when": {"only_used": true}, "verdict": "partial"}',
        '{"when": {"only_used": true}, "verdict": "pass"}',
        "AC-C09-AGG-2",
    ),
    (
        "gate-faces-reduced-to-three",
        '    "narrative": "C22"\n  },',
        "  },",
        "AC-C09-AGG-2",
    ),
    (
        "not-run-reason-dropped",
        '    "script-absent"\n',
        "",
        "AC-C09-AGG-2",
    ),
    (
        "aggregation-block-missing",
        '"id": "CR-GATE-AGG",',
        '"id": "SOMETHING-ELSE",',
        "AC-C09-AGG-2",
    ),
    # --- 縮退 -------------------------------------------------------------
    (
        "config-missing-verdict-relaxed",
        "全体 verdict は incomplete",
        "全体 verdict は pass",
        "AC-C09-3",
    ),
    (
        "fail-fast-introduced",
        "- あるゲートが落ちても後続ゲートを止めずに全ゲートを走らせる (fail-fast にしない)",
        "- あるゲートが落ちたらそこで打ち切る",
        "AC-C09-4",
    ),
    (
        "excluded-by-only-dropped",
        "not-run (excluded-by-only)",
        "報告から除外",
        "AC-C09-5",
    ),
    (
        "script-absent-dropped",
        "not-run (script-absent)",
        "skip",
        "AC-C09-9",
    ),
    (
        "entry-stop-relaxed",
        "1 ゲートも実行せず停止する。空の集約結果を pass として返さない",
        "空の集約結果を返す",
        "AC-C09-7",
    ),
    (
        "strict-validation-dropped",
        "`validate-handout-config.py --strict` (書き込みなし) で検出し、",
        "目視で判断し、",
        "AC-C09-3",
    ),
    # --- 境界 -------------------------------------------------------------
    (
        "normalization-taken-over",
        "この command 側で正規化して通すことはしない",
        "この command 側で正規化する",
        "AC-C09-6",
    ),
    # --- 報告 -------------------------------------------------------------
    (
        "not-run-rows-omitted",
        "実行しなかったゲートを表から省かない。",
        "実行したゲートだけを表に出す。",
        "AC-C09-10",
    ),
    (
        "summary-drops-gate-states",
        "`gates` 状態一覧を含む",
        "だけを含む",
        "AC-C09-10",
    ),
    # --- C01 との一致 -----------------------------------------------------
    (
        "consumer-parity-invariant-dropped",
        "同一の 4 ゲート実行結果に対しては必ず同一の\nverdict を受け取る",
        "適宜結果を参照する",
        "AC-C09-AGG-1",
    ),
]
