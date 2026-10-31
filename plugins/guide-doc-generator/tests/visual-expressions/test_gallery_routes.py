"""関係の候補を、実装済みのHTML/CSS・SVGの実例へ結び付ける。"""
import importlib.util
import json
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def gallery():
    spec = importlib.util.spec_from_file_location("route_gallery", ROOT / "scripts/build-diagram-gallery.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build_gallery()


class Outline(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.candidate_links = []
        self.in_candidates = False
        self.html_examples = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("id"):
            self.ids.add(attrs["id"])
        if tag == "section" and attrs.get("id") == "candidates":
            self.in_candidates = True
        if self.in_candidates and tag == "a":
            self.candidate_links.append(attrs.get("href"))
        if attrs.get("data-hb-gallery-medium") == "html":
            self.html_examples.append(attrs["id"])

    def handle_endtag(self, tag):
        if tag == "section":
            self.in_candidates = False


def test_catalog_routes_resolve_and_have_real_html_examples():
    catalog = json.loads((ROOT / "config/handout-diagrams.json").read_text())
    assert len(catalog["intents"]) >= 34
    assert len(catalog["html_examples"]) >= 3
    for intent in catalog["intents"]:
        assert all(key in catalog["html_examples"] for key in intent.get("html_examples", []))
    page = Outline()
    page.feed(gallery())
    assert len(page.html_examples) >= 3
    assert page.candidate_links
    assert all(link and link.startswith("#") and link[1:] in page.ids for link in page.candidate_links)
    expected = {"#" + pattern for intent in catalog["intents"] for pattern in intent["patterns"]}
    assert expected <= set(page.candidate_links)


def test_html_is_explained_as_rendering_method_and_conditions_stay_semantic():
    html = gallery()
    assert "HTMLは図の種類ではなく" in html
    assert "HTML/CSS" in html and "SVG" in html and "専用作図" in html
    catalog = json.loads((ROOT / "config/handout-diagrams.json").read_text())
    for intent in catalog["intents"]:
        assert not any(word in intent["selection_note"] for word in ("B05", "B07", "IMG", "sequence", "relationship", "gantt"))
