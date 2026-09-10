"""C21 srg-image-bridge.py の受入テスト共通ヘルパ (P04-C21-01)。

方針:
- 契約は `plugin-plans/guide-doc-generator/briefs/script-brief-C21.json` の
  argv / stdout / stderr / exit_codes / write_scope / single_writer / algorithm /
  acceptance_checks / failure_modes / network と、`briefs/RESOLUTION-P03.md` Y-01 から起こす。
- **委譲先を一切本物で動かさない。** node も codex も PATH 上の fake に差し替える
  (`make_fake_bin`)。fake node は build-image-prompts.js / generate-images-codex.js の
  CLI 形 (`<slide-dir> [--plan] [--genome] [--dry-run] [--source] [--batch]`) だけを模し、
  ファイルを置いて exit 0 を返す。ネットワークも codex exec も発生しない。
- **SRG 解決を repo の実体から隔離する。** この repo には
  `plugins/slide-report-generator` が実在するので、skip 系のテストで
  `HB_ROOT` を tmp の偽 plugin root に向けないと、解決段 (c) が実物を拾って
  「SRG 不在」が再現できない。`clean_env` は既定でこの隔離を行う。
- 実装が未存在でも import 例外にしない。`require_script()` が
  「実装が無い」という診断可能な失敗 (failure) として赤を出す。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

# tests/srg-image-bridge.py/ -> tests -> guide-doc-generator -> plugins -> repo root
TESTS_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = TESTS_DIR.parents[1]
PLUGINS_DIR = TESTS_DIR.parents[2]
REPO_ROOT = TESTS_DIR.parents[3]

SCRIPT_NAME = "srg-image-bridge.py"
SCRIPT = PLUGIN_ROOT / "scripts" / SCRIPT_NAME
SCRIPTS_DIR = PLUGIN_ROOT / "scripts"

PLAN_DIR = REPO_ROOT / "plugin-plans" / "guide-doc-generator"
BRIEF_PATH = PLAN_DIR / "briefs" / "script-brief-C21.json"
INVENTORY_PATH = PLAN_DIR / "component-inventory.json"

# 委譲先 (実物)。存在検査と cross-component の照合にだけ使い、実行はしない。
REAL_SRG_ROOT = PLUGINS_DIR / "slide-report-generator"
SRG_VENDOR_SCRIPTS = ("vendor/scripts/build-image-prompts.js", "vendor/scripts/generate-images-codex.js")
SRG_GENOME_RELPATH = "vendor/assets/style-genome-kanagawa-comic-diagram.json"

FRONTMATTER_LINTER = PLUGINS_DIR / "skill-governance-lint" / "scripts" / "lint-script-frontmatter.py"

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

# stdout 判定 JSON のトップレベルキー (brief stdout)。
STDOUT_KEYS = (
    "status",
    "skip_reason",
    "skip_detail",
    "srg_root",
    "runtime",
    "images",
    "delegated_commands",
)
IMAGE_KEYS = ("section_id", "slug", "path", "status", "png_bytes")
SKIP_REASONS = ("srg-absent", "runtime-absent")

# fake node / codex の挙動を切り替える環境変数。
ENV_LOG = "HB_FAKE_LOG"
ENV_NODE_VERSION = "HB_FAKE_NODE_VERSION"
ENV_PROMPTS = "HB_FAKE_PROMPTS"   # all | none | fail
ENV_PNGS = "HB_FAKE_PNGS"         # all | first | invalid | none
ENV_META = "HB_FAKE_META"         # faithful | drift | drop (RESOLUTION-R23 (d) の meta 照合用)

DEFAULT_NODE_VERSION = "v20.11.0"

_FAKE_NODE = r'''#!{python}
"""build-image-prompts.js / generate-images-codex.js の CLI 形だけを模した fake node。

実物の node も codex も起動しない。呼ばれた argv を JSON 行としてログへ積み、
env で指示された成果物 (prompt.txt / meta.json / png) を置いて exit 0 を返す。
"""
import json
import os
import sys
from pathlib import Path

LOG = os.environ.get("{env_log}")
argv = sys.argv[1:]


def log(entry):
    if not LOG:
        return
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


if not argv or argv[0] in ("--version", "-v"):
    log({{"tool": "node", "argv": argv}})
    sys.stdout.write(os.environ.get("{env_ver}", "{default_ver}") + "\n")
    sys.exit(0)

script = Path(argv[0])
flags = {{}}
positional = []
i = 1
while i < len(argv):
    a = argv[i]
    if a.startswith("--"):
        name = a[2:]
        if "=" in name:
            k, v = name.split("=", 1)
            flags[k] = v
        elif i + 1 < len(argv) and not argv[i + 1].startswith("--"):
            flags[name] = argv[i + 1]
            i += 1
        else:
            flags[name] = True
    else:
        positional.append(a)
    i += 1

log({{"tool": "node", "script": script.name, "script_path": str(script),
     "flags": {{k: (v if isinstance(v, bool) else str(v)) for k, v in flags.items()}},
     "positional": positional, "cwd": os.getcwd()}})


def generated_dir():
    plan = flags.get("plan")
    if isinstance(plan, str):
        return Path(plan).parent
    if positional:
        return Path(positional[0]) / "assets" / "generated"
    sys.stderr.write("fake node: slide-dir が無い\n")
    sys.exit(1)


if script.name == "build-image-prompts.js":
    mode = os.environ.get("{env_prompts}", "all")
    if mode == "fail":
        sys.stderr.write("FAIL slide 1: fake validation error\n")
        sys.exit(1)
    if mode == "none":
        sys.exit(0)
    gen = generated_dir()
    plan_path = flags.get("plan")
    if not isinstance(plan_path, str):
        plan_path = str(gen / "image-deck-plan.json")
    data = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    gen.mkdir(parents=True, exist_ok=True)
    meta_mode = os.environ.get("{env_meta}", "faithful")
    for slide in data.get("slides", []):
        slug = slide.get("slug")
        (gen / (slug + ".prompt.txt")).write_text("fake prompt for " + slug + "\n", encoding="utf-8")
        meta = {{"slug": slug, "source": "fake"}}
        if meta_mode == "faithful":
            # 委譲先は計画の密度指示とモチーフをそのまま meta へ書き戻す。
            if "densityLevel" in slide:
                meta["densityLevel"] = slide["densityLevel"]
            if "motifs" in slide:
                meta["motifs"] = slide["motifs"]
        elif meta_mode == "drift":
            meta["densityLevel"] = "drifted-density-level"
            meta["motifs"] = ["drifted-motif"]
        # meta_mode == "drop" は densityLevel / motifs を書かない (委譲先が値を落とした状態)
        (gen / (slug + ".meta.json")).write_text(
            json.dumps(meta, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    sys.stdout.write("OK fake build-image-prompts\n")
    sys.exit(0)

if script.name == "generate-images-codex.js":
    gen = generated_dir()
    slugs = sorted(p.name[: -len(".prompt.txt")] for p in gen.glob("*.prompt.txt"))
    if flags.get("dry-run"):
        for slug in slugs:
            sys.stdout.write("[dry-run] codex exec --sandbox danger-full-access " + slug + "\n")
        sys.exit(0)
    mode = os.environ.get("{env_pngs}", "all")
    targets = {{"all": slugs, "first": slugs[:1], "invalid": slugs, "none": []}}[mode]
    for slug in targets:
        out = gen / (slug + ".png")
        if mode == "invalid":
            out.write_text("これは PNG ではなく codex の説明テキストである\n", encoding="utf-8")
        else:
            out.write_bytes({png_sig!r} + slug.encode("utf-8"))
    for slug in slugs:
        if slug not in targets:
            sys.stdout.write("warn: " + slug + " failed after 3 attempts\n")
    sys.stdout.write("done fake generate-images-codex\n")
    sys.exit(0)

sys.stderr.write("fake node: 未知の script " + script.name + "\n")
sys.exit(1)
'''

_FAKE_CODEX = r'''#!{python}
"""fake codex。存在確認 (shutil.which) 用。起動されたらログへ残す。

テストは『codex が実行されなかったこと』を log から確認する。
"""
import json
import os
import sys

LOG = os.environ.get("{env_log}")
if LOG:
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({{"tool": "codex", "argv": sys.argv[1:]}}, ensure_ascii=False) + "\n")
sys.stdout.write("fake codex\n")
sys.exit(0)
'''


class Missing(AssertionError):
    """成果物がまだ存在しないことを示す (P04 では赤が正しい状態)。"""


def require_script(tc: unittest.TestCase) -> Path:
    if not SCRIPT.is_file():
        tc.fail("実装が未存在: {} (P04 時点ではこの失敗が期待値。P05 で解消する)".format(SCRIPT))
    return SCRIPT


def require_file(tc: unittest.TestCase, path: Path, owner: str) -> Path:
    if not path.is_file():
        tc.fail("依存成果物が未存在: {} (owner: {})".format(path, owner))
    return path


def read_source(tc: unittest.TestCase) -> str:
    return require_script(tc).read_text(encoding="utf-8")


def brief() -> dict:
    return json.loads(BRIEF_PATH.read_text(encoding="utf-8"))


def baked_text_discipline() -> dict:
    """RESOLUTION-R23 (b) の数値の唯一の正本 (script-brief-C21.baked_text_discipline)。"""
    return brief()["baked_text_discipline"]


def blocks_per_image_max() -> int:
    """1 画像あたりの焼き込みブロック数の上限。テスト側に数値リテラルを置かない。"""
    return int(baked_text_discipline()["blocks_per_image_max"])


def chars_per_block_max() -> int:
    """1 ブロックの字数上限 (書記素単位)。テスト側に数値リテラルを置かない。"""
    return int(baked_text_discipline()["chars_per_block_max"])


def baked_forms() -> tuple:
    """閉じた 3 語の form allowlist。語も brief から読む。"""
    return tuple(baked_text_discipline()["forms"].keys())


def image_style_families() -> dict:
    return brief()["image_style_families"]


def style_family_map() -> dict:
    """図解型 6 語 → style family の全域写像 (RESOLUTION-R23 (c))。"""
    return dict(image_style_families()["selection_rule"]["map"])


def diagram_patterns() -> tuple:
    return tuple(style_family_map().keys())


def family_genome_template(family: str) -> str:
    return image_style_families()["families"][family]["genome"]


def srg_hosted_family() -> str:
    """genome を SRG 同梱側に持つ family (名前をテストへ直書きしない)。"""
    for name in image_style_families()["families"]:
        if "<SRG_ROOT>" in family_genome_template(name):
            return name
    raise AssertionError("SRG 同梱 genome を持つ family が brief に無い")


def handout_hosted_family() -> str:
    """genome を handout 側に同梱する family (producer は P05-x-04)。"""
    for name in image_style_families()["families"]:
        if "<HB_ROOT>" in family_genome_template(name):
            return name
    raise AssertionError("handout 側 genome を持つ family が brief に無い")


def patterns_for_family(family: str) -> tuple:
    return tuple(p for p, f in style_family_map().items() if f == family)


def resolve_family_genome(family: str, *, srg_root, hb_root) -> Path:
    """brief の genome テンプレートのプレースホルダを実パスへ解決する。"""
    template = family_genome_template(family)
    return Path(
        template.replace("<SRG_ROOT>", str(srg_root)).replace("<HB_ROOT>", str(hb_root))
    )


def handout_genome_path() -> Path:
    """repo 実体としての handout 側 genome (P05-x-04 の産出物)。"""
    return resolve_family_genome(handout_hosted_family(), srg_root=REAL_SRG_ROOT, hb_root=PLUGIN_ROOT)


def real_genome_data() -> dict:
    return json.loads((REAL_SRG_ROOT / SRG_GENOME_RELPATH).read_text(encoding="utf-8"))


def find_key(node, key):
    if isinstance(node, dict):
        if key in node:
            return node[key]
        for value in node.values():
            found = find_key(value, key)
            if found is not None:
                return found
    elif isinstance(node, list):
        for value in node:
            found = find_key(value, key)
            if found is not None:
                return found
    return None


def genome_density_levels(data: dict | None = None) -> tuple:
    """密度語彙は genome ファイルからしか取らない (テスト側で 3 語を列挙しない)。"""
    levels = find_key(data if data is not None else real_genome_data(), "densityLevels")
    if not isinstance(levels, dict) or not levels:
        raise AssertionError("genome に densityPreservation.densityLevels が無い")
    return tuple(levels.keys())


def default_density_level() -> str:
    return genome_density_levels()[0]


def inventory_component(component_id: str = "C21") -> dict:
    data = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))

    def walk(node):
        if isinstance(node, dict):
            if node.get("id") == component_id:
                return node
            for value in node.values():
                found = walk(value)
                if found is not None:
                    return found
        elif isinstance(node, list):
            for value in node:
                found = walk(value)
                if found is not None:
                    return found
        return None

    return walk(data) or {}


# --- fixture 生成 ---------------------------------------------------------


def make_fake_bin(tmp: Path, *, node: bool = True, codex: bool = True) -> Path:
    """PATH に置く fake 実行体を作り、その bin ディレクトリを返す。"""
    bin_dir = Path(tmp) / "fake-bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    if node:
        target = bin_dir / "node"
        target.write_text(
            _FAKE_NODE.format(
                python=sys.executable,
                env_log=ENV_LOG,
                env_ver=ENV_NODE_VERSION,
                default_ver=DEFAULT_NODE_VERSION,
                env_prompts=ENV_PROMPTS,
                env_pngs=ENV_PNGS,
                env_meta=ENV_META,
                png_sig=PNG_SIGNATURE,
            ),
            encoding="utf-8",
        )
        target.chmod(0o755)
    if codex:
        target = bin_dir / "codex"
        target.write_text(
            _FAKE_CODEX.format(python=sys.executable, env_log=ENV_LOG), encoding="utf-8"
        )
        target.chmod(0o755)
    return bin_dir


def make_srg(tmp: Path, *, name: str = "slide-report-generator", motifs=None, omit=()) -> Path:
    """SRG 実体らしいディレクトリツリーを作る。

    omit に vendor script の相対パスを渡すと、その 1 本だけ欠けた
    「名前は SRG だが実体ではない」ツリーになる。
    """
    root = Path(tmp) / name
    (root / "vendor" / "scripts").mkdir(parents=True, exist_ok=True)
    (root / "vendor" / "assets").mkdir(parents=True, exist_ok=True)
    (root / "vendor" / "package.json").write_text(
        json.dumps({"type": "module"}, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    for relpath in SRG_VENDOR_SCRIPTS:
        if relpath in omit:
            continue
        (root / relpath).write_text("// fake vendor script\n", encoding="utf-8")
    (root / SRG_GENOME_RELPATH).write_text(
        json.dumps(fake_genome_payload(motifs), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return root


def fake_genome_payload(motifs=None) -> dict:
    """fake genome。密度語彙と layout 表は実 genome から読んで写す (テスト側で列挙しない)。

    RESOLUTION-R23 (d) 以降、script は densityLevels と layoutSelectionByStructure を
    genome から引く。fixture がこれらを持たないと『script が自前で列挙しているか』を
    区別できないため、実 genome の当該部分をそのまま載せる。
    """
    real = real_genome_data()
    payload = {
        "schemaVersion": real.get("schemaVersion", "1"),
        "styleName": "fake-genome",
        "motifs": [{"name": m, "meaning": m, "appearance": m} for m in (motifs or default_motifs())],
    }
    for key in ("contentAdaptationRules", "layoutSelectionByStructure"):
        if key in real:
            payload[key] = real[key]
    return payload


def default_motifs():
    """fixture 用の motif 名。語彙は genome ファイルからしか取らない (テスト側へ写さない)。"""
    return real_genome_motifs()[:3]


def real_genome_motifs():
    data = json.loads((REAL_SRG_ROOT / SRG_GENOME_RELPATH).read_text(encoding="utf-8"))
    return [m["name"] for m in data.get("motifs", [])]


def make_fake_plugin_root(tmp: Path, *, srg: Path | None = None) -> Path:
    """HB_ROOT に渡す偽 plugin root。srg を渡すと兄弟位置へ配置する。"""
    plugins = Path(tmp) / "fake-plugins"
    root = plugins / "guide-doc-generator"
    (root / "scripts").mkdir(parents=True, exist_ok=True)
    (root / ".claude-plugin").mkdir(parents=True, exist_ok=True)
    (root / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "guide-doc-generator"}, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    if srg is not None:
        dest = plugins / srg.name
        if not dest.exists():
            dest.symlink_to(srg, target_is_directory=True)
    return root


def install_handout_genome(tc: unittest.TestCase, hb_root: Path) -> Path:
    """handout 側 genome (P05-x-04 の産出物) を偽 plugin root へ設置する。

    実体が無ければ **skip せず fail** する。同梱すべき genome の欠落は環境の問題ではなく
    plugin の同梱漏れであり、fail-closed が契約 (algorithm 3b)。
    """
    source = require_file(tc, handout_genome_path(), "P05-x-04")
    dest = resolve_family_genome(handout_hosted_family(), srg_root=REAL_SRG_ROOT, hb_root=hb_root)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(source.read_bytes())
    return dest


def motif_roles(names) -> dict:
    """RESOLUTION-R23 (d): motifs は {platform, primary, props[]} の 3 役構造体。"""
    names = [str(n) for n in names] or [""]
    return {"platform": names[0], "primary": names[-1], "props": [names[0]]}


AUTO_KEY = "_hb_auto"


def section(
    section_id: str,
    *,
    heading: str | None = None,
    subject: str | None = None,
    diagram_structure: str | None = None,
    motifs=None,
    diagram_pattern: str | None = None,
    density_level: str | None = None,
    baked_text=None,
    adaptation_trace=None,
    **extra,
) -> dict:
    """画像計画の 1 セクション。英文は brief の下限 (40 字以上) を満たす長さで作る。

    RESOLUTION-R23 以降の必須フィールド (motifs の 3 役 / density_level /
    adaptation_trace / baked_text / diagram_pattern) を既定で満たす形にしてある。
    既定の本文は数字を 1 文字も含まない — 数値を持つセクションは form=metric の
    ブロックをちょうど 1 件持たねばならず (baked_text_discipline.metric_rule)、
    既定 fixture がそれを暗黙に要求すると検査点が混ざるためである。
    """
    auto = []
    if isinstance(motifs, dict):
        roles = {"platform": motifs.get("platform"), "primary": motifs.get("primary"),
                 "props": list(motifs.get("props", []))}
    elif motifs is None:
        roles = motif_roles(default_motifs())
        auto.append("motifs")
    else:
        roles = motif_roles(motifs)
    if diagram_pattern is None:
        auto.append("diagram_pattern")
    data = {
        "section_id": section_id,
        "heading": heading or "セクション {}".format(section_id),
        "lead_line": "この節を読むと {} の全体像が短い時間で掴める".format(section_id),
        "goal": "読み終えたら {} の手順を自分で再現できる状態になる".format(section_id),
        "subject": subject
        or (
            "A printable hand drawn diagram of the {} workflow with three labelled "
            "panels arranged from left to right".format(section_id)
        ),
        "diagram_structure": diagram_structure
        or (
            "Left panel holds the input documents, the centre panel holds the build "
            "pipeline, and the right panel holds the printed handout"
        ),
        "overlay_text": ["INPUT", "BUILD", "OUTPUT"],
        "alt": "{} の流れをパネルで示した図".format(section_id),
        "motifs": roles,
        "diagram_pattern": diagram_pattern or patterns_for_family(srg_hosted_family())[0],
        "density_level": density_level or default_density_level(),
        "baked_text": list(baked_text) if baked_text is not None else [
            {"form": baked_forms()[0], "text": "配布資料"}
        ],
        "adaptation_trace": list(adaptation_trace) if adaptation_trace is not None else [
            {"concept": "手順", "motif": roles["primary"]}
        ],
        AUTO_KEY: auto,
    }
    data.update(extra)
    return data


def plan_payload(sections=None, **extra) -> dict:
    """既定セクション列は (図解型, motifs.primary) が全件同一にならないよう位置で振る。

    全セクション同一は RESOLUTION-R23 (e) で exit2 になるため、既定 fixture が
    その違反を踏むと他の検査点が全部その 1 件に飲まれる。
    """
    raw = list(sections if sections is not None else [section("intro"), section("build")])
    iso_patterns = patterns_for_family(srg_hosted_family())
    names = default_motifs()
    prepared = []
    for index, item in enumerate(raw):
        data = dict(item)
        auto = data.pop(AUTO_KEY, [])
        # 自動振り分けは「section() が既定で入れた値を位置でばらす」ためのもので、
        # 呼び手が意図して pop したキーを復活させてはならない (復活させると
        # 「図解型を持たないセクション」の検査が素通りする)。
        if "diagram_pattern" in auto and iso_patterns and "diagram_pattern" in data:
            data["diagram_pattern"] = iso_patterns[index % len(iso_patterns)]
        if "motifs" in auto and names and isinstance(data.get("motifs"), dict):
            roles = dict(data["motifs"])
            previous = roles.get("primary")
            roles["primary"] = names[index % len(names)]
            data["motifs"] = roles
            data["adaptation_trace"] = [
                dict(entry, motif=roles["primary"]) if entry.get("motif") == previous else entry
                for entry in data.get("adaptation_trace", [])
            ]
        prepared.append(data)
    payload = {
        "title": "資料作成プラグインの使い方",
        "background": "社内向けの印刷配布資料を 1 ファイルで作るための研修資料である",
        "accent": "#2F6F4F",
        "sections": prepared,
    }
    payload.update(extra)
    return payload


def write_plan(path: Path, payload: dict) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def expected_slug(index: int, section_id: str) -> str:
    """algorithm 6: sec-NN-<section_id の kebab 化> (1 始まり)。"""
    kebab = "".join(ch.lower() if ch.isalnum() else "-" for ch in section_id)
    while "--" in kebab:
        kebab = kebab.replace("--", "-")
    return "sec-{:02d}-{}".format(index, kebab.strip("-"))


def make_assets_dir(tmp: Path, name: str = "assets") -> Path:
    path = Path(tmp) / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def png_bytes(slug: str) -> bytes:
    return PNG_SIGNATURE + slug.encode("utf-8")


def place_existing_png(assets_dir: Path, slug: str, data: bytes | None = None) -> Path:
    images = Path(assets_dir) / "images"
    images.mkdir(parents=True, exist_ok=True)
    target = images / (slug + ".png")
    target.write_bytes(data if data is not None else png_bytes(slug))
    return target


# --- 実行 -----------------------------------------------------------------


def clean_env(tmp: Path | None = None, *, bin_dir: Path | None = None, srg_root=None,
              hb_root=None, log: Path | None = None, **overrides) -> dict:
    """ユーザー環境と repo の実 SRG から隔離した実行環境。

    hb_root を明示しない場合でも、tmp を渡せば偽 plugin root を作って HB_ROOT に入れる。
    これをしないと解決段 (c) が repo 実在の plugins/slide-report-generator を拾ってしまい、
    「SRG 不在」の再現ができない。
    """
    env = dict(os.environ)
    for key in ("SRG_ROOT", "HB_ROOT", "CLAUDE_PLUGIN_ROOT", ENV_PROMPTS, ENV_PNGS, ENV_META,
                ENV_NODE_VERSION, ENV_LOG):
        env.pop(key, None)
    env["PYTHONIOENCODING"] = "utf-8"
    if bin_dir is not None:
        env["PATH"] = str(bin_dir)
    if hb_root is None and tmp is not None:
        hb_root = make_fake_plugin_root(Path(tmp))
    if hb_root is not None:
        env["HB_ROOT"] = str(hb_root)
    if srg_root is not None:
        env["SRG_ROOT"] = str(srg_root)
    if log is not None:
        env[ENV_LOG] = str(log)
    for key, value in overrides.items():
        if value is None:
            env.pop(key, None)
        else:
            env[key] = str(value)
    return env


def run(args, env=None, cwd=None, script: Path | None = None, stdin_data: str | None = None):
    cmd = [sys.executable, str(script or SCRIPT), *[str(a) for a in args]]
    return subprocess.run(
        cmd,
        input=(stdin_data or "").encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env if env is not None else clean_env(),
        cwd=str(cwd) if cwd else str(REPO_ROOT),
        timeout=120,
    )


def out_text(proc) -> str:
    return proc.stdout.decode("utf-8", "replace")


def err_text(proc) -> str:
    return proc.stderr.decode("utf-8", "replace")


def describe(proc) -> str:
    return "exit={}\n--- stdout ---\n{}\n--- stderr ---\n{}".format(
        proc.returncode, out_text(proc)[:4000], err_text(proc)[:4000]
    )


def stdout_json(tc: unittest.TestCase, proc) -> dict:
    """stdout の判定 JSON 1 個を取り出す (brief stdout: 人間向けの文は stderr だけ)。"""
    text = out_text(proc).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        tc.fail("stdout が JSON 1 個ではない ({}):\n{}".format(exc, describe(proc)))
    if not isinstance(data, dict):
        tc.fail("stdout の JSON が object ではない:\n{}".format(describe(proc)))
    return data


def node_log(log: Path):
    path = Path(log)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def invoked_scripts(log: Path):
    return [e.get("script") for e in node_log(log) if e.get("tool") == "node" and e.get("script")]


def tree_snapshot(root: Path):
    """ディレクトリ配下の相対パス -> バイト列。書き込みスコープの検査に使う。"""
    root = Path(root)
    snapshot = {}
    if not root.exists():
        return snapshot
    for path in sorted(root.rglob("*")):
        if path.is_file():
            snapshot[str(path.relative_to(root))] = path.read_bytes()
    return snapshot


class BridgeTestCase(unittest.TestCase):
    """実装未存在なら最初に赤 (failure) を出す共通の土台。"""

    def setUp(self):
        require_script(self)
