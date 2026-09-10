"""RESOLUTION-R23 のテスト共通土台。

数値・語彙の正本はすべて `_harness` 経由で `script-brief-C21.json` か genome ファイルから読む。
本ファイルは 6 / 12 / low / medium / high / motif 名 / family 名 のいずれの literal も持たない
(持つと正本が二重化し、RESOLUTION-P04-x-05 の『契約に書くのは不変条件であって導出値ではない』に反する)。

genome の実体について:
- isometric 側は SRG 同梱の実 genome を fixture へ写して使う (read-only 参照)。
- handout 側 (flat) の genome は `P05-x-04` の産出物であり、**未存在なら skip せず fail** する。
  同梱漏れを skip へ畳むと『画風が黙って差し替わった』ことに誰も気づけない (algorithm 3b)。
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import _harness as H


# RESOLUTION-R23 (a) の 2 つの policy 名。値そのものは裁定文の語であり導出値ではないので、
# 本ファイル 1 箇所に置いて各テストはここを参照する。
DEFAULT_TEXT_POLICY = "baked-with-overlay"
OVERLAY_ONLY_POLICY = "overlay-only"


def genome_motif_names(path: Path) -> list:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [m.get("name") for m in data.get("motifs", []) if isinstance(m, dict)]


def iso_family() -> str:
    return H.srg_hosted_family()


def flat_family() -> str:
    return H.handout_hosted_family()


def iso_patterns() -> tuple:
    return H.patterns_for_family(iso_family())


def flat_patterns() -> tuple:
    return H.patterns_for_family(flat_family())


def keyword_block(text: str) -> dict:
    return {"form": H.baked_forms()[0], "text": text}


def block_of_form(form: str, text: str, **extra) -> dict:
    block = {"form": form, "text": text}
    block.update(extra)
    return block


def form_named(fragment: str) -> str:
    """brief の forms から 1 語を引く (3 語を test 側へ写さないための間接参照)。"""
    for name in H.baked_forms():
        if name == fragment:
            return name
    raise AssertionError("form {} が brief の allowlist に無い: {}".format(fragment, H.baked_forms()))


class R23TestCase(H.BridgeTestCase):
    """事前検査 (algorithm 8b) を叩くための実行土台。"""

    def build_env(self, tmp, *, motifs=None, with_handout_genome=False, env_extra=None):
        tmp = Path(tmp)
        srg = H.make_srg(tmp, motifs=motifs)
        hb_root = H.make_fake_plugin_root(tmp)
        if with_handout_genome:
            H.install_handout_genome(self, hb_root)
        bin_dir = H.make_fake_bin(tmp)
        log = tmp / "log.jsonl"
        env = H.clean_env(tmp, bin_dir=bin_dir, hb_root=hb_root, log=log, **(env_extra or {}))
        return {"tmp": tmp, "srg": srg, "hb_root": hb_root, "env": env, "log": log}

    def run_plan(self, tmp, sections, *, motifs=None, extra=(), plan_extra=None,
                 with_handout_genome=False, env_extra=None):
        ctx = self.build_env(
            tmp, motifs=motifs, with_handout_genome=with_handout_genome, env_extra=env_extra
        )
        plan = H.write_plan(
            ctx["tmp"] / "plan.json", H.plan_payload(sections=sections, **(plan_extra or {}))
        )
        assets = H.make_assets_dir(ctx["tmp"])
        ctx["assets"] = assets
        ctx["proc"] = H.run(
            ["--image-plan", plan, "--assets-dir", assets, "--srg-root", ctx["srg"], *extra],
            env=ctx["env"],
        )
        return ctx

    def dry_run_plan(self, tmp, sections, **kwargs):
        extra = tuple(kwargs.pop("extra", ())) + ("--dry-run",)
        return self.run_plan(tmp, sections, extra=extra, **kwargs)

    # --- 判定ヘルパ --------------------------------------------------------

    def assertExit2(self, ctx, message):
        self.assertEqual(2, ctx["proc"].returncode, message + "\n" + H.describe(ctx["proc"]))

    def assertNotExit2(self, ctx, message):
        self.assertNotEqual(2, ctx["proc"].returncode, message + "\n" + H.describe(ctx["proc"]))

    def assertStoppedBeforeDelegating(self, ctx):
        self.assertEqual(
            [], H.invoked_scripts(ctx["log"]),
            "契約違反なのに委譲先を起動している:\n" + H.describe(ctx["proc"]),
        )

    def decks(self, ctx):
        """作業ディレクトリの image-deck-plan (family ごとに分かれる場合がある) を全部返す。"""
        generated = Path(ctx["assets"]) / "srg-work" / "assets" / "generated"
        paths = sorted(generated.glob("image-deck-plan*.json")) if generated.is_dir() else []
        if not paths:
            self.fail("image-deck-plan が 1 件も無い:\n" + H.describe(ctx["proc"]))
        return [json.loads(p.read_text(encoding="utf-8")) for p in paths]

    def slides(self, ctx):
        out = []
        for deck in self.decks(ctx):
            for slide in deck.get("slides", []):
                out.append((deck, slide))
        return out

    def temp(self):
        return tempfile.TemporaryDirectory()
