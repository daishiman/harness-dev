"""validate-briefing-docs.mjs: 文書の章立て・番号・根拠・相互参照・言い換えの検査。"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from conftest import PAGES, codes, make_case, node_eval, run_script

SCRIPT = "validate-briefing-docs"
# 最小の案件では出ない warn (要望・要件の札・データの 1 件と単位・画面ごとのボード)
NEW_WARNINGS = {"SCREEN-BOARD-MISSING", "DATA-MAP-MISSING", "DATA-ONE-MISSING", "DATA-UNIT-MISSING",
                "REQUEST-MISSING", "REQUEST-DEFERRED-NO-Q", "REQ-TAG-MISSING", "MATERIAL-UNUSED"}


def edit(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert old in text, f"{path.name} に {old!r} がありません"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def test_minimal_case_passes(case: Path) -> None:
    rc, out, err = run_script(SCRIPT, "--dir", str(case))
    assert rc == 0, err
    assert out["status"] == "ok"
    assert out["errors"] == []
    assert not codes(out["warnings"]) & NEW_WARNINGS, out["warnings"]
    assert {"requests": 0, "requests_deferred": 0, "screens_without_board": 0}.items() <= out["counts"].items()
    saved = json.loads((case / "_check" / "docs.json").read_text(encoding="utf-8"))
    assert saved["status"] == "ok"


def test_version_mismatch_between_docs(case: Path) -> None:
    edit(case / "仕様書.md", "版: v0.1", "版: v0.2")
    rc, out, _ = run_script(SCRIPT, "--dir", str(case))
    assert rc == 1
    assert "VERSION-MISMATCH" in codes(out["errors"])


def test_date_mismatch_between_docs(case: Path) -> None:
    edit(case / "仕様書.md", "更新日: 2026-10-01", "更新日: 2026-09-30")
    rc, out, _ = run_script(SCRIPT, "--dir", str(case))
    assert rc == 1
    (hit,) = [e for e in out["errors"] if e["code"] == "DATE-MISMATCH"]
    assert hit["file"] == "仕様書.md" and "2026-10-01" in hit["message"]


def test_changes_number_restarts_and_cells_are_filled(case: Path) -> None:
    edit(case / "要件定義.md", "版: v0.1", "版: v0.2")
    edit(case / "仕様書.md", "版: v0.1", "版: v0.2")
    (case / "変更点.md").write_text(
        "# 変更点: テスト\n\n## v0.2 (2026-10-01)\n\n"
        "| 番号 | 変更 | 場所 | きっかけ |\n| --- | --- | --- | --- |\n"
        "| C01 | 撮り直しを足した | 仕様書 S02 | 打ち合わせ |\n"
        "| C03 | 通知を外した |  | 打ち合わせ |\n",
        encoding="utf-8",
    )
    rc, out, _ = run_script(SCRIPT, "--dir", str(case))
    assert rc == 1
    assert {"CHANGES-NUMBER", "CHANGES-CELL-EMPTY"} <= codes(out["errors"])
    (number,) = [e for e in out["errors"] if e["code"] == "CHANGES-NUMBER"]
    assert number["line"] == 8 and "C02" in number["message"]

    edit(case / "変更点.md", "| C03 | 通知を外した |  |", "| C02 | 通知を外した | 仕様書 6 章 |")
    rc, out, _ = run_script(SCRIPT, "--dir", str(case))
    assert rc == 0, out["errors"]


def test_empty_evidence_is_error(case: Path) -> None:
    edit(case / "仕様書.md", "| 日付 | 日付 | ○ | 今日 | 記録の日 | 例 |", "| 日付 | 日付 | ○ | 今日 | 記録の日 |  |")
    rc, out, _ = run_script(SCRIPT, "--dir", str(case))
    assert rc == 1
    assert "EVIDENCE-EMPTY" in codes(out["errors"])


def test_evidence_must_point_to_known_hearing(case: Path) -> None:
    edit(case / "仕様書.md", "聞き取り:H01", "聞き取り:H99")
    rc, out, _ = run_script(SCRIPT, "--dir", str(case))
    assert rc == 1
    assert "EVIDENCE-REF-UNKNOWN" in codes(out["errors"])


def test_unknown_next_screen(case: Path) -> None:
    edit(case / "仕様書.md", "| 送る | 写真を送って一覧に入れる | S02 |", "| 送る | 写真を送って一覧に入れる | S09 |")
    rc, out, _ = run_script(SCRIPT, "--dir", str(case))
    assert rc == 1
    assert "NEXT-SCREEN-UNKNOWN" in codes(out["errors"])


def test_future_candidate_needs_preparation_and_timing(case: Path) -> None:
    edit(case / "仕様書.md", "  - 時期: 次の版\n", "  - 時期: いつか\n")
    rc, out, _ = run_script(SCRIPT, "--dir", str(case))
    assert rc == 0
    (hit,) = [w for w in out["warnings"] if w["code"] == "FUTURE-FIELD-MISSING"]
    assert "月ごとのまとめ" in hit["message"]
    assert "「時期: いつか」" in hit["message"] and "「備え:」" not in hit["message"]


def test_phone_page_needs_screens(tmp_path: Path) -> None:
    pages = [dict(p) for p in PAGES]
    pages[1]["screens"] = []
    base = make_case(tmp_path, pages=pages)
    rc, out, _ = run_script(SCRIPT, "--dir", str(base), "--stage", "pages")
    assert rc == 1
    assert "PAGE-SCREENS" in codes(out["errors"])


def test_jargon_needs_plain_words_or_definition(case: Path) -> None:
    req = case / "要件定義.md"
    edit(req, "紙の記録を写真で送るだけで、一覧に入るようにする。", "紙の記録を写真で送るだけで、API 経由で一覧に入るようにする。")
    rc, out, _ = run_script(SCRIPT, "--dir", str(case))
    assert rc == 1
    hits = [e for e in out["errors"] if e["code"] == "PLAIN-TERM"]
    assert hits and "API" in hits[0]["message"]

    # 用語の表で説明すれば通る
    edit(req, "| 権限 | 役割ごとの、できることとできないことの決まり |",
         "| 権限 | 役割ごとの、できることとできないことの決まり |\n| API | ほかのしくみとデータをやりとりする入り口 |")
    rc, out, _ = run_script(SCRIPT, "--dir", str(case))
    assert rc == 0, out["errors"]


def test_katakana_terms_match_whole_words_only() -> None:
    checks = [
        ["ログ", "ログを見る"], ["ログ", "ログインする"], ["ログ", "カタログを見る"],
        ["マスタ", "マスタを直す"], ["マスタ", "マスターを直す"],
        ["UI", "GUI の話"], ["UI", "ui を変える"],
    ]
    hits = node_eval(
        'import { termPattern } from "./validate-briefing-docs.mjs";\n'
        f"const checks = {json.dumps(checks, ensure_ascii=False)};\n"
        "console.log(JSON.stringify(checks.map(([term, text]) => termPattern(term).test(text))));"
    )
    assert hits == [True, False, False, True, True, False, True]


def test_briefing_shape_is_checked(tmp_path: Path) -> None:
    base = make_case(tmp_path)
    path = base / "briefing.json"
    briefing = json.loads(path.read_text(encoding="utf-8"))
    briefing["readers"] = []
    briefing["extra"] = 1
    path.write_text(json.dumps(briefing, ensure_ascii=False), encoding="utf-8")
    rc, out, _ = run_script(SCRIPT, "--dir", str(base), "--stage", "hearing")
    assert rc == 1
    shapes = [e["message"] for e in out["errors"] if e["code"] == "BRIEFING-SHAPE"]
    assert any("readers" in m for m in shapes) and any("extra" in m for m in shapes)


def test_data_policy_is_required(tmp_path: Path) -> None:
    base = make_case(tmp_path)
    path = base / "briefing.json"
    briefing = json.loads(path.read_text(encoding="utf-8"))
    for policy in (None, "public"):
        if policy is None:
            briefing.pop("data_policy")
        else:
            briefing["data_policy"] = policy
        path.write_text(json.dumps(briefing, ensure_ascii=False), encoding="utf-8")
        rc, out, _ = run_script(SCRIPT, "--dir", str(base), "--stage", "hearing")
        assert rc == 1, policy
        shapes = [e["message"] for e in out["errors"] if e["code"] == "BRIEFING-SHAPE"]
        assert any("data_policy" in m for m in shapes), policy


def test_screen_without_board_is_warned(tmp_path: Path) -> None:
    base = make_case(tmp_path, pages=PAGES[:2])
    _, out, _ = run_script(SCRIPT, "--dir", str(base), "--stage", "pages")
    (hit,) = [w for w in out["warnings"] if w["code"] == "SCREEN-BOARD-MISSING"]
    assert "S02" in hit["message"]
    assert out["counts"]["screens_without_board"] == 1


def test_many_material_sources_need_data_map(case: Path) -> None:
    rows = "".join(f"| 欄{i} | 文字 | ○ | 例の値 | 素材:記録票.pdf#欄{i} |\n" for i in range(1, 5))
    edit(case / "仕様書.md", "| 日付 | 日付 | ○ | 2026-10-01 | 例 |\n", "| 日付 | 日付 | ○ | 2026-10-01 | 素材:記録票.pdf |\n" + rows)
    rc, out, _ = run_script(SCRIPT, "--dir", str(case))
    assert rc == 0, out["errors"]
    (hit,) = [w for w in out["warnings"] if w["code"] == "DATA-MAP-MISSING"]
    assert "5 個" in hit["message"]


def test_data_needs_one_record_line(case: Path) -> None:
    edit(case / "仕様書.md", "1 件 = 記録票 1 枚\n\n", "")
    rc, out, _ = run_script(SCRIPT, "--dir", str(case))
    assert rc == 0, out["errors"]
    (hit,) = [w for w in out["warnings"] if w["code"] == "DATA-ONE-MISSING"]
    assert "D01 記録" in hit["message"]


def test_number_type_needs_unit(case: Path) -> None:
    spec = case / "仕様書.md"
    edit(spec, "| 相手先 | 文字 | ○ | サンプル商店 | 決めること:Q01 |\n",
         "| 相手先 | 文字 | ○ | サンプル商店 | 決めること:Q01 |\n| 枚数 | 数 | ○ | 3 | 例 |\n")
    _, out, _ = run_script(SCRIPT, "--dir", str(case))
    (hit,) = [w for w in out["warnings"] if w["code"] == "DATA-UNIT-MISSING"]
    assert "枚数" in hit["message"]

    # 単位をかっこで書けば通る
    edit(spec, "| 枚数 | 数 |", "| 枚数 | 数 (枚) |")
    _, out, _ = run_script(SCRIPT, "--dir", str(case))
    assert "DATA-UNIT-MISSING" not in codes(out["warnings"])


def test_request_stays_in_features_and_is_asked_when_deferred(case: Path) -> None:
    edit(case / "ヒアリング.md", "| H01 | 何を楽にしたいか | 打ち直しをなくしたい | 聞き取り |\n",
         "| H01 | 何を楽にしたいか | 打ち直しをなくしたい | 聞き取り |\n| H05 | ほしいもの | 月ごとにまとめたい | 要望 |\n")
    rc, out, _ = run_script(SCRIPT, "--dir", str(case))
    assert rc == 0, out["errors"]
    (hit,) = [w for w in out["warnings"] if w["code"] == "REQUEST-MISSING"]
    assert hit["file"] == "ヒアリング.md" and "H05" in hit["message"]

    # 6 章に残しても、あとで に回すなら 9 章で聞く
    req = case / "要件定義.md"
    edit(req, "| F03 | 月ごとにまとめる |", "| F03 | 月ごとにまとめる (要望:H05) |")
    _, out, _ = run_script(SCRIPT, "--dir", str(case))
    assert "REQUEST-MISSING" not in codes(out["warnings"])
    (hit,) = [w for w in out["warnings"] if w["code"] == "REQUEST-DEFERRED-NO-Q"]
    assert hit["file"] == "要件定義.md" and "F03" in hit["message"]

    edit(req, "| Q02 | 記録を何日分残すか | 30 日分 | 発注側の責任者 |\n",
         "| Q02 | 記録を何日分残すか | 30 日分 | 発注側の責任者 |\n| Q03 | 月ごとのまとめは次の版でよいか (要望:H05) | 次の版 | 発注側の責任者 |\n")
    rc, out, _ = run_script(SCRIPT, "--dir", str(case))
    assert rc == 0, out["errors"]
    assert not codes(out["warnings"]) & {"REQUEST-MISSING", "REQUEST-DEFERRED-NO-Q"}
    assert out["counts"]["requests"] == 1 and out["counts"]["requests_deferred"] == 1


def test_unknown_req_tag_is_error(case: Path) -> None:
    edit(case / "_src" / "02_phone-send.html", '<span class="req" data-req="F01">F01 写真を送る</span>',
         '<span class="req" data-req="F01">F01 写真を送る</span><span class="req" data-req="F09">F09 ためす</span>')
    rc, out, _ = run_script(SCRIPT, "--dir", str(case))
    assert rc == 1
    (hit,) = [e for e in out["errors"] if e["code"] == "REQ-TAG-UNKNOWN"]
    assert hit["file"] == "_src/02_phone-send.html" and "F09" in hit["message"]


def test_first_version_feature_needs_req_tag(case: Path) -> None:
    edit(case / "_src" / "03_pc-list.html", '<span class="req" data-req="F02">F02 一覧で直す</span>', "")
    rc, out, _ = run_script(SCRIPT, "--dir", str(case))
    assert rc == 0, out["errors"]
    (hit,) = [w for w in out["warnings"] if w["code"] == "REQ-TAG-MISSING"]
    assert hit["file"] == "要件定義.md" and "F02" in hit["message"] and "_src/03_pc-list.html" in hit["message"]


def test_board_lead_must_match_message(case: Path) -> None:
    """lead だけ直して message を直し忘れると、まとめの同じページに違う 2 文が並ぶ。"""
    edit(case / "_src" / "02_phone-send.html", '<div class="lead">撮って送るだけ</div>', '<div class="lead">撮って <b>送る</b>\n だけ</div>')
    rc, out, _ = run_script(SCRIPT, "--dir", str(case))
    assert rc == 0 and "BOARD-LEAD-MISMATCH" not in codes(out["warnings"]), "中のタグと空白の違いは同じ文"
    edit(case / "_src" / "02_phone-send.html", "撮って <b>送る</b>", "撮って <b>選ぶ</b>")
    rc, out, _ = run_script(SCRIPT, "--dir", str(case))
    (hit,) = [w for w in out["warnings"] if w["code"] == "BOARD-LEAD-MISMATCH"]
    assert rc == 0 and hit["file"] == "_src/02_phone-send.html" and "撮って送るだけ" in hit["message"]


def test_missing_folder_or_briefing_is_usage_error(tmp_path: Path) -> None:
    rc, out, _ = run_script(SCRIPT, "--dir", str(tmp_path / "なし"))
    assert rc == 2
    assert out["status"] == "usage-error"
    rc, _, _ = run_script(SCRIPT, "--dir", str(tmp_path))
    assert rc == 2


def test_hearing_stage_ignores_later_documents(tmp_path: Path) -> None:
    base = make_case(tmp_path)
    (base / "仕様書.md").write_text("書きかけ\n", encoding="utf-8")
    rc, out, err = run_script(SCRIPT, "--dir", str(base), "--stage", "hearing")
    assert rc == 0, err
    assert out["stage"] == "hearing"


def test_material_unused_is_reported_once(case: Path) -> None:
    """素材フォルダにあって、根拠にもボードにも出ていない素材を 1 つの warn で知らせる (出力フォルダ・隠しファイル・Excel は数えない)。"""
    materials = case.parent
    (materials / "古い様式.pdf").write_bytes(b"%PDF-1.4\n%%EOF\n")
    (materials / "写真").mkdir()
    (materials / "写真" / "画面.png").write_bytes(b"")
    (materials / "一覧.xlsx").write_bytes(b"")
    (materials / ".DS_Store").write_bytes(b"")
    (case / "_src" / "assets" / "切り出し.png").write_bytes(b"")
    edit(case / "_src" / "00_overview.html", "</main>", '<img data-source="写真/画面.png#上半分" alt="">\n</main>')

    _, out, _ = run_script(SCRIPT, "--dir", str(case))
    found = [w for w in out["warnings"] if w["code"] == "MATERIAL-UNUSED"]
    assert len(found) == 1 and "古い様式.pdf" in found[0]["message"], out["warnings"]
    assert out["counts"]["materials_unused"] == 1, "記録票.pdf は根拠に、写真/画面.png はボードに出ている"

    _, early, _ = run_script(SCRIPT, "--dir", str(case), "--stage", "spec")
    assert "MATERIAL-UNUSED" not in codes(early["warnings"]), "ボードが揃う all のときだけ見る"


def test_spec_details_cannot_be_filled_by_comments_or_empty_labels(case: Path) -> None:
    spec = case / '仕様書.md'
    text = spec.read_text(encoding='utf-8')
    text = text.replace('### 2.1 骨組み', '### 2.1 骨組み\n\n- 共通配置:\n<!-- - 画面区分: 管理者と利用者 -->')
    spec.write_text(text, encoding='utf-8')
    rc, out, _ = run_script(SCRIPT, '--dir', str(case), '--stage', 'spec')
    assert rc == 0  # Existing documents are compatible, but their gaps are visible.
    warnings = [w['message'] for w in out['warnings'] if w['code'] == 'SPEC-DETAIL-MISSING']
    assert any('共通配置' in w for w in warnings)
    assert any('画面区分' in w for w in warnings)
    assert any('処理境界' in w for w in warnings)
    assert any('安全対策' in w for w in warnings)
    assert any('稼働構成' in w for w in warnings)
    text = text.replace('- 共通配置:', '- 共通配置: PCは左メニュー、右本文。スマホは一列。', 1)
    text = text.replace('<!-- - 画面区分: 管理者と利用者 -->', '- 画面区分: 管理者は設定、利用者は入力。サーバーでも権限を確認する。')
    spec.write_text(text, encoding='utf-8')
    _, out, _ = run_script(SCRIPT, '--dir', str(case), '--stage', 'spec')
    warnings = [w['message'] for w in out['warnings'] if w['code'] == 'SPEC-DETAIL-MISSING']
    assert not any('2.1 骨組み' in w for w in warnings)


def complete_hearing(case: Path) -> None:
    catalog = node_eval('import { HEARING_QUESTIONS, HEARING_SECTIONS } from "./lib/hearing-catalog.mjs";\n'
                        'console.log(JSON.stringify({ questions: HEARING_QUESTIONS, sections: HEARING_SECTIONS }));')
    lines = ["# ヒアリング記録: 写真で記録", "更新日: 2026-10-01", ""]
    for section in catalog["sections"]:
        lines += [f'## {section["title"]}', '| 番号 | 質問 | 回答 | 出どころ |', '| --- | --- | --- | --- |']
        lines += [f'| {q["id"]} | {q["question"]} | 現場で確認した内容 | 聞き取り |'
                  for q in catalog["questions"] if q["section"] == section["id"]]
        lines.append("")
    lines += ['## 5. あとで相談すること', '']
    (case / 'ヒアリング.md').write_text('\n'.join(lines), encoding='utf-8')


@pytest.mark.parametrize('number', range(1, 37))
def test_each_fixed_hearing_question_is_required(case: Path, number: int) -> None:
    complete_hearing(case)
    hearing = case / 'ヒアリング.md'
    hid = f'H{number:02}'
    hearing.write_text(re.sub(rf'^\| {hid} \|.*\n', '', hearing.read_text(encoding='utf-8'), flags=re.M), encoding='utf-8')
    rc, out, _ = run_script(SCRIPT, '--dir', str(case), '--stage', 'hearing')
    assert rc == 0  # Legacy documents remain readable; omission is not a claim of completion.
    hits = [w for w in out['warnings'] if w['code'] == 'HEARING-REQUIRED-MISSING']
    assert len(hits) == 1 and hid in hits[0]['message']
    assert out['counts']['hearing_required_missing'] == 1


def test_hearing_catalog_accepts_extra_question_and_detects_wrong_section(case: Path) -> None:
    complete_hearing(case)
    hearing = case / 'ヒアリング.md'
    last = re.search(r'^\| H36 \|.*\n', hearing.read_text(encoding='utf-8'), flags=re.M)[0]
    edit(hearing, last, last + '| H37 | 追加で確かめること | 確認済み | 聞き取り |\n')
    rc, out, _ = run_script(SCRIPT, '--dir', str(case), '--stage', 'hearing')
    assert rc == 0 and out['warnings'] == []
    assert out['counts']['hearing_required_missing'] == 0
    assert out['counts']['hearing_items'] == 37
    text = hearing.read_text(encoding='utf-8')
    row = re.search(r'^\| H36 \|.*\n', text, flags=re.M)[0]
    text = text.replace(row, '').replace('| H01 |', row + '| H01 |')
    hearing.write_text(text, encoding='utf-8')
    _, out, _ = run_script(SCRIPT, '--dir', str(case), '--stage', 'hearing')
    assert out['counts']['hearing_wrong_section'] == 1
    assert 'HEARING-SECTION' in codes(out['warnings'])


def test_undecided_answer_must_reach_pending_list_and_question(case: Path) -> None:
    complete_hearing(case)
    hearing = case / 'ヒアリング.md'
    text = hearing.read_text(encoding='utf-8')
    text = re.sub(r'^(\| H17 \|.*?)\| 聞き取り \|$', r'\1| 未定 |', text, flags=re.M)
    hearing.write_text(text, encoding='utf-8')
    rc, out, _ = run_script(SCRIPT, '--dir', str(case), '--stage', 'requirements')
    assert rc == 0
    assert {'HEARING-PENDING-MISSING', 'HEARING-PENDING-NO-Q'} <= codes(out['warnings'])
    assert out['counts']['hearing_pending_unlisted'] == out['counts']['hearing_pending_without_question'] == 1
    edit(hearing, '## 5. あとで相談すること', '## 5. あとで相談すること\n- H17: 入り方を確かめる')
    edit(case / '要件定義.md', '入れる項目はこの 4 つでよいか', '入り方を確かめる (H17)')
    _, out, _ = run_script(SCRIPT, '--dir', str(case), '--stage', 'requirements')
    assert not {'HEARING-PENDING-MISSING', 'HEARING-PENDING-NO-Q'} & codes(out['warnings'])
    assert out['counts']['hearing_pending_unlisted'] == out['counts']['hearing_pending_without_question'] == 0
    edit(hearing, '| 未定 |', '| 聞き取り |')
    _, out, _ = run_script(SCRIPT, '--dir', str(case), '--stage', 'hearing')
    assert 'HEARING-PENDING-STALE' in codes(out['warnings'])


@pytest.mark.parametrize('resolution', ['empty', 'placeholder', 'decided'])
def test_pending_hearing_needs_actionable_open_question(case: Path, resolution: str) -> None:
    edit(case / '要件定義.md', '| Q01 | 入れる項目はこの 4 つでよいか | 日付・相手先・数・メモ | 現場の担当者 |',
         '| Q01 | H03の入り方 |  |  |' if resolution == 'empty' else
         '| Q01 | H03の入り方 | 未定 | <!-- 確認先 --> |' if resolution == 'placeholder' else
         '| Q01 | H03の入り方 | 会社のメールで入る | 決定 (v0.1) |')
    rc, out, _ = run_script(SCRIPT, '--dir', str(case), '--stage', 'requirements')
    assert rc == 0
    expected = 'HEARING-PENDING-DECIDED-Q' if resolution == 'decided' else 'QUESTION-CELL-EMPTY'
    assert expected in codes(out['warnings'])
    assert out['counts']['hearing_pending_without_question'] == 1
    assert out['counts']['question_rows_incomplete'] == (0 if resolution == 'decided' else 1)


@pytest.mark.parametrize('suffix', [' (Q99)', '。Q99で確かめる', ' (案: Q99)'])
def test_unknown_question_in_spec_text_is_error(case: Path, suffix: str) -> None:
    edit(case / '仕様書.md', '### 2.1 骨組み', '### 2.1 骨組み\n- 共通配置: 左にメニュー' + suffix)
    rc, out, _ = run_script(SCRIPT, '--dir', str(case), '--stage', 'spec')
    assert rc == 1
    assert 'QUESTION-REF-UNKNOWN' in codes(out['errors'])
    assert out['counts']['question_refs_unknown'] == 1


def test_question_refs_allow_real_question_but_ignore_examples_and_identifiers(case: Path) -> None:
    edit(case / '仕様書.md', '### 2.1 骨組み',
         '### 2.1 骨組み\n- 共通配置: 案はQ01で確認。製品ABCQ99・Q99ABC・https://example.com/Q99 は参照でない。\n'
         '<!-- Q99 -->\n```text\nQ99\n```\n`Q99`')
    rc, out, _ = run_script(SCRIPT, '--dir', str(case), '--stage', 'spec')
    assert rc == 0, out['errors']
    assert out['counts']['question_refs_unknown'] == 0


@pytest.mark.parametrize('mutation', ['empty', 'missing', 'duplicate', 'cell'])
def test_role_coverage(case: Path, mutation: str) -> None:
    spec = case / '仕様書.md'
    field = '| 現場の担当者 | 写真を送る | 一覧を直す | 自分が送った記録だけ |'
    office = '| 事務の担当者 | 一覧を直す | なし | すべての記録 |'
    if mutation == 'empty':
        edit(spec, field, '')
        edit(spec, office, '')
    elif mutation == 'missing':
        edit(spec, office, '')
    elif mutation == 'duplicate':
        edit(spec, office, office + '\n' + office)
    else:
        edit(spec, field, field.replace('自分が送った記録だけ', ''))
    rc, out, _ = run_script(SCRIPT, '--dir', str(case), '--stage', 'spec')
    assert rc == 0
    expected = {'empty': 'ROLE-TABLE-EMPTY', 'missing': 'ROLE-MISSING', 'duplicate': 'ROLE-DUP', 'cell': 'ROLE-CELL-EMPTY'}
    assert expected[mutation] in codes(out['warnings'])
    counter = {'empty': 'roles_missing', 'missing': 'roles_missing', 'duplicate': 'roles_duplicate', 'cell': 'role_rows_incomplete'}[mutation]
    assert out['counts'][counter] == (2 if mutation == 'empty' else 1)


def test_explicit_role_groups_cover_only_complete_member_names(case: Path) -> None:
    spec = case / '仕様書.md'
    edit(spec, '| 現場の担当者 | 写真を送る | 一覧を直す | 自分が送った記録だけ |\n'
               '| 事務の担当者 | 一覧を直す | なし | すべての記録 |',
         '| 使う人 (現場の担当者・事務の担当者) | 写真を送る・一覧を直す | なし | 担当する記録 |')
    rc, out, _ = run_script(SCRIPT, '--dir', str(case), '--stage', 'spec')
    assert rc == 0 and out['counts']['roles_missing'] == 0
    edit(spec, '使う人 (現場の担当者・事務の担当者)', '使う人 (別の現場の担当者・事務の担当者)')
    _, out, _ = run_script(SCRIPT, '--dir', str(case), '--stage', 'spec')
    assert out['counts']['roles_missing'] == 1


@pytest.mark.parametrize(('section', 'field'), [
    ('2.2 ヘッダー', '表示内容'), ('2.3 メニュー', '項目と順序'), ('2.4 フッター', '固定領域'),
    ('2.5 色の役割', '色と意味'), ('2.7 メッセージ', '結果と直し方'),
])
@pytest.mark.parametrize('value', ['', '未定', '<案件から記入>', '<!-- 仮の内容 -->'])
def test_each_previously_unchecked_detail_cannot_be_blank(case: Path, section: str, field: str, value: str) -> None:
    edit(case / '仕様書.md', f'### {section}', f'### {section}\n- {field}: {value}')
    rc, out, _ = run_script(SCRIPT, '--dir', str(case), '--stage', 'spec')
    assert rc == 0
    assert any(w['code'] == 'SPEC-DETAIL-MISSING' and f'「{field}」' in w['message'] for w in out['warnings'])
    assert out['counts']['spec_detail_missing'] > 0
    edit(case / '仕様書.md', f'- {field}: {value}', f'- {field}: 案として共通の表示を使う (Q01)')
    _, out, _ = run_script(SCRIPT, '--dir', str(case), '--stage', 'spec')
    assert not any(w['code'] == 'SPEC-DETAIL-MISSING' and f'「{field}」' in w['message'] for w in out['warnings'])
