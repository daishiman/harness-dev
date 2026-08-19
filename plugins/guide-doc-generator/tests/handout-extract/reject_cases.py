"""非受入例の定義。

受入例 `fixtures/accept/commands/handout-extract.md` へ **1 箇所だけ**違反を
注入し、対応する契約 id で落ちることを固定する。各タプルは
(名前, 置換前, 置換後, 期待する契約 id) で、置換前の文字列は受入例に
ちょうど 1 回だけ現れなければならない (test_contract_checker が検査する)。
"""

REJECT_CASES = [
    # --- AC-C08-1 frontmatter --------------------------------------------
    (
        "name-mismatch",
        "name: handout-extract\n",
        "name: handout-extractor\n",
        "AC-C08-1",
    ),
    (
        "description-drops-roundtrip",
        "description: 既存の単一 HTML から構成データの逆抽出と round-trip 判定を手動起動する",
        "description: 既存の単一 HTML から構成データを逆抽出する",
        "AC-C08-1",
    ),
    (
        "argument-hint-drifts-from-inventory",
        'argument-hint: "<html-path> [--out <config.json>]"',
        'argument-hint: "<html-path>"',
        "AC-C08-1",
    ),
    (
        "allowed-tools-drops-skill",
        "allowed-tools: [Read, Write, Bash, Skill]",
        "allowed-tools: [Read, Write, Bash]",
        "AC-C08-1",
    ),
    (
        "allowed-tools-adds-edit",
        "allowed-tools: [Read, Write, Bash, Skill]\n",
        "allowed-tools: [Read, Write, Bash, Skill, Edit]\n",
        "AC-C08-1",
    ),
    (
        "disable-model-invocation-true",
        "disable-model-invocation: false",
        "disable-model-invocation: true",
        "AC-C08-1",
    ),
    # --- AC-C08-2 委譲 -----------------------------------------------------
    (
        "delegation-form-paraphrased",
        '`Skill(run-handout-extract, args="$ARGUMENTS")` を起動し',
        "run-handout-extract skill を呼び出し",
        "AC-C08-2",
    ),
    (
        "responsibility-r2-not-declared",
        "(R2-complete)",
        "(補完)",
        "AC-C08-2",
    ),
    (
        "delegated-script-not-declared",
        " / verify-handout-selfcontained.py",
        "",
        "AC-C08-2",
    ),
    # --- AC-C08-3 round-trip の粒度 ---------------------------------------
    (
        "byte-equality-becomes-a-criterion",
        "HTML のバイト一致は判定しない",
        "HTML のバイト一致も判定する",
        "AC-C08-3",
    ),
    (
        "unrestorable-term-dropped",
        "lead-line と判断軸",
        "lead-line",
        "AC-C08-3",
    ),
    (
        "restorable-term-dropped",
        "セクションの並び / 部品種別 / ",
        "",
        "AC-C08-3",
    ),
    # --- AC-C08-4 境界 -----------------------------------------------------
    (
        "next-step-not-handout-build",
        "`/handout-build --config <出力パス>` である",
        "自分で資料を生成する",
        "AC-C08-4",
    ),
    (
        "absorbs-verification-c09",
        "4 面ゲートの検証 (C09 /handout-verify) は兼ねない。",
        "4 面ゲートの検証 (C09 /handout-verify) も続けて実行する。",
        "AC-C08-4",
    ),
    (
        "offers-content-improvement",
        "資料内容の書き換えはしない。改善提案もしない。",
        "気付いた点は資料内容の書き換えとして改善提案する。",
        "AC-C08-4",
    ),
    # --- AC-C08-ARGS 引数解決 ---------------------------------------------
    (
        "out-default-loses-html-dir",
        '"default": "{html_dir}/handout-config.json"',
        '"default": "handout-config.json"',
        "AC-C08-ARGS",
    ),
    (
        "directory-precondition-removed",
        '    { "when": { "html_path": "dir" }, "action": "stop", "reason": "html-path-is-directory" },\n',
        "",
        "AC-C08-ARGS",
    ),
    (
        "existing-out-silently-delegates",
        '{ "when": { "out_exists": true }, "action": "confirm-overwrite" }',
        '{ "when": { "out_exists": true }, "action": "delegate" }',
        "AC-C08-ARGS",
    ),
    (
        "report-placed-elsewhere",
        '"report_placement": "{out_dir}"',
        '"report_placement": "reports"',
        "AC-C08-ARGS",
    ),
    (
        "overwrite-confirmation-dropped",
        "既存ファイルがある場合は黙って上書きせず、上書きしてよいかを確認する。",
        "既存ファイルがある場合は上書きする。",
        "AC-C08-ARGS",
    ),
    # --- AC-C08-DEGRADE 委譲先不在時の縮退 --------------------------------
    (
        "missing-skill-not-handled",
        "- 委譲先 skill run-handout-extract が見つからない場合は停止し、解決を試みたパスを示す。逆抽出の成功として返さない。\n",
        "",
        "AC-C08-DEGRADE",
    ),
    (
        "missing-script-treated-as-success",
        "が不在の場合も同様に停止し、解決を試みたパスを示す。",
        "が不在の場合は検査を省いて成功とする。",
        "AC-C08-DEGRADE",
    ),
    # --- AC-C08-FM-* 失敗時の扱い -----------------------------------------
    (
        "entry-stop-hides-resolved-path",
        "解決したパスと期待する形 (単一 HTML ファイル) を示す",
        "エラーを表示する",
        "AC-C08-FM-1",
    ),
    (
        "empty-config-returned-as-success",
        "空の構成データを成功として返さない。",
        "空の構成データでも成功として返す。",
        "AC-C08-FM-3",
    ),
    (
        "completion-policy-choice-dropped",
        "推測値の充填・空のまま残置・利用者への確認",
        "推測値の充填",
        "AC-C08-FM-4",
    ),
    (
        "roundtrip-diff-softened",
        "差分ありを等価扱いにしない。",
        "差分が軽微なら等価とみなす。",
        "AC-C08-FM-5",
    ),
    (
        "fabricates-values-to-pass-validate",
        "値を捏造して通すことはしない。",
        "不足フィールドは妥当な値で補って通す。",
        "AC-C08-FM-6",
    ),
    # --- AC-C08-PARSE 入口が自前でパースしない ----------------------------
    (
        "entry-parses-html-itself",
        "Read はこの入力 HTML の存在確認にだけ使う。",
        "Read で読み込んだ HTML を BeautifulSoup で解析して部品を同定する。",
        "AC-C08-PARSE",
    ),
    (
        "entry-claims-interpretation",
        "この command は HTML の解釈にも構成データの補完にも関与しない。",
        "この command が HTML の解釈と構成データの補完を行う。",
        "AC-C08-PARSE",
    ),
]
