#!/usr/bin/env python3
# /// script
# name: docx_lib
# purpose: python-docx を使わず標準ライブラリ(zipfile+xml.etree)だけで .docx を読み書きする最小実装。pip install 不要。
# inputs:
#   - .docx パス
# outputs:
#   - 段落/run の読み書き・黄色ハイライト・段落削除/追加・保存
# contexts: [C]
# network: false
# write-scope: local-tmp
# dependencies: []
# requires-python: ">=3.11"
# ///
"""責務: .docx の最小編集(python-docx 代替・標準ライブラリのみ)。

docx_fill / appendix / scan_template が必要とする API だけを互換提供する:
  Document(path) / doc.paragraphs / doc.tables / doc.add_paragraph() / doc.save(path)
  Para.runs / .text / .add_run(text) / .alignment / .clear_runs() / .delete()
  Run.text / .font(highlight_color, name) / .add_break(page?) / .bold
  定数 YELLOW / PAGE / CENTER
.docx は ZIP。本文は word/document.xml。namespace は元XMLから動的に register して prefix を保持する。
"""

import re
import xml.etree.ElementTree as ET
import zipfile

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"

# python-docx 互換の定数(値は WordML の属性値)
YELLOW = "yellow"
PAGE = "page"
CENTER = "center"


def _q(tag):
    return f"{{{W}}}{tag}"


def _register_ns(xml_bytes):
    """document.xml の xmlns 宣言を全て register_namespace し、保存時に prefix を保持する。"""
    for m in re.finditer(rb'xmlns:([A-Za-z0-9]+)="([^"]+)"', xml_bytes):
        try:
            ET.register_namespace(m.group(1).decode(), m.group(2).decode())
        except ValueError:
            pass
    m = re.search(rb'xmlns="([^"]+)"', xml_bytes)
    if m:
        ET.register_namespace("", m.group(1).decode())


class Font:
    def __init__(self, r_elem):
        self._r = r_elem

    def _rpr(self, create=False):
        rpr = self._r.find(_q("rPr"))
        if rpr is None and create:
            rpr = ET.Element(_q("rPr"))
            self._r.insert(0, rpr)
        return rpr

    @property
    def highlight_color(self):
        rpr = self._rpr()
        if rpr is None:
            return None
        h = rpr.find(_q("highlight"))
        return h.get(_q("val")) if h is not None else None

    @highlight_color.setter
    def highlight_color(self, val):
        if val is None:
            rpr = self._rpr()
            if rpr is not None:
                h = rpr.find(_q("highlight"))
                if h is not None:
                    rpr.remove(h)
            return
        rpr = self._rpr(create=True)
        h = rpr.find(_q("highlight"))
        if h is None:
            h = ET.SubElement(rpr, _q("highlight"))
        h.set(_q("val"), val)

    @property
    def name(self):
        rpr = self._rpr()
        if rpr is None:
            return None
        rf = rpr.find(_q("rFonts"))
        return rf.get(_q("ascii")) if rf is not None else None

    @name.setter
    def name(self, val):
        if not val:
            return
        rpr = self._rpr(create=True)
        rf = rpr.find(_q("rFonts"))
        if rf is None:
            rf = ET.SubElement(rpr, _q("rFonts"))
        for attr in ("ascii", "hAnsi", "eastAsia"):
            rf.set(_q(attr), val)

    # size/bold は差込で参照されるが視覚継承は name で足りるため no-op 互換
    @property
    def size(self):
        return None

    @size.setter
    def size(self, val):
        pass

    @property
    def bold(self):
        rpr = self._rpr()
        return rpr is not None and rpr.find(_q("b")) is not None

    @bold.setter
    def bold(self, val):
        if val:
            rpr = self._rpr(create=True)
            if rpr.find(_q("b")) is None:
                ET.SubElement(rpr, _q("b"))


class Run:
    def __init__(self, r_elem):
        self._r = r_elem
        self.font = Font(r_elem)

    @property
    def text(self):
        return "".join((t.text or "") for t in self._r.findall(_q("t")))

    @text.setter
    def text(self, val):
        for t in self._r.findall(_q("t")):
            self._r.remove(t)
        t = ET.SubElement(self._r, _q("t"))
        t.set(XML_SPACE, "preserve")
        t.text = val

    def add_break(self, break_type=None):
        br = ET.SubElement(self._r, _q("br"))
        if break_type == PAGE:
            br.set(_q("type"), "page")


class Para:
    def __init__(self, p_elem, parent):
        self._p = p_elem
        self._parent = parent

    @property
    def runs(self):
        return [Run(r) for r in self._p.findall(_q("r"))]

    @property
    def text(self):
        return "".join((t.text or "") for t in self._p.iter(_q("t")))

    def add_run(self, text=""):
        r = ET.SubElement(self._p, _q("r"))
        run = Run(r)
        if text:
            run.text = text
        return run

    def clear_runs(self):
        for r in self._p.findall(_q("r")):
            self._p.remove(r)

    def delete(self):
        if self._parent is not None:
            self._parent.remove(self._p)

    @property
    def alignment(self):
        pPr = self._p.find(_q("pPr"))
        if pPr is None:
            return None
        jc = pPr.find(_q("jc"))
        return jc.get(_q("val")) if jc is not None else None

    @alignment.setter
    def alignment(self, val):
        pPr = self._p.find(_q("pPr"))
        if pPr is None:
            pPr = ET.Element(_q("pPr"))
            self._p.insert(0, pPr)
        jc = pPr.find(_q("jc"))
        if jc is None:
            jc = ET.SubElement(pPr, _q("jc"))
        jc.set(_q("val"), val or "left")


class _Cell:
    def __init__(self, tc_elem):
        self._tc = tc_elem

    @property
    def paragraphs(self):
        return [Para(p, self._tc) for p in self._tc.findall(_q("p"))]


class _Row:
    def __init__(self, tr_elem):
        self._tr = tr_elem

    @property
    def cells(self):
        return [_Cell(tc) for tc in self._tr.findall(_q("tc"))]


class Table:
    def __init__(self, tbl_elem):
        self._tbl = tbl_elem

    @property
    def rows(self):
        return [_Row(tr) for tr in self._tbl.findall(_q("tr"))]


class Doc:
    def __init__(self, path):
        with zipfile.ZipFile(path) as z:
            self._names = z.namelist()
            self._other = {n: z.read(n) for n in self._names if n != "word/document.xml"}
            doc_xml = z.read("word/document.xml")
        _register_ns(doc_xml)
        self._root = ET.fromstring(doc_xml)
        self._body = self._root.find(_q("body"))

    @property
    def paragraphs(self):
        return [Para(p, self._body) for p in self._body.findall(_q("p"))]

    @property
    def tables(self):
        return [Table(t) for t in self._body.findall(_q("tbl"))]

    def add_paragraph(self):
        """本文末尾(sectPr の前)に空段落を追加して返す。"""
        p = ET.Element(_q("p"))
        sectPr = self._body.find(_q("sectPr"))
        if sectPr is not None:
            self._body.insert(list(self._body).index(sectPr), p)
        else:
            self._body.append(p)
        return Para(p, self._body)

    def save(self, path):
        body_xml = ET.tostring(self._root, encoding="unicode")
        header = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\r\n'
        full = (header + body_xml).encode("utf-8")
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            for n in self._names:
                if n == "word/document.xml":
                    z.writestr(n, full)
                else:
                    z.writestr(n, self._other[n])
            if "word/document.xml" not in self._names:
                z.writestr("word/document.xml", full)


def Document(path):
    """python-docx 互換エントリ。新規作成(空 .docx)は未サポート(本スキルはひな形を必ず開く)。"""
    return Doc(path)
