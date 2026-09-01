"""run-x-visual-generate の4スクリプトが「守ったつもり」を実際に止めることを確かめる。

背景:
  図解とサムネイルの版面規範 (字数・ゾーン数・禁止語・比率) は、LLM が守ったと
  申告するだけでは担保されない。守れていない構造データのまま画像生成へ進むと、
  版面が崩れたうえに課金だけが発生する。本テストは 4 スクリプトが違反を実際に
  exit 1 で止めることを、違反を1つずつ注入して確かめる。

  検出力の確認を主眼に置く。全ケースが exit 0 を返すテストは「検査していない緑」と
  区別がつかないため、正常系1件に対して違反系を複数並べ、それぞれが落ちることを見る。

対象:
  build-visual-prompts.js   構造データの制約検証と meta 生成
  validate-visual-assets.js 生成 PNG の署名・比率・寸法・背景の不透明性の検証
  embed-visual-paths.js     投稿ファイルへの差し込み (冪等・誤爆回避)
  generate-images-codex.js  codex 呼び出しの組み立て (--dry-run のみ。課金しない)
"""
import copy
import hashlib
import json
import os
import shutil
import struct
import subprocess
import zlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "plugins" / "x-longpost-creator" / "scripts"
# 背景色の期待値は kind ごとに違う（図解は純白・サムネイルはオフホワイト）。
# テスト側でも visual-spec.json を唯一の出所にして、規範と二重管理しない。
SPEC_DATA = json.loads(
    (
        ROOT / "plugins" / "x-longpost-creator" / "skills" / "run-x-visual-generate"
        / "references" / "visual-spec.json"
    ).read_text(encoding="utf-8")
)
TEMPLATE = ROOT / "plugins" / "x-longpost-creator" / "assets" / "output-template.md"

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None, reason="node が PATH に無い"
)

KINDS = ("diagram", "x-thumb", "note-thumb")

# 全制約を満たす構造データ。各テストはこれを1点だけ壊して違反を注入する。
VALID_STRUCTURE = {
    "title": "スキルを作る前に決めるべきこと",
    "headline": "作る前に決めておくと手戻りがなくなる三つのこと",
    "primaryType": "T1",
    "nestedType": None,
    "zones": [
        {
            "id": "z1",
            "heading": "決めずに作り始める",
            "chain": [
                {"icon": "person silhouette typing", "label": "思いつき"},
                {"icon": "scattered documents", "label": "散らばる"},
            ],
            "conclusion": ["途中で方針が変わる", "作り直しが増える"],
        },
        {
            "id": "z2",
            "heading": "先に境界を決める",
            "chain": [
                {"icon": "single box with border", "label": "範囲"},
                {"icon": "checklist", "label": "条件"},
                {"icon": "lock", "label": "固定"},
            ],
            "conclusion": ["やらないことが決まる", "判断が速くなる"],
        },
        {
            "id": "z3",
            "heading": "機械に判定させる",
            "chain": [
                {"icon": "gear", "label": "検査"},
                {"icon": "check mark", "label": "合格"},
            ],
            "conclusion": ["数えられる物は機械へ", "人は中身だけ見る"],
        },
    ],
    "thumbnails": {
        "x": {
            "main": "作る前に決めておくべき三つのこと",
            "sub": "手戻りが消える",
            "icons": ["person silhouette", "gear"],
        },
        "note": {
            "main": "スキルを作る前に決める三つのこと",
            "sub": "スキル設計の前提",
            "icons": ["checklist"],
        },
    },
}


def _run(script: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["node", str(SCRIPTS / script), *args],
        capture_output=True,
        text=True,
    )


def _run_with_env(script: str, *args: str, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["node", str(SCRIPTS / script), *args],
        capture_output=True,
        text=True,
        env=env,
    )


def _write_structure(tmp_path: Path, structure: dict) -> Path:
    path = tmp_path / "visual-structure.json"
    path.write_text(json.dumps(structure, ensure_ascii=False), encoding="utf-8")
    return path


OFF_WHITE = (0xF8, 0xF3, 0xE6)
PURE_WHITE = (0xFF, 0xFF, 0xFF)


def _make_png(
    path: Path,
    width: int,
    height: int,
    color_type: int | None = None,
    background: tuple | None = None,
) -> None:
    """最小の実 PNG を書く。IHDR の寸法・color type と四隅の画素が検証対象になる。

    color_type / background を省略すると、ファイル名の kind に対応する正常な背景を書く
    （図解は純白のグレースケール、サムネイル2種はオフホワイトの RGB）。こうしておくと
    「背景以外を試すテスト」が背景の都合で落ちない。

    color_type=4 を渡すとアルファチャンネル付きになり、透過背景の事故を再現できる。
    background に色を渡すと、その色で塗った RGB 画像になり、背景色の事故を再現できる。
    """

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    if color_type is None and background is None:
        kind = path.stem
        is_thumb = SPEC_DATA["kinds"].get(kind, {}).get("palette") == "thumbnail"
        background = OFF_WHITE if is_thumb else None
        color_type = 2 if is_thumb else 0
    elif background is not None and color_type is None:
        color_type = 2

    if color_type == 2:
        pixel = bytes(background or PURE_WHITE)
    else:
        pixel = b"\xff" * {0: 1, 4: 2}[color_type]

    ihdr = struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0)
    raw = b"".join(b"\x00" + pixel * width for _ in range(height))
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


# --------------------------------------------------------------------------
# build-visual-prompts.js
# --------------------------------------------------------------------------


def test_valid_structure_standard_writes_two_thumbnail_meta(tmp_path):
    """標準系: 必須サムネイル2種のmetaだけを書き、図解は明示時だけ作る。"""
    structure = _write_structure(tmp_path, VALID_STRUCTURE)
    proc = _run(
        "build-visual-prompts.js",
        "--structure", str(structure),
        "--out-dir", str(tmp_path),
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert not (tmp_path / "diagram.meta.json").exists()
    for kind in ("x-thumb", "note-thumb"):
        meta = json.loads((tmp_path / f"{kind}.meta.json").read_text(encoding="utf-8"))
        assert meta["kind"] == kind
        # 生成していない出自を記録しない (generate-images-codex.js が実生成後に上書きする)
        assert meta["source"] is None
        assert meta["promptFile"] == f"{kind}.prompt.txt"


def _mutate(fn):
    structure = copy.deepcopy(VALID_STRUCTURE)
    fn(structure)
    return structure


def _set_zone_count(s):
    s["zones"] = s["zones"][:2]


def _set_long_label(s):
    s["zones"][0]["chain"][0]["label"] = "七文字を超える札"


def _set_forbidden_word(s):
    s["zones"][1]["conclusion"][0] = "僕がやらないことを決める"


def _set_emoji(s):
    s["zones"][2]["heading"] = "機械に判定させる\U0001f680"


def _set_title_emoji(s):
    s["title"] = "スキル設計\U0001f680"


def _set_title_forbidden_word(s):
    s["title"] = "私がスキルを設計する"


def _set_unapproved_symbol(s):
    s["metadata"] = {"badge": "未許可記号☆"}


def _set_bad_type(s):
    s["primaryType"] = "T9"


def _set_nested_same_as_primary(s):
    s["nestedType"] = s["primaryType"]


def _set_short_headline(s):
    s["headline"] = "短すぎる見出し"


def _set_long_conclusion(s):
    s["zones"][0]["conclusion"][1] = "二十字を明確に超えてしまう長さの結論文をここへ置く"


def _set_too_many_icons(s):
    s["thumbnails"]["x"]["icons"] = ["a", "b", "c", "d"]


@pytest.mark.parametrize(
    "mutator, expected_rule",
    [
        pytest.param(_set_zone_count, "VA-C02", id="zones-not-three"),
        pytest.param(_set_long_label, "VA-C04", id="label-over-6-chars"),
        pytest.param(_set_forbidden_word, "VA-C05", id="forbidden-word-boku"),
        pytest.param(_set_emoji, "VA-C06", id="emoji-in-heading"),
        pytest.param(_set_title_emoji, "VA-C06", id="emoji-in-title"),
        pytest.param(_set_title_forbidden_word, "VA-C05", id="forbidden-word-in-title"),
        pytest.param(_set_unapproved_symbol, "VA-C08", id="unapproved-symbol-in-extra-field"),
        pytest.param(_set_bad_type, "VA-C03", id="unknown-structure-type"),
        pytest.param(_set_nested_same_as_primary, "VA-C03", id="nested-equals-primary"),
        pytest.param(_set_short_headline, "VA-C04", id="headline-too-short"),
        pytest.param(_set_long_conclusion, "VA-C04", id="conclusion-over-20-chars"),
        pytest.param(_set_too_many_icons, "TP-C04", id="thumbnail-icons-over-3"),
    ],
)
def test_each_violation_is_rejected(tmp_path, mutator, expected_rule):
    """違反を1点だけ注入したら exit 1 で止まり、該当する rule ID が報告される。"""
    structure = _write_structure(tmp_path, _mutate(mutator))
    proc = _run(
        "build-visual-prompts.js",
        "--structure", str(structure),
        "--out-dir", str(tmp_path),
    )
    assert proc.returncode == 1, f"違反が素通りした: {proc.stdout}"
    payload = json.loads(proc.stdout)
    assert payload["ok"] is False
    rules = {v["rule"] for v in payload["violations"]}
    assert expected_rule in rules, f"expected {expected_rule}, got {rules}"
    # 違反時は meta を書かない (壊れた構造から生成へ進ませないため)
    assert not (tmp_path / "diagram.meta.json").exists()


def test_missing_arguments_exit_2(tmp_path):
    """引数不足は 1 (制約違反) ではなく 2 (呼び出し側の誤り) で区別する。"""
    proc = _run("build-visual-prompts.js", "--out-dir", str(tmp_path))
    assert proc.returncode == 2


# --------------------------------------------------------------------------
# validate-visual-assets.js
# --------------------------------------------------------------------------


def test_correct_sizes_pass(tmp_path):
    for kind in ("x-thumb", "note-thumb"):
        generation = SPEC_DATA["kinds"][kind]["generation"]
        _make_png(tmp_path / f"{kind}.png", generation["width"], generation["height"])
    proc = _run("validate-visual-assets.js", "--image-dir", str(tmp_path))
    assert proc.returncode == 0, proc.stdout


def test_standard_validation_is_strict_and_thumbnail_only(tmp_path):
    """標準経路は図解を要求せず、サムネイル2枚の実寸を厳密検証する。"""
    x_spec = SPEC_DATA["kinds"]["x-thumb"]["generation"]
    note_spec = SPEC_DATA["kinds"]["note-thumb"]["generation"]
    _make_png(tmp_path / "x-thumb.png", x_spec["width"], x_spec["height"])
    _make_png(tmp_path / "note-thumb.png", note_spec["width"], note_spec["height"])

    proc = _run("validate-visual-assets.js", "--image-dir", str(tmp_path))

    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["strict"] is True
    assert [result["kind"] for result in payload["results"]] == [
        "x-thumb", "note-thumb"
    ]

    _make_png(tmp_path / "note-thumb.png", 2560, 1340)
    proc = _run("validate-visual-assets.js", "--image-dir", str(tmp_path))
    assert proc.returncode == 1
    assert "size-mismatch" in json.loads(proc.stdout)["results"][1]["reasons"]


def test_text_saved_as_png_is_detected(tmp_path):
    """生成系が説明テキストを .png として書く事故を PNG 署名で止める。"""
    (tmp_path / "diagram.png").write_text(
        "I generated a description instead of an image.", encoding="utf-8"
    )
    proc = _run(
        "validate-visual-assets.js", "--image-dir", str(tmp_path), "--only", "diagram"
    )
    assert proc.returncode == 1
    assert json.loads(proc.stdout)["results"][0]["reason"] == "not-png"


def test_wrong_ratio_fails_but_wrong_size_only_warns(tmp_path):
    """比率違いは貼り先で文字が欠けるので FAIL、寸法違いは縮小で直るので WARN。"""
    _make_png(tmp_path / "diagram.png", 256, 144)  # 16:9 のまま縮小
    proc = _run(
        "validate-visual-assets.js", "--image-dir", str(tmp_path), "--only", "diagram"
    )
    assert proc.returncode == 0
    assert json.loads(proc.stdout)["results"][0]["warnings"]

    _make_png(tmp_path / "note-thumb.png", 256, 144)  # 1.91:1 ではない
    proc = _run(
        "validate-visual-assets.js", "--image-dir", str(tmp_path), "--only", "note-thumb"
    )
    assert proc.returncode == 1
    assert json.loads(proc.stdout)["results"][0]["reason"] == "ratio-mismatch"


def test_strict_promotes_size_mismatch_to_failure(tmp_path):
    _make_png(tmp_path / "diagram.png", 256, 144)
    proc = _run(
        "validate-visual-assets.js",
        "--image-dir", str(tmp_path),
        "--only", "diagram",
        "--strict",
    )
    assert proc.returncode == 1
    assert json.loads(proc.stdout)["results"][0]["reason"] == "size-mismatch"


def test_transparent_background_is_rejected(tmp_path):
    """VS-02 は背景を純白かつ不透明と定める。

    生成系は「白背景」を「背景を描かない」と解釈してアルファ付きで返すことがある。
    その画像は白い画面上では正常に見えるので目視をすり抜け、貼り先がダークテーマに
    なって初めて黒地に黒文字で全文が消える。比率と同格の FAIL にする。
    """
    _make_png(tmp_path / "diagram.png", 2560, 1440, color_type=4)
    proc = _run(
        "validate-visual-assets.js", "--image-dir", str(tmp_path), "--only", "diagram"
    )
    assert proc.returncode == 1, proc.stdout
    result = json.loads(proc.stdout)["results"][0]
    assert result["reason"] == "has-alpha"
    assert result["opaque"] is False
    # 寸法・比率は正しいので、透過だけが単独で失敗理由になっていること。
    assert result["reasons"] == ["has-alpha"]


def test_opaque_background_is_reported_as_such(tmp_path):
    """不透明な画像が誤って弾かれないこと（has-alpha 検査の偽陽性防止）。"""
    _make_png(tmp_path / "diagram.png", 2560, 1440)
    proc = _run(
        "validate-visual-assets.js", "--image-dir", str(tmp_path), "--only", "diagram"
    )
    assert proc.returncode == 0, proc.stdout
    assert json.loads(proc.stdout)["results"][0]["opaque"] is True


def test_validation_returns_absolute_artifact_path_for_host_preview(tmp_path):
    """検証後に同じファイルを画像ビューアで開けるよう、絶対パスを返す。"""
    image_dir = tmp_path / "relative-looking-images"
    image_dir.mkdir()
    _make_png(image_dir / "diagram.png", 2560, 1440)

    proc = _run(
        "validate-visual-assets.js",
        "--image-dir", str(image_dir),
        "--only", "diagram",
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    result = json.loads(proc.stdout)["results"][0]
    assert Path(result["path"]).is_absolute()
    assert Path(result["path"]) == (image_dir / "diagram.png").resolve()


def test_transparency_and_ratio_failures_are_reported_together(tmp_path):
    """理由を1つしか返さないと、片方だけ直して再生成しても緑にならない。"""
    _make_png(tmp_path / "note-thumb.png", 256, 144, color_type=4)  # 1.91:1 ではない
    proc = _run(
        "validate-visual-assets.js", "--image-dir", str(tmp_path), "--only", "note-thumb"
    )
    assert proc.returncode == 1
    assert json.loads(proc.stdout)["results"][0]["reasons"] == [
        "has-alpha",
        "ratio-mismatch",
    ]


# --------------------------------------------------------------------------
# embed-visual-paths.js
# --------------------------------------------------------------------------


def _prepare_post(tmp_path: Path) -> Path:
    post = tmp_path / "post.md"
    post.write_text(
        TEMPLATE.read_text(encoding="utf-8") + "\n# Next Action\n- [ ] 図解\n",
        encoding="utf-8",
    )
    for kind in KINDS:
        generation = SPEC_DATA["kinds"][kind]["generation"]
        _make_png(
            tmp_path / f"{kind}.png",
            generation["width"],
            generation["height"],
        )
    for kind in ("x-thumb", "note-thumb"):
        image = (tmp_path / f"{kind}.png").resolve()
        (tmp_path / f"{kind}.review.json").write_text(
            json.dumps({
                "version": 1,
                "kind": kind,
                "ok": True,
                "imagePath": str(image),
                "imageSha256": hashlib.sha256(image.read_bytes()).hexdigest(),
                "presentation": {"host": "codex", "tool": "view_image"},
                "validation": {
                    "strict": True,
                    "kind": kind,
                    "actual": (
                        f'{SPEC_DATA["kinds"][kind]["generation"]["width"]}x'
                        f'{SPEC_DATA["kinds"][kind]["generation"]["height"]}'
                    ),
                    "expected": (
                        f'{SPEC_DATA["kinds"][kind]["generation"]["width"]}x'
                        f'{SPEC_DATA["kinds"][kind]["generation"]["height"]}'
                    ),
                },
                "checks": {
                    "noPeople": "PASS",
                    "noInfoProduct": "PASS",
                    "textReadableCorrect": "PASS",
                    "gentleOffWhite": "PASS",
                    "impact": "PASS",
                },
            }),
            encoding="utf-8",
        )
    return post


def test_embed_is_idempotent_and_does_not_touch_checkbox_line(tmp_path):
    """2回流しても内容が変わらず、`- [ ] 図解` を書き換えない (行全体一致で探すため)。"""
    post = _prepare_post(tmp_path)

    proc = _run("embed-visual-paths.js", "--file", str(post), "--image-dir", str(tmp_path))
    assert proc.returncode == 0, proc.stdout
    assert {e["action"] for e in json.loads(proc.stdout)["embedded"]} == {"inserted"}
    after_first = post.read_text(encoding="utf-8")
    assert "![[diagram.png]]" in after_first
    assert "- [ ] 図解" in after_first  # チェックボックス行は無傷

    proc = _run("embed-visual-paths.js", "--file", str(post), "--image-dir", str(tmp_path))
    assert proc.returncode == 0
    assert {e["action"] for e in json.loads(proc.stdout)["embedded"]} == {"unchanged"}
    assert post.read_text(encoding="utf-8") == after_first


def test_embed_reports_missing_image(tmp_path):
    post = _prepare_post(tmp_path)
    (tmp_path / "x-thumb.png").unlink()
    before = post.read_bytes()
    proc = _run("embed-visual-paths.js", "--file", str(post), "--image-dir", str(tmp_path))
    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    problems = payload["problems"]
    assert [p["reason"] for p in problems] == ["image-missing"]
    assert payload["embedded"] == []
    assert post.read_bytes() == before


def test_embed_reports_missing_slot_without_changing_file_bytes(tmp_path):
    post = _prepare_post(tmp_path)
    post.write_text(
        post.read_text(encoding="utf-8").replace("Xサムネイル（5:2）\n", ""),
        encoding="utf-8",
    )
    before = post.read_bytes()

    proc = _run("embed-visual-paths.js", "--file", str(post), "--image-dir", str(tmp_path))

    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert [problem["reason"] for problem in payload["problems"]] == ["slot-missing"]
    assert payload["embedded"] == []
    assert post.read_bytes() == before


def test_markdown_mode_uses_absolute_path(tmp_path):
    post = _prepare_post(tmp_path)
    proc = _run(
        "embed-visual-paths.js",
        "--file", str(post),
        "--image-dir", str(tmp_path),
        "--markdown",
    )
    assert proc.returncode == 0
    assert f"![図解]({tmp_path / 'diagram.png'})" in post.read_text(encoding="utf-8")


def test_embed_publishes_unique_assets_to_obsidian_attachment_dir(tmp_path):
    """
    実投稿と同じく、本文は一意な basename の Obsidian 埋め込みを持ち、
    画像実体は明示した添付フォルダに置く。固定名 diagram.png は投稿を跨いで共有しない。
    """
    work_dir = tmp_path / "work"
    post_dir = tmp_path / "vault" / "05_Project" / "X"
    attachment_dir = tmp_path / "vault" / "02_Configs" / "Extra"
    work_dir.mkdir()
    post_dir.mkdir(parents=True)
    attachment_dir.mkdir(parents=True)

    post = post_dir / "X長文投稿-prompt作成 - 2026-08-31_確認経路.md"
    post.write_text(TEMPLATE.read_text(encoding="utf-8"), encoding="utf-8")
    for kind in KINDS:
        generation = SPEC_DATA["kinds"][kind]["generation"]
        _make_png(
            work_dir / f"{kind}.png",
            generation["width"],
            generation["height"],
        )
    for kind in ("x-thumb", "note-thumb"):
        review = _record_review(work_dir, kind)
        assert review.returncode == 0, review.stdout + review.stderr

    proc = _run(
        "embed-visual-paths.js",
        "--file", str(post),
        "--image-dir", str(work_dir),
        "--attachment-dir", str(attachment_dir),
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(proc.stdout)
    body = post.read_text(encoding="utf-8")
    for kind in KINDS:
        published = attachment_dir / f"{post.stem}-{kind}.png"
        assert published.is_file()
        assert f"![[{published.name}]]" in body
        artifact = next(item for item in payload["artifacts"] if item["kind"] == kind)
        assert Path(artifact["path"]) == published.resolve()

    # 再実行は同じ一意名を更新し、本文の参照を増殖させない。
    after_first = post.read_text(encoding="utf-8")
    proc = _run(
        "embed-visual-paths.js",
        "--file", str(post),
        "--image-dir", str(work_dir),
        "--attachment-dir", str(attachment_dir),
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert post.read_text(encoding="utf-8") == after_first
    assert {item["action"] for item in json.loads(proc.stdout)["embedded"]} == {"unchanged"}


REVIEW_FLAGS = (
    "--no-people", "PASS",
    "--no-info-product", "PASS",
    "--text-readable-correct", "PASS",
    "--gentle-off-white", "PASS",
    "--impact", "PASS",
)


def _record_review(image_dir: Path, kind: str) -> subprocess.CompletedProcess:
    return _run(
        "record-thumbnail-review.js",
        "--image-dir", str(image_dir),
        "--kind", kind,
        "--host", "codex",
        *REVIEW_FLAGS,
    )


def test_thumbnail_review_receipt_records_five_checks_and_image_hash(tmp_path):
    spec = SPEC_DATA["kinds"]["x-thumb"]["generation"]
    image = tmp_path / "x-thumb.png"
    _make_png(image, spec["width"], spec["height"])

    proc = _record_review(tmp_path, "x-thumb")

    assert proc.returncode == 0, proc.stdout + proc.stderr
    receipt_path = tmp_path / "x-thumb.review.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["ok"] is True
    assert receipt["imagePath"] == str(image.resolve())
    assert receipt["imageSha256"] == hashlib.sha256(image.read_bytes()).hexdigest()
    assert receipt["presentation"] == {"host": "codex", "tool": "view_image"}
    assert receipt["validation"] == {
        "strict": True,
        "kind": "x-thumb",
        "actual": f'{spec["width"]}x{spec["height"]}',
        "expected": f'{spec["width"]}x{spec["height"]}',
    }
    assert receipt["checks"] == {
        "noPeople": "PASS",
        "noInfoProduct": "PASS",
        "textReadableCorrect": "PASS",
        "gentleOffWhite": "PASS",
        "impact": "PASS",
    }


def test_thumbnail_review_rejects_wrong_dimensions_before_receipt(tmp_path):
    _make_png(tmp_path / "x-thumb.png", 16, 9)

    proc = _record_review(tmp_path, "x-thumb")

    assert proc.returncode == 1
    assert not (tmp_path / "x-thumb.review.json").exists()
    assert "strict-visual-validation-failed" in proc.stdout


def test_embed_only_thumbnails_requires_hash_matching_review_receipts(tmp_path):
    post = _prepare_post(tmp_path)
    for kind in ("x-thumb", "note-thumb"):
        (tmp_path / f"{kind}.review.json").unlink()

    missing = _run(
        "embed-visual-paths.js",
        "--file", str(post),
        "--image-dir", str(tmp_path),
        "--only", "x-thumb,note-thumb",
    )
    assert missing.returncode == 1
    assert {problem["reason"] for problem in json.loads(missing.stdout)["problems"]} == {
        "review-receipt-missing"
    }

    for kind in ("x-thumb", "note-thumb"):
        review = _record_review(tmp_path, kind)
        assert review.returncode == 0, review.stdout + review.stderr

    accepted = _run(
        "embed-visual-paths.js",
        "--file", str(post),
        "--image-dir", str(tmp_path),
        "--only", "x-thumb,note-thumb",
    )
    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
    assert [item["kind"] for item in json.loads(accepted.stdout)["artifacts"]] == [
        "x-thumb", "note-thumb"
    ]
    body = post.read_text(encoding="utf-8")
    assert "![[x-thumb.png]]" in body and "![[note-thumb.png]]" in body
    assert "![[diagram.png]]" not in body

    note = tmp_path / "note-thumb.png"
    note.write_bytes(note.read_bytes() + b"stale-after-review")
    stale = _run(
        "embed-visual-paths.js",
        "--file", str(post),
        "--image-dir", str(tmp_path),
        "--only", "x-thumb,note-thumb",
    )
    assert stale.returncode == 1
    assert "review-image-hash-mismatch" in {
        problem["reason"] for problem in json.loads(stale.stdout)["problems"]
    }


def test_embed_revalidates_dimensions_even_if_receipt_hash_is_current(tmp_path):
    post = _prepare_post(tmp_path)
    bad = tmp_path / "x-thumb.png"
    _make_png(bad, 16, 9)
    receipt_path = tmp_path / "x-thumb.review.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["imageSha256"] = hashlib.sha256(bad.read_bytes()).hexdigest()
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    proc = _run(
        "embed-visual-paths.js",
        "--file", str(post),
        "--image-dir", str(tmp_path),
        "--only", "x-thumb,note-thumb",
    )

    assert proc.returncode == 1
    assert "strict-visual-validation-failed" in {
        problem["reason"] for problem in json.loads(proc.stdout)["problems"]
    }


# --------------------------------------------------------------------------
# generate-images-codex.js (--dry-run のみ。実生成は課金されるので走らせない)
# --------------------------------------------------------------------------


def _prepare_generation_inputs(tmp_path: Path) -> None:
    """生成の前提を実際の順序どおりに整える (構造検証 -> meta 生成 -> プロンプト)。

    generate-images-codex.js は meta.json を寸法の出所として要求する。テストでも
    build-visual-prompts.js を先に通すことで、この順序依存自体を検証対象に含める。
    """
    structure = _write_structure(tmp_path, VALID_STRUCTURE)
    proc = _run(
        "build-visual-prompts.js",
        "--structure", str(structure),
        "--out-dir", str(tmp_path),
        "--only", ",".join(KINDS),
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    for kind in KINDS:
        (tmp_path / f"{kind}.prompt.txt").write_text("PROMPT", encoding="utf-8")


def test_generation_requires_meta_from_build_step(tmp_path):
    """meta.json 無しでは生成へ進めない (寸法の出所が無いまま課金させない)。"""
    for kind in KINDS:
        (tmp_path / f"{kind}.prompt.txt").write_text("PROMPT", encoding="utf-8")
    proc = _run("generate-images-codex.js", "--image-dir", str(tmp_path), "--dry-run")
    assert proc.returncode != 0
    assert "meta" in (proc.stdout + proc.stderr)


def test_dry_run_forbids_code_drawing_and_pins_size(tmp_path):
    """組み立てた指示が退化 (コード描画) を名指しで禁じ、種別ごとの寸法を含む。"""
    _prepare_generation_inputs(tmp_path)
    proc = _run("generate-images-codex.js", "--image-dir", str(tmp_path), "--dry-run")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    combined = proc.stdout + proc.stderr
    # 事故3 対策: 指示しないと PIL/matplotlib のコード描画へ退化する
    for banned in ("PIL", "matplotlib", "code-based drawing"):
        assert banned in combined
    for kind in ("x-thumb", "note-thumb"):
        generation = SPEC_DATA["kinds"][kind]["generation"]
        size = f'{generation["width"]}x{generation["height"]}'
        assert size in combined
    assert "2560x1440" not in combined
    # shell 文字列ではなく executable + argv の契約を表示する。
    assert '"executable"' in combined
    assert '"argv"' in combined
    assert "< /dev/null" not in combined
    # 画像は1枚も作られない (課金していない)
    assert not list(tmp_path.glob("*.png"))


def test_standard_generation_targets_both_thumbnails_and_makes_diagram_optional(tmp_path):
    _prepare_generation_inputs(tmp_path)

    proc = _run("generate-images-codex.js", "--image-dir", str(tmp_path), "--dry-run")

    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = _last_json_object(proc.stdout)
    assert [result["kind"] for result in payload["results"]] == [
        "x-thumb", "note-thumb"
    ]
    assert "diagram" not in [result["kind"] for result in payload["results"]]
    assert "1280x670" in proc.stdout


def test_dry_run_requires_prompt_file(tmp_path):
    """meta が揃っていてもプロンプト本文が無ければ止まる。

    meta 不足で落ちたのを取り違えないよう、meta は先に揃えたうえで
    プロンプトだけを取り除く。
    """
    _prepare_generation_inputs(tmp_path)
    (tmp_path / "diagram.prompt.txt").unlink()
    proc = _run(
        "generate-images-codex.js",
        "--image-dir", str(tmp_path),
        "--only", "diagram",
        "--dry-run",
    )
    assert proc.returncode != 0
    assert "prompt" in (proc.stdout + proc.stderr).lower()


def test_missing_codex_is_rejected_before_any_paid_attempt(tmp_path):
    _prepare_generation_inputs(tmp_path)
    env = os.environ.copy()
    env["XLP_CODEX_BIN"] = str(tmp_path / "missing-codex")

    proc = _run_with_env(
        "generate-images-codex.js",
        "--image-dir", str(tmp_path),
        "--only", "diagram,x-thumb",
        env=env,
    )

    assert proc.returncode == 2, proc.stdout + proc.stderr
    combined = proc.stdout + proc.stderr
    assert "codex-not-found" in combined
    assert "[RUN" not in combined
    assert not list(tmp_path.glob("*.png"))
    for kind in KINDS:
        meta = json.loads((tmp_path / f"{kind}.meta.json").read_text(encoding="utf-8"))
        assert meta["source"] is None


def test_dry_run_can_inspect_argv_without_shell_alias(tmp_path):
    _prepare_generation_inputs(tmp_path)
    configured = tmp_path / "codex executable with spaces"
    configured.write_text("#!/bin/sh\nexit 99\n", encoding="utf-8")
    configured.chmod(0o755)
    env = os.environ.copy()
    env["XLP_CODEX_BIN"] = str(configured)

    proc = _run_with_env(
        "generate-images-codex.js",
        "--image-dir", str(tmp_path),
        "--only", "diagram",
        "--dry-run",
        env=env,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert json.dumps(str(configured)) in proc.stdout
    assert '"argv":["exec"' in proc.stdout.replace(" ", "")
    assert not list(tmp_path.glob("*.png"))


def test_dry_run_rejects_explicit_missing_codex_before_generation(tmp_path):
    _prepare_generation_inputs(tmp_path)
    env = os.environ.copy()
    env["XLP_CODEX_BIN"] = str(tmp_path / "missing-codex")

    proc = _run_with_env(
        "generate-images-codex.js",
        "--image-dir", str(tmp_path),
        "--only", "diagram",
        "--dry-run",
        env=env,
    )

    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "codex-not-found" in (proc.stdout + proc.stderr)
    assert "[DRY" not in proc.stdout
    assert not list(tmp_path.glob("*.png"))


def _last_json_object(stdout: str):
    start = stdout.rfind("\n{")
    if start == -1:
        start = stdout.find("{") - 1
    return json.loads(stdout[start + 1:])


def test_fake_codex_session_image_is_recovered_to_requested_folder(tmp_path):
    """
    無課金の偽 Codex で、codex exec -> generated_images/<session-id> ->
    指定フォルダへの回収と、ホストが開く絶対パスの引き継ぎまでを通す。
    """
    image_dir = tmp_path / "requested image folder"
    codex_home = tmp_path / "isolated-codex-home"
    image_dir.mkdir()
    codex_home.mkdir()
    _prepare_generation_inputs(image_dir)

    generated = tmp_path / "fake-generated.png"
    _make_png(generated, 2560, 1440)
    fake_codex = tmp_path / "fake-codex"
    fake_codex.write_text(
        "#!/bin/sh\n"
        "session=deadbeef-0000-0000-0000-000000000001\n"
        'mkdir -p "$CODEX_HOME/generated_images/$session"\n'
        'cp -f "$XLP_FAKE_IMAGE" "$CODEX_HOME/generated_images/$session/generated.png"\n'
        'printf "session id: %s\\n" "$session"\n',
        encoding="utf-8",
    )
    fake_codex.chmod(0o755)

    env = os.environ.copy()
    env["XLP_CODEX_BIN"] = str(fake_codex)
    env["CODEX_HOME"] = str(codex_home)
    env["XLP_FAKE_IMAGE"] = str(generated)
    proc = _run_with_env(
        "generate-images-codex.js",
        "--image-dir", str(image_dir),
        "--only", "diagram",
        env=env,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    recovered = image_dir / "diagram.png"
    assert recovered.read_bytes() == generated.read_bytes()
    payload = _last_json_object(proc.stdout)
    result = payload["results"][0]
    assert Path(result["png"]) == recovered.resolve()
    assert result["presentation"] == {
        "absolutePath": str(recovered.resolve()),
        "claudeCode": {"tool": "Read", "path": str(recovered.resolve())},
        "codex": {"tool": "view_image", "path": str(recovered.resolve())},
    }
    meta = json.loads((image_dir / "diagram.meta.json").read_text(encoding="utf-8"))
    assert meta["source"] == "codex-image2"


def test_fake_codex_records_complete_stochastic_provenance(tmp_path):
    """seed非対応でも、同じ生成条件と結果を監査できるdigest一式を残す。"""
    image_dir = tmp_path / "images"
    codex_home = tmp_path / "codex-home"
    ref_dir = tmp_path / "refs"
    image_dir.mkdir()
    codex_home.mkdir()
    _prepare_generation_inputs(image_dir)

    note_spec = SPEC_DATA["kinds"]["note-thumb"]["generation"]
    generated = tmp_path / "fake-note.png"
    _make_png(generated, note_spec["width"], note_spec["height"])
    reference = ref_dir / "note-style.png"
    env = _reference_env(
        ref_dir,
        [{"file": reference.name, "kinds": ["note-thumb"]}],
    )
    _make_png(reference, 64, 32)

    fake_codex = tmp_path / "fake-codex"
    fake_codex.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "--version" ]; then printf "fake-codex 9.9.9\\n"; exit 0; fi\n'
        "session=deadbeef-0000-0000-0000-000000000009\n"
        'mkdir -p "$CODEX_HOME/generated_images/$session"\n'
        'cp -f "$XLP_FAKE_IMAGE" "$CODEX_HOME/generated_images/$session/generated.png"\n'
        'printf "session id: %s\\n" "$session"\n',
        encoding="utf-8",
    )
    fake_codex.chmod(0o755)
    env.update({
        "XLP_CODEX_BIN": str(fake_codex),
        "CODEX_HOME": str(codex_home),
        "XLP_FAKE_IMAGE": str(generated),
    })

    proc = _run_with_env(
        "generate-images-codex.js",
        "--image-dir", str(image_dir),
        "--only", "note-thumb",
        env=env,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    meta = json.loads((image_dir / "note-thumb.meta.json").read_text(encoding="utf-8"))
    provenance = meta["provenance"]
    assert provenance["mode"] == "stochastic"
    assert provenance["seed"] == {"supported": False, "value": None}
    assert provenance["sessionId"] == "deadbeef-0000-0000-0000-000000000009"
    assert provenance["executor"] == {
        "path": str(fake_codex.resolve()),
        "version": "fake-codex 9.9.9",
        "versionAvailable": True,
    }
    assert provenance["sha256"]["prompt"] == hashlib.sha256(
        (image_dir / "note-thumb.prompt.txt").read_bytes()
    ).hexdigest()
    assert provenance["sha256"]["structure"] == hashlib.sha256(
        (image_dir / "visual-structure.json").read_bytes()
    ).hexdigest()
    assert provenance["sha256"]["png"] == hashlib.sha256(
        (image_dir / "note-thumb.png").read_bytes()
    ).hexdigest()
    assert provenance["sha256"]["references"] == [{
        "file": reference.name,
        "sha256": hashlib.sha256(reference.read_bytes()).hexdigest(),
    }]


# ---------------------------------------------------------------------------
# 寸法の唯一の正本 visual-spec.json から、生成用 meta と画像検証の
# 両方が同じ値を読むことを CLI の観測結果で確かめる。
# ---------------------------------------------------------------------------

SPECS_DOC = (
    ROOT / "plugins" / "x-longpost-creator" / "skills" / "run-x-visual-generate"
    / "references" / "thumbnail-specs.md"
)
VISUAL_SPEC = (
    ROOT / "plugins" / "x-longpost-creator" / "skills" / "run-x-visual-generate"
    / "references" / "visual-spec.json"
)

# thumbnail-specs.md の表の行頭ラベルと kind の対応
_DOC_LABEL_TO_KIND = {
    "図解": "diagram",
    "X サムネイル": "x-thumb",
    "note サムネイル": "note-thumb",
}


def _parse_doc_table():
    """thumbnail-specs.md の寸法表を {kind: (ratio, deliver, generate)} で返す。"""
    rows = {}
    for line in SPECS_DOC.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 4:
            continue
        kind = _DOC_LABEL_TO_KIND.get(cells[0])
        if kind is None:
            continue
        # 「約 1.91:1」のような接頭辞を落として比率だけにする
        rows[kind] = (cells[1].replace("約", "").strip(), cells[2], cells[3])
    assert set(rows) == set(KINDS), f"{SPECS_DOC.name} の表から 3 種を読めない"
    return rows


def test_meta_and_asset_validation_use_dimensions_from_single_visual_spec(tmp_path):
    spec = json.loads(VISUAL_SPEC.read_text(encoding="utf-8"))
    assert set(spec["kinds"]) == set(KINDS)

    structure = _write_structure(tmp_path, VALID_STRUCTURE)
    proc = _run(
        "build-visual-prompts.js",
        "--structure", str(structure),
        "--out-dir", str(tmp_path),
        "--only", ",".join(KINDS),
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr

    for kind, expected in spec["kinds"].items():
        generation = expected["generation"]
        _make_png(tmp_path / f"{kind}.png", generation["width"], generation["height"])
        meta = json.loads((tmp_path / f"{kind}.meta.json").read_text(encoding="utf-8"))
        assert meta["generation"] == {
            "size": f'{generation["width"]}x{generation["height"]}',
            "ratio": expected["ratio"]["label"],
        }

    proc = _run("validate-visual-assets.js", "--image-dir", str(tmp_path), "--strict")
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_ratio_label_is_consistent_across_all_three_sources():
    """機械可読 spec と人間向け説明の比率表記が一致する。"""
    spec = json.loads(VISUAL_SPEC.read_text(encoding="utf-8"))
    doc = _parse_doc_table()
    for kind in KINDS:
        assert spec["kinds"][kind]["ratio"]["label"] == doc[kind][0]


def test_doc_table_matches_script_dimensions():
    """thumbnail-specs.md の説明が machine-readable spec と一致する。"""
    spec = json.loads(VISUAL_SPEC.read_text(encoding="utf-8"))
    doc = _parse_doc_table()
    for kind in KINDS:
        kind_spec = spec["kinds"][kind]
        generation = kind_spec["generation"]
        delivery = kind_spec["delivery"]
        assert doc[kind][1] == f'{delivery["width"]}x{delivery["height"]}'
        assert doc[kind][2] == f'{generation["width"]}x{generation["height"]}'


# --------------------------------------------------------------------------
# validate-visual-assets.js — 背景色 (lib/png-background.js)
#
# 背景色の規定は kind で違う。図解は純白、サムネイルはオフホワイトである。
# 規範に両方の指定が並存する以上、生成系はどちらへも転ぶ。サムネイルが純白で
# 返っても単体では正常に見えるため、目視では捕まらない事故になる。
# --------------------------------------------------------------------------


def _validate_one(tmp_path: Path, kind: str) -> dict:
    proc = _run("validate-visual-assets.js", "--image-dir", str(tmp_path), "--only", kind)
    return json.loads(proc.stdout)["results"][0], proc.returncode


def _make_filtered_png(path: Path, width: int, height: int, rgb: tuple, filter_type: int) -> None:
    """指定の PNG フィルタで走査線を符号化する。フィルタ解除を通らないと色が復元できない。"""

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    row = bytes(rgb) * width
    prev = bytes(len(row))
    raw = b""
    for _ in range(height):
        if filter_type == 0:
            raw += b"\x00" + row
        elif filter_type == 2:  # Up: 前行との差分
            raw += b"\x02" + bytes((row[i] - prev[i]) & 0xFF for i in range(len(row)))
        else:
            raise ValueError(filter_type)
        prev = row
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def test_pure_white_thumbnail_background_is_rejected(tmp_path):
    """サムネイルが純白で返ると貼り先の白い UI と地続きになり画像の輪郭が消える。"""
    _make_png(tmp_path / "x-thumb.png", 2560, 1024, background=PURE_WHITE)
    result, code = _validate_one(tmp_path, "x-thumb")
    assert code == 1
    assert result["reason"] == "background-too-white"
    assert result["backgroundHex"] == "#FFFFFF"
    assert result["expectedBackground"] == "off-white"


def test_off_white_diagram_background_is_rejected(tmp_path):
    """逆向きの漏れも止める。図解にサムネイルの palette が混入した場合。"""
    _make_png(tmp_path / "diagram.png", 2560, 1440, background=OFF_WHITE)
    result, code = _validate_one(tmp_path, "diagram")
    assert code == 1
    assert result["reason"] == "background-not-white"


def test_dark_thumbnail_background_is_rejected(tmp_path):
    """色面や写真が全面に敷かれた場合。文字が読めなくなるので FAIL にする。"""
    _make_png(tmp_path / "note-thumb.png", 2560, 1340, background=(0x2F, 0x48, 0x58))
    result, code = _validate_one(tmp_path, "note-thumb")
    assert code == 1
    assert result["reason"] == "background-too-dark"


def test_correct_background_passes_and_is_reported(tmp_path):
    _make_png(tmp_path / "x-thumb.png", 2560, 1024)
    result, code = _validate_one(tmp_path, "x-thumb")
    assert code == 0
    assert result["backgroundStatus"] == "pass"
    assert result["backgroundHex"] == "#F8F3E6"
    assert result["palette"] == "thumbnail"


def test_background_check_is_skipped_when_alpha_present(tmp_path):
    """透過している画像の四隅 RGB には意味がない。has-alpha だけを理由に挙げる。"""
    _make_png(tmp_path / "x-thumb.png", 2560, 1024, color_type=4)
    result, code = _validate_one(tmp_path, "x-thumb")
    assert code == 1
    assert result["reasons"] == ["has-alpha"]
    assert result["backgroundStatus"] == "unchecked"


def test_up_filtered_png_background_is_decoded(tmp_path):
    """PNG フィルタ解除の実装確認。差分符号化された走査線から元の色を復元できること。"""
    _make_filtered_png(tmp_path / "x-thumb.png", 2560, 1024, OFF_WHITE, filter_type=2)
    result, code = _validate_one(tmp_path, "x-thumb")
    assert code == 0, result
    assert result["backgroundHex"] == "#F8F3E6"


# --------------------------------------------------------------------------
# lint-thumbnail-prompt.js
#
# 画像生成は課金される。プロンプト文が規範を満たしているかを生成の「前」に
# 止める層であり、ここが緑にならない限り generate へ進まない契約になっている。
# --------------------------------------------------------------------------

VALID_STYLE = """STYLE: A calm, minimal Japanese thumbnail graphic. The entire canvas is filled with an
opaque warm off-white background (#F8F3E6), painted edge to edge as a solid rectangle.
All text is set in #1A1A1A with no outline or shadow. Geometric objects may use a restrained
paper-cut texture and shallow soft shadow, never dramatic 3D. Exactly two accent colors,
each with a fixed role: #C1C2A0 (muted sage) is used only
for structural elements such as connecting lines, rails and rings, never on text; #D87C45
(terracotta) is used only for a single small band carrying the supporting phrase, and the
text inside that band is white. No other color appears. Never use red."""

VALID_LAYOUT = {
    "x-thumb": """LAYOUT: 5:2 wide canvas. Split into a left text zone (65% width) and a right shape zone
(35% width). The right zone holds one to three flat geometric shapes, no arrows between
them. Keep at least 5% empty margin on all four sides. Do not draw a border frame around
the canvas.""",
    "note-thumb": """LAYOUT: 1.91:1 wide canvas. Centered vertical stack: a bold Japanese headline at the top,
one horizontal row of up to three flat geometric shapes in the middle connected by at most
one arrow chain. Keep at least 5% empty margin on all four sides. Do not draw a border
frame around the canvas.""",
}

VALID_CONTENT = {
    "x-thumb": (
        f'CONTENT:\nMain line (very large bold): "{VALID_STRUCTURE["thumbnails"]["x"]["main"]}"\n'
        f'Sub line: "{VALID_STRUCTURE["thumbnails"]["x"]["sub"]}"\n'
        "Shapes: two overlapping speech bubbles"
    ),
    "note-thumb": (
        f'CONTENT:\nMain line (very large bold): "{VALID_STRUCTURE["thumbnails"]["note"]["main"]}"\n'
        f'Sub line: "{VALID_STRUCTURE["thumbnails"]["note"]["sub"]}"\n'
        "Shapes: a check mark inside a circle"
    ),
}

VALID_TYPOGRAPHY = """TYPOGRAPHY: All text is Japanese, rendered in a heavy sans-serif gothic typeface in #1A1A1A.
Render every quoted Japanese string exactly as written, crisp and undistorted.
Do not add any text that is not quoted above. Do not decorate the letterforms."""

VALID_NEGATIVE = """NEGATIVE: no emoji, no human figures, no human silhouettes, no faces, no hands.
The background must be an opaque, fully painted off-white rectangle covering the entire
canvas; do NOT output a transparent background and do NOT include an alpha channel.
No outlined text, no gradient text, no drop shadow, no 3d text, no italic emphasis.
No neon, no highly saturated primary colors, no glowing elements, no dark backgrounds.
No starburst, no explosion marks, no speed lines, no lightning bolt, no crown, no medal.
No huge numbers promising results, no circled numbers, no price figures.
No diagonal band splitting the canvas, no decorative rule, no cluttered composition,
no more than three arrows. No photographic elements, no photorealistic rendering."""


def _write_thumb_prompts(tmp_path: Path, **override) -> Path:
    """規範どおりの2本を書き、override で片方のブロックだけ差し替える。"""
    for kind in ("x-thumb", "note-thumb"):
        blocks = [
            override.get("style", VALID_STYLE),
            override.get("layout", VALID_LAYOUT[kind]),
            override.get("content", VALID_CONTENT[kind]),
            VALID_TYPOGRAPHY,
            override.get("negative", VALID_NEGATIVE),
        ]
        (tmp_path / f"{kind}.prompt.txt").write_text("\n\n".join(blocks) + "\n", encoding="utf-8")
    return tmp_path


def _lint(tmp_path: Path, *extra: str) -> tuple:
    structure = tmp_path / "visual-structure.json"
    if not structure.exists():
        structure = _write_structure(tmp_path, VALID_STRUCTURE)
    proc = _run(
        "lint-thumbnail-prompt.js",
        "--image-dir", str(tmp_path),
        "--structure", str(structure),
        *extra,
    )
    return json.loads(proc.stdout), proc.returncode


def test_canonical_thumbnail_prompts_pass(tmp_path):
    """規範の §6 に載っている文言そのままで緑になること。

    これが赤なら規範とスクリプトが食い違っており、利用者は仕様どおり書いても
    先へ進めない。仕様と検査器の同期を守る番人にあたるケースである。
    """
    _write_thumb_prompts(tmp_path)
    out, code = _lint(tmp_path)
    assert code == 0, out
    assert out["violationCount"] == 0


def _lint_with_structure(tmp_path: Path, *extra: str) -> tuple:
    structure = _write_structure(tmp_path, VALID_STRUCTURE)
    proc = _run(
        "lint-thumbnail-prompt.js",
        "--image-dir", str(tmp_path),
        "--structure", str(structure),
        *extra,
    )
    return json.loads(proc.stdout), proc.returncode


def _write_structure_matching_thumb_prompts(tmp_path: Path) -> None:
    contents = {
        "x-thumb": (
            f'CONTENT:\nMain line (very large bold): "{VALID_STRUCTURE["thumbnails"]["x"]["main"]}"\n'
            f'Sub line: "{VALID_STRUCTURE["thumbnails"]["x"]["sub"]}"\n'
            "Shapes: two overlapping speech bubbles"
        ),
        "note-thumb": (
            f'CONTENT:\nMain line (very large bold): "{VALID_STRUCTURE["thumbnails"]["note"]["main"]}"\n'
            f'Sub line: "{VALID_STRUCTURE["thumbnails"]["note"]["sub"]}"\n'
            "Shapes: a check mark inside a circle"
        ),
    }
    for kind in ("x-thumb", "note-thumb"):
        (tmp_path / f"{kind}.prompt.txt").write_text(
            "\n\n".join((
                VALID_STYLE,
                VALID_LAYOUT[kind],
                contents[kind],
                VALID_TYPOGRAPHY,
                VALID_NEGATIVE,
            )) + "\n",
            encoding="utf-8",
        )


def test_lint_requires_structure_and_compares_main_and_sub_exactly(tmp_path):
    _write_structure_matching_thumb_prompts(tmp_path)

    missing = _run("lint-thumbnail-prompt.js", "--image-dir", str(tmp_path))
    assert missing.returncode == 2
    assert "--structure" in missing.stderr

    out, code = _lint_with_structure(tmp_path)
    assert code == 0, out

    prompt = tmp_path / "note-thumb.prompt.txt"
    prompt.write_text(
        prompt.read_text(encoding="utf-8").replace(
            VALID_STRUCTURE["thumbnails"]["note"]["main"],
            "本文には存在しない別の主文です",
        ),
        encoding="utf-8",
    )
    out, code = _lint_with_structure(tmp_path)
    assert code == 1
    assert "TL-11" in {item["rule"] for item in out["violations"]}


@pytest.mark.parametrize("block,rule", [("style", "TL-12"), ("typography", "TL-12"), ("negative", "TL-12")])
def test_lint_requires_shared_blocks_to_be_byte_identical_for_both_thumbnails(
    tmp_path, block, rule
):
    _write_structure_matching_thumb_prompts(tmp_path)
    prompt = tmp_path / "note-thumb.prompt.txt"
    text = prompt.read_text(encoding="utf-8")
    marker = {
        "style": "STYLE:",
        "typography": "TYPOGRAPHY:",
        "negative": "NEGATIVE:",
    }[block]
    prompt.write_text(text.replace(marker, marker + " intentionally different", 1), encoding="utf-8")

    out, code = _lint_with_structure(tmp_path)

    assert code == 1
    assert rule in {item["rule"] for item in out["violations"]}


def test_thumbnail_main_text_accepts_six_characters_and_rejects_five(tmp_path):
    six = copy.deepcopy(VALID_STRUCTURE)
    six["thumbnails"]["x"]["main"] = "続ける工夫を"
    structure = _write_structure(tmp_path, six)
    proc = _run(
        "build-visual-prompts.js",
        "--structure", str(structure),
        "--out-dir", str(tmp_path),
        "--only", "x-thumb",
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr

    five = copy.deepcopy(six)
    five["thumbnails"]["x"]["main"] = "続ける工夫"
    structure = _write_structure(tmp_path, five)
    proc = _run(
        "build-visual-prompts.js",
        "--structure", str(structure),
        "--out-dir", str(tmp_path),
        "--only", "x-thumb",
    )
    assert proc.returncode == 1
    assert "VA-C04" in proc.stdout


def test_tl02_covers_every_palette_color_including_newly_added_ones(tmp_path):
    """palette に色が増えたとき、TL-02 の検査対象が自動で追随すること。

    検査するロールをスクリプト側へ並べていると、規範に色が増えても検査だけが
    取り残され、「規範にはあるがプロンプトには書かれていない色」が課金前の
    関門を素通りする。palette の全 hex について、その1色だけを STYLE から
    落としたら必ず TL-02 が挙がることを確かめる。
    """
    palette = SPEC_DATA["palettes"]["thumbnail"]
    hexes = [v for v in palette.values() if isinstance(v, str) and v.startswith("#")]
    assert len(hexes) >= 4, "背景・文字・アクセント2色を想定している"

    for hex_value in hexes:
        _write_thumb_prompts(
            tmp_path,
            style=VALID_STYLE.replace(hex_value, "an unspecified color"),
        )
        out, code = _lint(tmp_path)
        assert code == 1, f"{hex_value} を消しても緑になった: {out}"
        rules = {v["rule"] for v in out["violations"]}
        assert "TL-02" in rules, f"{hex_value}: {out}"


def _leak_diagram_style(_):
    return {"style": VALID_STYLE.replace("opaque warm off-white background (#F8F3E6)", "pure white background")}


def _drop_human_ban(_):
    return {"negative": VALID_NEGATIVE.replace("no human figures, no human silhouettes, no faces, no hands", "no clutter")}


def _drop_symbol_group(_):
    return {"negative": VALID_NEGATIVE.replace("No starburst, no explosion marks, no speed lines, no lightning bolt, no crown, no medal.", "")}


def _drop_alpha_ban(_):
    return {"negative": VALID_NEGATIVE.replace("do NOT include an alpha channel", "keep it clean")}


def _drop_margin(kind):
    return {"layout": VALID_LAYOUT[kind].replace("Keep at least 5% empty margin on all four sides. ", "")}


def _wrong_ratio(kind):
    return {"layout": VALID_LAYOUT[kind].replace("5:2 wide canvas", "4:3 wide canvas").replace("1.91:1 wide canvas", "4:3 wide canvas")}


def _too_many_quotes(kind):
    return {"content": VALID_CONTENT[kind] + '\nExtra: "余計な一本" and "さらに一本"'}


def _over_long_main(kind):
    main = VALID_STRUCTURE["thumbnails"]["x" if kind == "x-thumb" else "note"]["main"]
    return {"content": VALID_CONTENT[kind].replace(
        f'"{main}"', '"質問を足すよりも捨てていくほうがずっと早いという話"'
    )}


def _forbidden_word(kind):
    return {"content": VALID_CONTENT[kind].replace("Main line", "Main line for 僕")}


@pytest.mark.parametrize(
    "mutator, expected_rule",
    [
        pytest.param(_leak_diagram_style, "TL-03", id="diagram-palette-leak"),
        pytest.param(_drop_human_ban, "TL-04", id="missing-human-ban"),
        pytest.param(_drop_symbol_group, "TL-05", id="missing-symbol-group"),
        pytest.param(_drop_alpha_ban, "TL-06", id="missing-alpha-ban"),
        pytest.param(_drop_margin, "TL-07", id="missing-margin"),
        pytest.param(_wrong_ratio, "TL-08", id="wrong-canvas-ratio"),
        pytest.param(_too_many_quotes, "TL-09", id="too-many-quoted-lines"),
        pytest.param(_over_long_main, "TL-09", id="main-line-too-long"),
        pytest.param(_forbidden_word, "TL-10", id="forbidden-word"),
    ],
)
def test_each_prompt_violation_is_rejected(tmp_path, mutator, expected_rule):
    for kind in ("x-thumb", "note-thumb"):
        override = mutator(kind)
        blocks = [
            override.get("style", VALID_STYLE),
            override.get("layout", VALID_LAYOUT[kind]),
            override.get("content", VALID_CONTENT[kind]),
            VALID_TYPOGRAPHY,
            override.get("negative", VALID_NEGATIVE),
        ]
        (tmp_path / f"{kind}.prompt.txt").write_text("\n\n".join(blocks) + "\n", encoding="utf-8")
    out, code = _lint(tmp_path)
    assert code == 1, out
    assert expected_rule in {v["rule"] for v in out["violations"]}, out


def test_zone_width_percentages_do_not_mask_missing_margin(tmp_path):
    """"65% width" の部分一致で "5%" が当たり、余白指示の欠落を見逃した回帰。"""
    _write_thumb_prompts(tmp_path, layout=(
        "LAYOUT: 5:2 wide canvas. Split into a left text zone (65% width) and a right shape "
        "zone (35% width). Do not draw a border frame around the canvas."
    ))
    out, code = _lint(tmp_path, "--only", "x-thumb")
    assert code == 1
    details = [v["detail"] for v in out["violations"] if v["rule"] == "TL-07"]
    assert any("余白" in d for d in details), out


def test_missing_block_is_rejected(tmp_path):
    _write_thumb_prompts(tmp_path)
    text = (tmp_path / "x-thumb.prompt.txt").read_text(encoding="utf-8")
    (tmp_path / "x-thumb.prompt.txt").write_text(text.split("TYPOGRAPHY:")[0], encoding="utf-8")
    out, code = _lint(tmp_path, "--only", "x-thumb")
    assert code == 1
    assert "TL-01" in {v["rule"] for v in out["violations"]}


def test_missing_prompt_file_is_rejected(tmp_path):
    out, code = _lint(tmp_path, "--only", "x-thumb")
    assert code == 1
    assert out["violationCount"] == 1


def test_lint_rejects_non_thumbnail_kind(tmp_path):
    """図解は別系統の規範なので、この検査器の対象にしない。"""
    structure = _write_structure(tmp_path, VALID_STRUCTURE)
    proc = _run(
        "lint-thumbnail-prompt.js", "--image-dir", str(tmp_path),
        "--structure", str(structure), "--only", "diagram"
    )
    assert proc.returncode == 2
    assert "サムネイル種別ではありません" in proc.stderr


def test_lint_missing_arguments_exit_2(tmp_path):
    proc = _run("lint-thumbnail-prompt.js")
    assert proc.returncode == 2


# ---------------------------------------------------------------------------
# 画風の見本画像 (references/reference-images/) と kind ごとの起動指示文
# ---------------------------------------------------------------------------


def _reference_env(ref_dir: Path, images: list[dict]) -> dict:
    """見本の置き場を差し替えた環境を作る。

    既定の置き場は plugin 同梱ディレクトリなので、テストがそこへ実体を置くと
    リポジトリを汚す。XLP_REFERENCE_IMAGE_DIR で tmp へ逃がす。
    """
    ref_dir.mkdir(parents=True, exist_ok=True)
    (ref_dir / "manifest.json").write_text(
        json.dumps({"images": images}, ensure_ascii=False), encoding="utf-8"
    )
    env = dict(os.environ)
    env["XLP_REFERENCE_IMAGE_DIR"] = str(ref_dir)
    return env


def test_thumbnail_instruction_does_not_force_diagram_palette(tmp_path):
    """起動指示文が kind ごとに分岐する (共通の固定文が規範を上書きしない)。

    以前は kind によらず "pure white background" と "black-and-white" を強制して
    おり、プロンプト側がオフホワイトを正しく指定してもこの指示文が上書きしていた。
    """
    _prepare_generation_inputs(tmp_path)
    thumb = _run(
        "generate-images-codex.js",
        "--image-dir", str(tmp_path), "--only", "x-thumb", "--dry-run",
    )
    assert thumb.returncode == 0, thumb.stdout + thumb.stderr
    thumb_out = thumb.stdout
    palette = SPEC_DATA["palettes"]["thumbnail"]
    assert palette["background"] in thumb_out
    # アクセントは2色あり、役割が違う。片方だけを書くと生成系が
    # もう片方を勝手に捨てるので、両方が指示文に載ることを要求する (TS-05)。
    assert palette["accent"] in thumb_out
    assert palette["label"] in thumb_out
    assert "black-and-white" not in thumb_out
    assert "human figure" in thumb_out

    diagram = _run(
        "generate-images-codex.js",
        "--image-dir", str(tmp_path), "--only", "diagram", "--dry-run",
    )
    assert diagram.returncode == 0, diagram.stdout + diagram.stderr
    assert SPEC_DATA["palettes"]["diagram"]["background"] in diagram.stdout
    assert "black-and-white" in diagram.stdout
    # 図解側にサムネイルの配色が漏れていない
    assert palette["accent"] not in diagram.stdout


def test_reference_images_are_attached_and_copying_is_forbidden(tmp_path):
    """実体がある見本は -i で添付され、複製の禁止が指示文に載る。"""
    _prepare_generation_inputs(tmp_path)
    ref_dir = tmp_path / "refs"
    env = _reference_env(ref_dir, [{"file": "sheet.png", "kinds": ["diagram"]}])
    _make_png(ref_dir / "sheet.png", 64, 64)

    proc = _run_with_env(
        "generate-images-codex.js",
        "--image-dir", str(tmp_path), "--only", "diagram", "--dry-run",
        env=env,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    argv = json.loads(proc.stdout.splitlines()[1])["argv"]
    assert argv[:2] == ["exec", "-i"]
    assert argv[2] == str(ref_dir / "sheet.png")
    # 見本は粒度の参照であって複製の対象ではない
    joined = " ".join(argv)
    assert "Do NOT copy their composition" in joined
    assert "reference image(s) are attached" in joined


def test_missing_reference_is_warned_by_default_and_fails_when_required(tmp_path):
    """宣言だけあって実体が無い見本は、既定では WARN、要求時は FAIL。

    見本なしでも生成は動く (正本は文章の canon) が、宣言との差は必ず記録へ残す。
    """
    _prepare_generation_inputs(tmp_path)
    env = _reference_env(tmp_path / "refs", [{"file": "absent.png", "kinds": ["diagram"]}])

    warned = _run_with_env(
        "generate-images-codex.js",
        "--image-dir", str(tmp_path), "--only", "diagram", "--dry-run",
        env=env,
    )
    assert warned.returncode == 0, warned.stdout + warned.stderr
    assert "absent.png" in warned.stderr
    assert "WARN" in warned.stderr

    required = _run_with_env(
        "generate-images-codex.js",
        "--image-dir", str(tmp_path), "--only", "diagram", "--dry-run",
        "--require-reference-images",
        env=env,
    )
    assert required.returncode == 1
    assert "reference-images-missing" in required.stdout


def test_reference_manifest_rejects_unknown_kind_and_path_escape(tmp_path):
    """宣言の綴り違いとディレクトリ脱出を止める。

    kind の綴りが違うと見本が黙って1枚も渡らない状態が続き、file の相対脱出は
    任意のファイルを生成系へ送信しうる。
    """
    _prepare_generation_inputs(tmp_path)

    bad_kind = _run_with_env(
        "generate-images-codex.js",
        "--image-dir", str(tmp_path), "--only", "diagram", "--dry-run",
        env=_reference_env(tmp_path / "r1", [{"file": "a.png", "kinds": ["diagrams"]}]),
    )
    assert bad_kind.returncode == 1
    assert "reference-manifest-invalid" in bad_kind.stdout

    escape = _run_with_env(
        "generate-images-codex.js",
        "--image-dir", str(tmp_path), "--only", "diagram", "--dry-run",
        env=_reference_env(tmp_path / "r2", [{"file": "../secret.png", "kinds": ["diagram"]}]),
    )
    assert escape.returncode == 1
    assert "reference-manifest-invalid" in escape.stdout


def test_shipped_reference_manifest_declares_only_known_kinds():
    """同梱 manifest の kind 名が visual-spec.json と一致する (実体の有無は問わない)。"""
    manifest = json.loads(
        (
            ROOT / "plugins" / "x-longpost-creator" / "assets" / "reference-images" / "manifest.json"
        ).read_text(encoding="utf-8")
    )
    valid = set(SPEC_DATA["kinds"])
    for entry in manifest["images"]:
        assert set(entry["kinds"]) <= valid, entry
        assert "/" not in entry["file"] and ".." not in entry["file"], entry
        assert entry["role"], entry
