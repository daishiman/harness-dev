#!/usr/bin/env python3
# /// script
# name: build-graph-node
# purpose: C02 single writer for ordinary dev-graph artifacts and C14 macro features; compose kind templates, validate the staged graph, then atomically add or diff-update nodes with an immutable receipt.
# inputs: ["argv: add|update --repo-root PATH --input JSON [--config PATH] [--dry-run]"]
# outputs: ["stdout: JSON preview/receipt or rejection report"]
# requires-python = ">=3.10"
# dependencies: [_common.py, validate-graph-schema.py, resolve-repo-context.py]
# contexts: [A, B, C, E]
# network: false
# write-scope: caller repository content roots, the C24-resolved graph, and immutable receipts beside that graph
# ///
"""C02 artifact writer (add/update) that shares the register-package writer lock."""
from __future__ import annotations

import argparse
import copy
import fcntl
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator

from _common import ContractError, atomic_json, contained, dump, load_json, utc_now

HERE = Path(__file__).resolve().parent
PLUGIN_ROOT = HERE.parent
OWNER = "C02/run-dev-graph-node"
KIND_PREFIX = {"issue": "issue", "task": "task", "specification": "spec", "architecture": "arch", "document": "doc",
               "feature": "feature"}
C24_ROOT_KEY = {"issue": "issues", "task": "tasks", "specification": "specifications",
                "architecture": "architecture", "document": "documents", "feature": "features"}
ROUTABLE_KINDS = set(KIND_PREFIX) - {"feature"}
SUBTYPE_ORDER = ["frontend", "backend", "infrastructure", "data", "security", "api"]
ARCH_SUBTYPES = SUBTYPE_ORDER[:5]
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,79}$")
OPERATION = re.compile(r"^[A-Za-z0-9_.:/ -]{1,80}$")
HEADING = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*$")
FENCE = re.compile(r"^\s*(```|~~~)")
FRONT_KEY = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*)[ \t]*:")
LIST_MARK = re.compile(r"^(?:[-*+>]\s+|\d+[.)]\s+)?(?:\[[ xX]\]\s+)?")
# Every code point str.splitlines() ends a line on: a key holding one would split into several headings on re-read.
LINE_BREAK = re.compile(r"[\n\r\v\f\x1c-\x1e\x85\u2028\u2029]")
HEADING_MAX = 120
# Names readiness reports (`api-contract`, `<subtype>:<leaf>`, `api:<op>:<leaf>`); they address leaves, never H2 titles.
READINESS_ITEM = re.compile(rf"^(?:api-contract$|(?:{'|'.join(SUBTYPE_ORDER)}):)")
SECRET = re.compile(r"(sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|xox[baprs]-[A-Za-z0-9-]{10,})")
AUTO_CONFIDENCE, AUTO_MARGIN = 0.80, 0.15
TRACKER_FROM_CONFIG = {"beads": "beads", "github": "github", "none": "none"}
MACRO_TEXT_KEYS = ("purpose", "goal")
MACRO_LIST_KEYS = ("scope_in", "scope_out", "acceptance", "architecture_refs")
# feature body sections that are projections of frontmatter: callers change them through macro_patch/node_patch only.
MACRO_SECTIONS = ("目的", "到達状態", "スコープ", "受入", "アーキテクチャ参照", "機能間依存")
# readiness_fill {via, key} for each projection: the field whose value the section renders.
MACRO_FILL = {"目的": ("macro_patch", "purpose"), "到達状態": ("macro_patch", "goal"), "スコープ": ("macro_patch", "scope_in"),
              "受入": ("macro_patch", "acceptance"), "アーキテクチャ参照": ("macro_patch", "architecture_refs"),
              "機能間依存": ("node_patch", "depends_on")}
ADD_KEYS = {
    "artifact_kind", "slug", "title", "project_id", "domain", "tracker_binding", "owners", "tags",
    "priority", "start_date", "target_date", "iteration", "depends_on", "related_nodes", "resource_scope",
    "artifact_subtypes", "classification", "sections", "subtype_sections", "api_contracts", "source_lineage",
    "macro",
}
PATCH_KEYS = {
    "title", "project_id", "domain", "owners", "tags", "priority", "start_date", "target_date",
    "iteration", "depends_on", "related_nodes", "resource_scope", "status",
}
UPDATE_KEYS = {"graph_node_id", "node_patch", "set_sections", "append_sections", "add_subtypes",
               "subtype_sections", "add_api_contracts", "macro_patch"}
PACKAGE_KEYS = {"parent_feature", "feature_package_id", "phase_ref"}


def _load_validator() -> Any:
    spec = importlib.util.spec_from_file_location("dev_graph_validate_graph_schema", HERE / "validate-graph-schema.py")
    if spec is None or spec.loader is None:
        raise ContractError("cannot load validate-graph-schema.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VGS = _load_validator()


class WriterError(ContractError):
    def __init__(self, code: str, detail: str, findings: list[dict[str, str]] | None = None) -> None:
        super().__init__(f"{code}: {detail}")
        self.code, self.detail, self.findings = code, detail, findings or []


# ---------------------------------------------------------------- C24 / lock / io

def _context(repo_root: str, config: str) -> dict[str, Any]:
    argv = [sys.executable, str(HERE / "resolve-repo-context.py"), "--repo-root", repo_root,
            "--config", config, "--mode", "write"]
    cp = subprocess.run(argv, text=True, capture_output=True, check=False)
    if cp.returncode:
        raise WriterError("c24_context_failed", (cp.stderr or cp.stdout).strip())
    ctx = json.loads(cp.stdout)
    root = Path(ctx["repo_root"]).resolve(strict=True)
    if Path(ctx["content_roots"]["repository"]).resolve(strict=True) != root:
        raise WriterError("c24_context_failed", "content_roots.repository differs from repo_root")
    return ctx


def _content_root(ctx: dict[str, Any], root: Path, kind: str) -> Path:
    canonical = root / VGS.ROOT_BY_KIND[kind]
    declared = (ctx.get("content_roots") or {}).get(C24_ROOT_KEY[kind])
    if declared is not None and Path(declared).resolve(strict=False) != canonical.resolve(strict=False):
        raise WriterError("content_root_mismatch", f"{C24_ROOT_KEY[kind]} must resolve to {VGS.ROOT_BY_KIND[kind]}/ for file_path parity")
    if canonical.is_symlink() or not canonical.is_dir():
        raise WriterError("content_root_missing", f"{VGS.ROOT_BY_KIND[kind]}/ is absent; run run-dev-graph-init first")
    return canonical


@contextmanager
def _single_writer(graph: Path) -> Iterator[None]:
    # Same lock file as register-package.py so both C02 entry points serialize on one graph.
    lock_path = graph.with_name(f".{graph.name}.register.lock")
    with lock_path.open("a+", encoding="utf-8") as stream:
        try:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise WriterError("writer_busy", f"another C02 writer holds {lock_path.name}") from exc
        yield


def _write_atomic(path: Path, data: bytes, *, create_only: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if create_only:
            try:
                os.link(temp, path)
            except FileExistsError as exc:
                raise WriterError("artifact_path_exists", str(path)) from exc
        else:
            os.replace(temp, path)
    finally:
        try:
            os.unlink(temp)
        except FileNotFoundError:
            pass


def _canonical_digest(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------- markdown model

def _unfenced(lines: list[str]) -> Iterator[tuple[int, str]]:
    fenced = False
    for index, raw in enumerate(lines):
        text = raw.rstrip("\r\n")
        if FENCE.match(text):
            fenced = not fenced
            continue
        if not fenced:
            yield index, text


def _headings(lines: list[str]) -> list[dict[str, Any]]:
    found = []
    for index, text in _unfenced(lines):
        match = HEADING.match(text)
        if match:
            found.append({"level": len(match.group(1)), "title": match.group(2), "line": index})
    stack: list[dict[str, Any]] = []
    for pos, head in enumerate(found):
        head["own_end"] = found[pos + 1]["line"] if pos + 1 < len(found) else len(lines)
        head["end"] = next((other["line"] for other in found[pos + 1:] if other["level"] <= head["level"]), len(lines))
        while stack and stack[-1]["level"] >= head["level"]:
            stack.pop()
        head["ancestors"] = [item["title"] for item in stack]
        head["path"] = [item["title"] for item in stack if item["level"] > 1]
        stack.append(head)
    return found


def _own_text(lines: list[str], head: dict[str, Any]) -> str:
    return "".join(lines[head["line"] + 1:head["own_end"]])


def _placeholder_mask(tokens: list[str]) -> re.Pattern[str]:
    """The contract token `<` opens a `<...>` span; a bare `<` (`p95 < 300ms`) is prose, not a placeholder."""
    return re.compile("|".join(r"<[^<>\n]*>" if token == "<" else re.escape(token) for token in tokens))


def _substantive(text: str, template: str, mask: re.Pattern[str]) -> bool:
    """template-contract `placeholder_only_section`: a section stays unfilled only while every line is still a
    template line or nothing but placeholders, both compared with each placeholder masked."""
    def shape(line: str) -> str:
        # Adjacent placeholders (`<a> <b>`) are still one unfilled slot.
        return re.sub(r"\0[\s\0]*\0", "\0", mask.sub("\0", line.strip()))

    scaffold = {shape(line) for line in template.splitlines() if line.strip()}
    for line in text.splitlines():
        if not line.strip():
            continue
        masked = shape(line)
        if masked not in scaffold and re.sub(r"[\0\s|`]", "", LIST_MARK.sub("", masked, count=1)):
            return True
    return False


def _section_text(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise WriterError("invalid_input", f"{label} must be a string")
    if SECRET.search(value):
        raise WriterError("secret_like_content", label)
    # Check the text the way it is read back (splitlines), not the way it is written ("\n").
    rows = value.splitlines()
    if sum(1 for row in rows if FENCE.match(row)) % 2:
        raise WriterError("section_unbalanced_fence", f"{label}: an open code fence would hide every later heading")
    if any(HEADING.match(text) for _, text in _unfenced(rows)):
        raise WriterError("section_contains_heading", f"{label}: section text must not contain markdown headings")
    return value.strip("\n")


def _heading_key(key: Any, label: str) -> str:
    """A caller-chosen H2 title becomes document structure, so it must stay one addressable line."""
    if not isinstance(key, str) or not key.strip() or key != key.strip() or len(key) > HEADING_MAX:
        raise WriterError("invalid_section_key", f"{label}: section keys are trimmed non-empty strings of at most {HEADING_MAX} chars")
    if LINE_BREAK.search(key) or key.startswith("#") or " > " in key:
        raise WriterError("invalid_section_key", f"{label}: {key!r} must be one line without a leading '#' or ' > '")
    if SECRET.search(key):
        raise WriterError("secret_like_content", f"{label}: section key")
    if READINESS_ITEM.match(key):
        raise WriterError("readiness_item_is_not_a_heading",
                          f"{label}: {key!r} is a readiness item; fill it with the via/key its readiness_fill entry names")
    return key


def _line_item(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or LINE_BREAK.search(value):
        raise WriterError("invalid_input", f"{label} must be a non-empty single-line string")
    if SECRET.search(value):
        raise WriterError("secret_like_content", label)
    return value.strip()


def _apply_edits(lines: list[str], edits: list[tuple[int, int, list[str]]], label: str) -> list[str]:
    """Splice (start, end, replacement) edits in document order; inserts at one point keep request order."""
    out: list[str] = []
    cursor = 0
    for _, (start, end, replacement) in sorted(enumerate(edits), key=lambda pair: (pair[1][0], pair[0])):
        if start < cursor:
            raise WriterError("overlapping_edits", f"{label}: section edits overlap")
        out += lines[cursor:start] + replacement
        cursor = end
    return out + lines[cursor:]


def _block(level: int, title: str, text: str) -> list[str]:
    out = [f"{'#' * level} {title}\n", "\n"]
    if text.strip():
        out += [line + "\n" for line in text.split("\n")]
        out.append("\n")
    return out


def _template(root: Path, name: str) -> tuple[list[tuple[int, str, str]], str]:
    """Prefer the init-scaffolded editable copy; fall back to the plugin canonical template."""
    local = root / ".dev-graph" / "templates" / name
    if local.is_file() and not local.is_symlink():
        path, source = contained(local, root), "repository"
    else:
        path, source = PLUGIN_ROOT / "templates" / name, "plugin"
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    return [(head["level"], head["title"], _own_text(lines, head).strip("\n")) for head in _headings(lines)], source


def _overlay_leaves(sections: list[tuple[int, str, str]]) -> list[tuple[str, str]]:
    return [(title, own) for level, title, own in sections if level == 2]


# ---------------------------------------------------------------- composition

class Composer:
    def __init__(self, root: Path, contract: dict[str, Any]) -> None:
        self.root, self.contract = root, contract
        self.mask = _placeholder_mask(list(contract["placeholder_tokens"]))
        self.sources: set[str] = set()

    def _load(self, name: str) -> list[tuple[int, str, str]]:
        sections, source = _template(self.root, name)
        self.sources.add(f"{source}:{name}")
        return sections

    def subtype_title(self, subtype: str) -> str:
        sections = self._load(self.contract["artifacts"]["architecture"]["subtype_templates"][subtype])
        return next(title for level, title, _ in sections if level == 1)

    def subtype_block(self, subtype: str, inputs: dict[str, Any]) -> list[str]:
        sections = self._load(self.contract["artifacts"]["architecture"]["subtype_templates"][subtype])
        title = self.subtype_title(subtype)
        leaves = _overlay_leaves(sections)
        unknown = sorted(set(inputs) - {leaf for leaf, _ in leaves})
        if unknown:
            raise WriterError("unknown_section", f"subtype {subtype} has no sections {unknown}")
        out = _block(3, title, "")
        for leaf, default in leaves:
            out += _block(4, leaf, _section_text(inputs[leaf], f"{subtype}:{leaf}") if leaf in inputs else default)
        return out

    def api_block(self, contract_input: Any) -> list[str]:
        if not isinstance(contract_input, dict) or set(contract_input) - {"operation", "sections"}:
            raise WriterError("invalid_input", "api_contracts[] items are {operation, sections}")
        operation = contract_input.get("operation")
        if not isinstance(operation, str) or not OPERATION.match(operation):
            raise WriterError("invalid_input", f"api operation must match {OPERATION.pattern}")
        inputs = contract_input.get("sections") or {}
        if not isinstance(inputs, dict):
            raise WriterError("invalid_input", "api_contracts[].sections must be an object")
        leaves = _overlay_leaves(self._load(self.contract["artifacts"]["specification"]["conditional_templates"]["api_changed"]))
        unknown = sorted(set(inputs) - {leaf for leaf, _ in leaves})
        if unknown:
            raise WriterError("unknown_section", f"api {operation} has no sections {unknown}")
        out = _block(3, f"API: {operation}", "")
        for leaf, default in leaves:
            out += _block(4, leaf, _section_text(inputs[leaf], f"api:{operation}:{leaf}") if leaf in inputs else default)
        return out

    def generated(self, kind: str, name: str, state: dict[str, Any]) -> str | None:
        """Section text derived from node state; update regenerates it when that state changes."""
        if kind == "architecture" and name == "Subtype architecture":
            rows = []
            for subtype in ARCH_SUBTYPES:
                template = self.contract["artifacts"]["architecture"]["subtype_templates"][subtype]
                label = subtype.capitalize()
                rows.append(f"- {label}: 合成済み (`{template}`)" if subtype in state["subtypes"] else f"- {label}: N/A: subtype 非選択")
            return "合成対象の subtype と該当テンプレート:\n\n" + "\n".join(rows)
        if kind == "specification" and name == "API契約" and state["api_count"]:
            return "API を公開・変更する。endpoint ごとの契約を以下に合成する (`api-contract.md`)。"
        if kind == "feature":
            return _feature_text(name, state["node"])
        return None

    def expected(self, kind: str, name: str, state: dict[str, Any]) -> str:
        """What a writer-composed section holds for this state: generated text, else the template default."""
        text = self.generated(kind, name, state)
        if text is not None:
            return text
        sections = self._load(self.contract["artifacts"][kind]["template"])
        return next((own for _, title, own in sections if title == name), "")

    def compose(self, kind: str, state: dict[str, Any], sections: dict[str, Any],
                subtype_sections: dict[str, Any], api_contracts: list[Any]) -> list[str]:
        spec = self.contract["artifacts"][kind]
        levels = {title: level for level, title, _ in self._load(spec["template"])}
        required = list(spec["required_sections"])
        if kind == "feature" and set(sections) & set(MACRO_SECTIONS):
            raise WriterError("macro_section_is_projection",
                              f"{sorted(set(sections) & set(MACRO_SECTIONS))} are rendered from macro/depends_on; pass the values there")
        out: list[str] = []
        for index, name in enumerate(required):
            level = levels.get(name, 1 if index == 0 else 2)
            text = _section_text(sections[name], name) if name in sections else self.expected(kind, name, state)
            out += _block(level, name, text)
            if kind == "architecture" and name == "Subtype architecture":
                for subtype in [item for item in ARCH_SUBTYPES if item in state["subtypes"]]:
                    out += self.subtype_block(subtype, subtype_sections.get(subtype) or {})
            if kind == "specification" and name == "API契約":
                for item in api_contracts:
                    out += self.api_block(item)
        for name in [key for key in sections if key not in required]:
            out += _block(2, _heading_key(name, "sections"), _section_text(sections[name], name))
        return out

    def readiness(self, kind: str, subtypes: list[str], lines: list[str]) -> list[dict[str, Any]]:
        """Missing sections as {item, via, key}: the update input that fills each one, so callers never
        translate readiness names into heading paths. via=None means no writer path (a heading removed by hand)."""
        heads = _headings(lines)
        missing: dict[str, dict[str, Any]] = {}

        def need(item: str, via: str | None, key: str | None) -> None:
            missing.setdefault(item, {"item": item, "via": via, "key": key})

        top: dict[str, dict[str, Any]] = {}
        for head in heads:
            if head["level"] <= 2:
                top.setdefault(head["title"], head)
        spec = self.contract["artifacts"][kind]
        defaults = {title: own for _, title, own in self._load(spec["template"])}
        for name in spec["required_sections"]:
            head = top.get(name)
            # A feature projection is filled at its source field, never as section text.
            projection = MACRO_FILL.get(name) if kind == "feature" else None
            if head is None:
                need(name, *(projection or ("append_sections", name)))
            elif not _substantive(_own_text(lines, head), defaults.get(name, ""), self.mask):
                need(name, *(projection or ("set_sections", name)))

        def leaves_under(block: dict[str, Any], leaves: list[tuple[str, str]], prefix: str) -> None:
            children = {head["title"]: head for head in heads
                        if head["level"] == 4 and block["line"] < head["line"] < block["end"]}
            for leaf, default in leaves:
                if leaf not in children:
                    need(f"{prefix}:{leaf}", None, None)
                elif not _substantive(_own_text(lines, children[leaf]), default, self.mask):
                    need(f"{prefix}:{leaf}", "set_sections", f"{block['title']} > {leaf}")

        if kind == "architecture":
            for subtype in [item for item in ARCH_SUBTYPES if item in subtypes]:
                sections = self._load(self.contract["artifacts"]["architecture"]["subtype_templates"][subtype])
                title = next(title for level, title, _ in sections if level == 1)
                block = next((head for head in heads if head["level"] == 3 and head["title"] == title), None)
                if block is None:
                    need(f"{subtype}:{title}", None, None)
                else:
                    leaves_under(block, _overlay_leaves(sections), subtype)
        if kind == "specification" and "api" in subtypes:
            leaves = _overlay_leaves(self._load(self.contract["artifacts"]["specification"]["conditional_templates"]["api_changed"]))
            blocks = [head for head in heads if head["level"] == 3 and head["title"].startswith("API: ") and "API契約" in head["ancestors"]]
            if not blocks:
                need("api-contract", "add_api_contracts", None)
            for block in blocks:
                leaves_under(block, leaves, f"api:{block['title'][5:]}")
        return list(missing.values())


LINE_BREAKERS = {"\x85": "\\u0085", "\u2028": "\\u2028", "\u2029": "\\u2029"}


def _frontmatter(node: dict[str, Any], keys: list[str], unmanaged: list[str] | None = None) -> str:
    # One JSON value per line: escape the code points str.splitlines() treats as line ends.
    rows = []
    for key in keys:
        # sort_keys matches graph.json, so an update re-serialising a node read back from the graph moves no keys.
        value = json.dumps(node[key], ensure_ascii=False, sort_keys=True)
        for raw, escaped in LINE_BREAKERS.items():
            value = value.replace(raw, escaped)
        rows.append(f"{key}: {value}\n")
    return "---\n" + "".join(rows) + "".join(unmanaged or []) + "---\n"


def _split_frontmatter(text: str, label: str) -> tuple[list[str], list[str]]:
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise WriterError("frontmatter_invalid", f"{label} has no frontmatter")
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return lines[1:index], lines[index + 1:]
    raise WriterError("frontmatter_invalid", f"{label} frontmatter is not terminated")


def _unmanaged_frontmatter(front: list[str], keys: list[str]) -> list[str]:
    """Raw lines (with continuations) of keys outside the contract; update keeps them verbatim."""
    kept: list[str] = []
    keep = False
    for line in front:
        match = FRONT_KEY.match(line)
        if match:
            keep = match.group(1) not in keys
        if keep:
            kept.append(line if line.endswith(("\n", "\r")) else line + "\n")
    return kept


def _feature_text(name: str, node: dict[str, Any]) -> str | None:
    """feature body projected from frontmatter, so body and graph cannot drift apart."""
    if name == "目的":
        return node["purpose"]
    if name == "到達状態":
        return node["goal"]
    if name == "スコープ":
        return "\n".join([*(f"- スコープ内: {item}" for item in node["scope_in"]),
                          *(f"- スコープ外: {item}" for item in node["scope_out"])])
    if name == "受入":
        return "\n".join(f"- [ ] {item}" for item in node["acceptance"])
    if name == "アーキテクチャ参照":
        return "\n".join(f"- `{item}`" for item in node["architecture_refs"])
    if name == "機能間依存":
        depends = node.get("depends_on") or []
        return "\n".join(f"- `{item}`" for item in depends) if depends else "- 先行 feature なし (`depends_on` は空)"
    if name == "Handoff":
        return ("- per-feature planning: ready 時に run-system-dev-plan を自動起動するか、手動 `/system-dev-plan` の結果を同じ登録経路で受理する\n"
                "- 生成物: P01..P13 の exact 13 executable task specs と 13-node intra-feature DAG\n"
                f"- 登録先: `register-package.py register` が parent_feature=`{node['graph_node_id']}` で 13 件を atomic 登録する (expected/applied=13)\n"
                "- 完了rollup: exact 13 全 done かつ P07/P10/P11 の evidence が受入を満たす場合だけ done")
    return None


# ---------------------------------------------------------------- input rules

def _reject_feature(kind: Any) -> None:
    if kind == "feature":
        raise WriterError("feature_requires_c14_macro_contract",
                          "feature nodes are declared by the C14 macro contract (add with artifact_kind=feature and macro{...}); R1/R2 routing never yields them")


def _macro(raw: Any, label: str, *, partial: bool) -> dict[str, Any]:
    """C14 macro contract: purpose/goal text and non-empty unique single-line lists (graph-node schema allOf[3])."""
    keys = set(MACRO_TEXT_KEYS) | set(MACRO_LIST_KEYS)
    if not isinstance(raw, dict) or set(raw) - keys or (not partial and set(raw) != keys) or not raw:
        raise WriterError("invalid_macro", f"{label}: macro is {{{', '.join(sorted(keys))}}}" + (" (any subset)" if partial else ""))
    macro: dict[str, Any] = {}
    for key in MACRO_TEXT_KEYS:
        if key in raw:
            text = _section_text(raw[key], f"{label}.macro.{key}").strip()
            if not text:
                raise WriterError("invalid_macro", f"{label}.macro.{key} must be non-empty")
            macro[key] = text
    for key in MACRO_LIST_KEYS:
        if key in raw:
            items = raw[key]
            if not isinstance(items, list) or not items:
                raise WriterError("invalid_macro", f"{label}.macro.{key} must be a non-empty list")
            values = [_line_item(item, f"{label}.macro.{key}[]") for item in items]
            if len(set(values)) != len(values):
                raise WriterError("invalid_macro", f"{label}.macro.{key} has duplicates")
            macro[key] = values
    return macro


def _macro_edges(node: dict[str, Any], kinds: dict[Any, Any], label: str) -> None:
    """Macro layer purity: architecture_refs name architecture nodes, depends_on names features only."""
    for ref in node["architecture_refs"]:
        if kinds.get(ref) != "architecture":
            raise WriterError("invalid_macro_reference", f"{label}: architecture_refs {ref!r} is not an architecture node")
    for dep in node.get("depends_on") or []:
        if kinds.get(dep) != "feature":
            raise WriterError("invalid_macro_reference", f"{label}: feature depends_on {dep!r} is not a feature node")


def _check_keys(entry: dict[str, Any], allowed: set[str], label: str) -> None:
    extra = set(entry) - allowed
    if extra & PACKAGE_KEYS:
        raise WriterError("package_member_requires_register_package",
                          f"{label}: {sorted(extra & PACKAGE_KEYS)} belong to exact-13 packages; use register-package.py register")
    if extra:
        raise WriterError("writer_owned_or_unknown_field", f"{label}: {sorted(extra)} cannot be supplied")


def _subtypes(kind: str, raw: Any, api_count: int) -> list[str]:
    if not isinstance(raw, list) or any(item not in SUBTYPE_ORDER for item in raw) or len(set(raw)) != len(raw):
        raise WriterError("invalid_subtypes", f"artifact_subtypes must be unique values of {SUBTYPE_ORDER}")
    chosen = [item for item in SUBTYPE_ORDER if item in raw]
    if kind == "architecture" and (not chosen or "api" in chosen):
        raise WriterError("invalid_subtypes", "architecture needs one or more of frontend/backend/infrastructure/data/security")
    if kind == "specification" and (set(chosen) - {"api"} or ("api" in chosen and not api_count)):
        raise WriterError("invalid_subtypes", "specification subtype is only api, and api needs api_contracts")
    if kind == "specification" and api_count and "api" not in chosen:
        chosen.append("api")  # same rule as update/add_api_contracts: contracts imply the api subtype
    if kind not in {"architecture", "specification"} and chosen:
        raise WriterError("invalid_subtypes", f"{kind} has no subtypes")
    return chosen


def _declared(kind: str, file_path: str, reason: str) -> dict[str, Any]:
    """C14 declares the macro layer (features and the architecture they cite); routing confidence does not apply."""
    return {"confidence": 1.0, "margin": 1.0, "decision": "c14_macro_contract", "reason": reason,
            "candidates": [{"artifact_kind": kind, "confidence": 1.0, "candidate_path": file_path}]}


def _classification(raw: Any, kind: str, slug: str) -> dict[str, Any]:
    if not isinstance(raw, dict) or set(raw) - {"reason", "candidates", "decision"}:
        raise WriterError("invalid_classification", "classification is {reason, candidates, decision}")
    reason, candidates, decision = raw.get("reason"), raw.get("candidates"), raw.get("decision")
    if not isinstance(reason, str) or not reason.strip():
        raise WriterError("invalid_classification", "classification.reason is required")
    if decision == "c14_macro_contract":
        if kind != "architecture" or "candidates" in raw:
            raise WriterError("invalid_classification",
                              "decision=c14_macro_contract is {reason, decision} on an architecture a same-batch feature cites")
        return _declared(kind, f"{VGS.ROOT_BY_KIND[kind]}/{slug}.md", reason.strip())
    if not isinstance(candidates, list) or not candidates:
        raise WriterError("invalid_classification", "classification.candidates must be a non-empty list")
    scores: dict[str, float] = {}
    for item in candidates:
        if not isinstance(item, dict) or set(item) != {"artifact_kind", "confidence"}:
            raise WriterError("invalid_classification", "candidates[] items are {artifact_kind, confidence}")
        _reject_feature(item["artifact_kind"])
        if item["artifact_kind"] not in ROUTABLE_KINDS or item["artifact_kind"] in scores:
            raise WriterError("invalid_classification", f"candidate kind invalid or duplicated: {item['artifact_kind']}")
        value = item["confidence"]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
            raise WriterError("invalid_classification", "candidate confidence must be within 0..1")
        scores[item["artifact_kind"]] = float(value)
    if kind not in scores:
        raise WriterError("invalid_classification", f"artifact_kind {kind} is not among the candidates")
    ranked = sorted(scores.items(), key=lambda pair: (-pair[1], pair[0]))
    confidence = scores[kind]
    margin = round(confidence - max((score for other, score in scores.items() if other != kind), default=0.0), 6)
    automatic = ranked[0][0] == kind and confidence >= AUTO_CONFIDENCE and margin >= AUTO_MARGIN
    decision = decision or ("auto" if automatic else None)
    if decision not in {"auto", "user_confirmed"}:
        raise WriterError("classification_requires_user_confirmation",
                          f"confidence={confidence} margin={margin} is below auto thresholds; confirm via R2 and pass decision=user_confirmed")
    if decision == "auto" and not automatic:
        raise WriterError("classification_requires_user_confirmation",
                          f"decision=auto needs top candidate, confidence>={AUTO_CONFIDENCE} and margin>={AUTO_MARGIN} (got {confidence}/{margin})")
    return {
        "confidence": confidence, "margin": margin, "decision": decision, "reason": reason.strip(),
        "candidates": [{"artifact_kind": other, "confidence": score,
                        "candidate_path": f"{VGS.ROOT_BY_KIND[other]}/{slug}.md"} for other, score in ranked],
    }


def _tracker(raw: Any, mode: Any) -> str:
    """register-package._resolve_binding's rule: none always; beads/github only where the repo tracker mode allows."""
    if raw == "repo-config-default":
        binding = TRACKER_FROM_CONFIG.get(mode)
        if binding is None:
            raise WriterError("tracker_binding_unresolved",
                              f"repo-config-default cannot resolve tracker mode {mode!r}; mode both needs an explicit beads/github/none")
    elif raw in {"beads", "github", "none"}:
        if raw != "none" and mode not in {raw, "both"}:
            raise WriterError("tracker_binding_not_allowed", f"binding intent {raw} is not allowed by tracker mode {mode!r}")
        binding = raw
    else:
        raise WriterError("tracker_binding_unresolved", "tracker_binding must be beads/github/none or repo-config-default")
    if binding == "github":
        # schema allOf[14]+[9]: github binding needs an issue publication mode, which only confirmed/pass/complete
        # issue|task nodes may carry. A writer that creates drafts cannot satisfy it, so it refuses up front.
        raise WriterError("github_binding_requires_confirmed_node",
                          "register the draft with tracker_binding=none; GitHub publication happens after confirm/pass through C12 (gh-bridge), not this writer")
    return binding


# ---------------------------------------------------------------- operations

def _plan_add(payload: dict[str, Any], nodes: list[dict[str, Any]], root: Path, ctx: dict[str, Any],
              composer: Composer, now: str) -> list[dict[str, Any]]:
    entries = payload.get("artifacts")
    if not isinstance(entries, list) or not entries or not all(isinstance(item, dict) for item in entries):
        raise WriterError("invalid_input", "add input needs artifacts[] objects")
    keys = list(composer.contract["common_frontmatter"]["required"])
    config_path = Path(ctx["local_state_paths"]["config"])
    mode = ((load_json(config_path) if config_path.is_file() else {}).get("execution_tracker") or {}).get("mode")
    taken_ids = {node.get("graph_node_id") for node in nodes}
    taken_paths = {node.get("file_path") for node in nodes}
    plan = []
    for index, entry in enumerate(entries):
        label = f"artifacts[{index}]"
        kind = entry.get("artifact_kind")
        _check_keys(entry, ADD_KEYS, label)
        if kind == "feature" and "macro" not in entry:
            _reject_feature(kind)
        if kind not in KIND_PREFIX:
            raise WriterError("invalid_kind", f"{label}: artifact_kind must be one of {sorted(KIND_PREFIX)}")
        if kind != "feature" and "macro" in entry:
            raise WriterError("invalid_input", f"{label}: macro is the C14 contract of feature nodes only")
        if kind == "feature" and "classification" in entry:
            raise WriterError("invalid_input", f"{label}: features are declared by C14, not classified; drop classification")
        slug = entry.get("slug")
        if not isinstance(slug, str) or not SLUG.match(slug):
            raise WriterError("invalid_slug", f"{label}: slug must match {SLUG.pattern}")
        graph_node_id, file_path = f"{KIND_PREFIX[kind]}-{slug}", f"{VGS.ROOT_BY_KIND[kind]}/{slug}.md"
        if graph_node_id in taken_ids or file_path in taken_paths:
            raise WriterError("duplicate_node", f"{label}: {graph_node_id} or {file_path} already exists")
        target = contained(_content_root(ctx, root, kind) / f"{slug}.md", root, must_exist=False)
        if target.exists() or target.is_symlink():
            raise WriterError("artifact_path_exists", f"{label}: {file_path} exists outside the graph")
        sections = entry.get("sections") or {}
        subtype_sections = entry.get("subtype_sections") or {}
        api_contracts = entry.get("api_contracts") or []
        if not isinstance(sections, dict) or not isinstance(subtype_sections, dict) or not isinstance(api_contracts, list):
            raise WriterError("invalid_input", f"{label}: sections/subtype_sections are objects and api_contracts is a list")
        subtypes = _subtypes(kind, entry.get("artifact_subtypes", []), len(api_contracts))
        if kind != "architecture" and subtype_sections or set(subtype_sections) - set(subtypes):
            raise WriterError("invalid_input", f"{label}: subtype_sections must target selected architecture subtypes")
        if kind != "specification" and api_contracts:
            raise WriterError("invalid_input", f"{label}: api_contracts apply to specification only")
        operations = [item.get("operation") for item in api_contracts if isinstance(item, dict)]
        if len(set(operations)) != len(operations):
            raise WriterError("duplicate_section", f"{label}: api_contracts repeat an operation")
        if kind == "feature":
            macro = _macro(entry.get("macro"), label, partial=False)
            classified = _declared(kind, file_path, "declared by the C14 macro contract (run-dev-graph-decompose)")
        else:
            macro = {"purpose": None, "goal": None, "scope_in": [], "scope_out": [], "acceptance": [], "architecture_refs": []}
            classified = _classification(entry.get("classification"), kind, slug)
        for field in ("title", "project_id", "domain"):
            if not isinstance(entry.get(field), str) or not entry[field].strip():
                raise WriterError("missing_required_field", f"{label}.{field} must be a non-empty string")
            if SECRET.search(entry[field]):
                raise WriterError("secret_like_content", f"{label}.{field}")
        node = {
            "graph_node_id": graph_node_id, "artifact_kind": kind, "artifact_subtypes": subtypes,
            "title": entry.get("title"), "project_id": entry.get("project_id"), "domain": entry.get("domain"),
            "status": "draft", "owners": entry.get("owners", []), "tags": entry.get("tags", []),
            "priority": entry.get("priority"), "start_date": entry.get("start_date"),
            "target_date": entry.get("target_date"), "iteration": entry.get("iteration"),
            "created_at": now, "updated_at": now, "depends_on": entry.get("depends_on", []),
            "related_nodes": entry.get("related_nodes", []), "resource_scope": entry.get("resource_scope", []),
            **macro,
            "parent_feature": None, "feature_package_id": None, "phase_ref": None,
            "file_path": file_path, "template_id": kind, "template_version": composer.contract["template_version"],
            "confirmation_status": "draft", "evaluation_status": "pending",
            "confirmation_evidence": {"evaluator": None, "evidence_ref": None, "evaluated_digest": None},
            "source_lineage": entry.get("source_lineage") or {
                "origin_kind": "generated" if kind == "feature" else "manual",
                "source_plugin": "dev-graph" if kind == "feature" else None, "source_path": None,
                "source_version": None, "source_digest": None, "imported_at": None},
            "classification_confidence": classified["confidence"], "classification_reason": classified["reason"],
            "classification_candidates": classified["candidates"],
            "github_publication": {"mode": "local_only", "project_aliases": [], "labels": [], "milestone": None},
            "issue_linkage": None, "tracker_binding": _tracker(entry.get("tracker_binding"), mode), "beads_linkage": None,
            "github_project_linkages": [], "pull_request_linkages": [], "execution_contexts": [],
            "completion_evidence": {"policy": "manual", "status": "not_applicable", "source": None,
                                    "completed_at": None, "reconciled_at": None, "evidence_refs": []},
        }
        state = {"subtypes": subtypes, "api_count": len(api_contracts), "node": node}
        body = composer.compose(kind, state, sections, subtype_sections, api_contracts)
        fill = composer.readiness(kind, subtypes, body)
        missing = [item["item"] for item in fill]
        node["implementation_readiness"] = {"status": "incomplete" if missing else "complete",
                                            "missing_sections": missing, "checked_at": now}
        text = _frontmatter(node, keys) + "\n" + "".join(body)
        taken_ids.add(graph_node_id)
        taken_paths.add(file_path)
        detail = {"graph_node_id": graph_node_id, "file_path": file_path,
                  "classification": {key: classified[key] for key in ("decision", "confidence", "margin")},
                  "implementation_readiness": node["implementation_readiness"]["status"],
                  "missing_sections": missing, "readiness_fill": fill}
        plan.append({"node": node, "before_node": None, "path": target, "before": None, "text": text,
                     "label": label, "detail": detail, "declared": classified["decision"] == "c14_macro_contract"})
    kinds = {node.get("graph_node_id"): node.get("artifact_kind") for node in nodes}
    kinds.update({item["node"]["graph_node_id"]: item["node"]["artifact_kind"] for item in plan})
    cited = {ref for item in plan if item["node"]["artifact_kind"] == "feature" for ref in item["node"]["architecture_refs"]}
    for item in plan:
        if item["node"]["artifact_kind"] == "feature":
            _macro_edges(item["node"], kinds, item["label"])
        elif item["declared"] and item["node"]["graph_node_id"] not in cited:
            raise WriterError("invalid_classification",
                              f"{item['label']}: decision=c14_macro_contract needs a feature in the same batch whose architecture_refs cite {item['node']['graph_node_id']}")
    return plan


def _locate(heads: list[dict[str, Any]], key: str) -> dict[str, Any]:
    parts = [part.strip() for part in key.split(" > ")]
    title, ancestors = parts[-1], parts[:-1]
    matches = [head for head in heads if head["title"] == title and all(item in head["ancestors"] for item in ancestors)]
    if len(matches) > 1:
        # A key that spells the whole path below the H1 is exact: `認証・認可` is the H2 even where an API block repeats it as a leaf.
        matches = [head for head in matches if head["path"] == ancestors] or matches
    if len(matches) != 1:
        code = "section_not_found" if not matches else "section_ambiguous"
        raise WriterError(code, f"{key} (qualify with 'Ancestor > Heading' when ambiguous)")
    return matches[0]


def _tail(lines: list[str]) -> list[str]:
    """Blank lines that separate a block added at the end of the document from what precedes it."""
    if lines and not lines[-1].endswith("\n"):
        return ["\n", "\n"]
    return [] if not lines or lines[-1].strip() == "" else ["\n"]


def _body_lines(text: str) -> list[str]:
    return ["\n", *[line + "\n" for line in text.split("\n")], "\n"] if text.strip() else ["\n"]


def _plan_update(payload: dict[str, Any], nodes: list[dict[str, Any]], root: Path, ctx: dict[str, Any],
                 composer: Composer, now: str) -> list[dict[str, Any]]:
    entries = payload.get("updates")
    if not isinstance(entries, list) or not entries or not all(isinstance(item, dict) for item in entries):
        raise WriterError("invalid_input", "update input needs updates[] objects")
    keys = list(composer.contract["common_frontmatter"]["required"])
    by_id = {node.get("graph_node_id"): node for node in nodes}
    kinds = {node_id: node.get("artifact_kind") for node_id, node in by_id.items()}
    seen: set[str] = set()
    plan = []
    for index, entry in enumerate(entries):
        label = f"updates[{index}]"
        _check_keys(entry, UPDATE_KEYS, label)
        graph_node_id = entry.get("graph_node_id")
        if graph_node_id not in by_id or graph_node_id in seen:
            raise WriterError("unknown_node", f"{label}: {graph_node_id!r} is absent or repeated")
        seen.add(graph_node_id)
        before_node = by_id[graph_node_id]
        kind = before_node.get("artifact_kind")
        if kind not in KIND_PREFIX:
            raise WriterError("invalid_kind", f"{label}: {graph_node_id} has unsupported artifact_kind {kind!r}")
        if any(before_node.get(key) is not None for key in PACKAGE_KEYS):
            raise WriterError("package_member_requires_register_package", f"{label}: exact-13 package members are owned by system-dev-planner")
        node = copy.deepcopy(before_node)
        patch = entry.get("node_patch") or {}
        if not isinstance(patch, dict):
            raise WriterError("invalid_input", f"{label}.node_patch must be an object")
        immutable = set(patch) - PATCH_KEYS
        if immutable:
            raise WriterError("writer_owned_or_unknown_field", f"{label}.node_patch cannot change {sorted(immutable)}")
        for field, value in patch.items():
            if isinstance(value, str) and SECRET.search(value):
                raise WriterError("secret_like_content", f"{label}.node_patch.{field}")
            node[field] = value
        if patch.get("status") in {"closed", "tombstoned"} and before_node.get("status") != patch["status"]:
            node["closed_at"] = now
        macro_patch = entry.get("macro_patch")
        if macro_patch is not None:
            if kind != "feature":
                raise WriterError("invalid_input", f"{label}: macro_patch applies to feature nodes only")
            node.update(_macro(macro_patch, label, partial=True))
        if kind == "feature":
            _macro_edges(node, kinds, label)
        target = contained(root / str(before_node.get("file_path")), root, must_exist=True)
        _content_root(ctx, root, kind)
        before_bytes = target.read_bytes()
        frontmatter = VGS.frontmatter_of(target)
        if frontmatter.get("graph_node_id") != graph_node_id or frontmatter.get("file_path") != before_node.get("file_path"):
            raise WriterError("artifact_parity_error", f"{label}: frontmatter identity differs from the graph node")
        front, lines = _split_frontmatter(before_bytes.decode("utf-8"), str(before_node.get("file_path")))
        heads = _headings(lines)
        top = [head for head in heads if head["level"] <= 2]
        edits: list[tuple[int, int, list[str]]] = []
        replaced, appended, regenerated = [], [], []
        explicit: set[int] = set()
        set_sections = entry.get("set_sections") or {}
        append_sections = entry.get("append_sections") or {}
        if not isinstance(set_sections, dict) or not isinstance(append_sections, dict):
            raise WriterError("invalid_input", f"{label}: set_sections/append_sections must be objects")
        for key, value in set_sections.items():
            head = _locate(heads, key)
            if kind == "feature" and head["level"] <= 2 and head["title"] in MACRO_SECTIONS:
                raise WriterError("macro_section_is_projection", f"{label}: {key} is rendered from macro/depends_on; use macro_patch or node_patch")
            if head["line"] in explicit:
                raise WriterError("overlapping_edits", f"{label}: {key} names a section that is already being replaced")
            explicit.add(head["line"])
            edits.append((head["line"] + 1, head["own_end"], _body_lines(_section_text(value, key))))
            replaced.append(key)
        subtypes = list(node.get("artifact_subtypes") or [])
        add_subtypes = entry.get("add_subtypes") or []
        subtype_sections = entry.get("subtype_sections") or {}
        if not isinstance(add_subtypes, list) or not isinstance(subtype_sections, dict) or set(subtype_sections) - set(add_subtypes):
            raise WriterError("invalid_input", f"{label}: subtype_sections must target add_subtypes")
        for subtype in add_subtypes:
            if kind != "architecture" or subtype in subtypes or subtype not in ARCH_SUBTYPES:
                raise WriterError("invalid_subtypes", f"{label}: cannot add subtype {subtype!r} to {kind} (specification api comes from add_api_contracts; subtypes are never removed)")
            subtypes.append(subtype)
        if kind == "architecture" and add_subtypes:
            anchor = _locate(top, "Subtype architecture")
            by_title = {composer.subtype_title(subtype): subtype for subtype in ARCH_SUBTYPES}
            blocks = [(head["line"], by_title[head["title"]]) for head in heads
                      if head["level"] == 3 and anchor["line"] < head["line"] < anchor["end"] and head["title"] in by_title]
            for subtype in [item for item in ARCH_SUBTYPES if item in add_subtypes]:
                # Canonical SUBTYPE_ORDER position: before the first existing block that ranks after it.
                rank = SUBTYPE_ORDER.index(subtype)
                at = next((line for line, other in blocks if SUBTYPE_ORDER.index(other) > rank), anchor["end"])
                edits.append((at, at, composer.subtype_block(subtype, subtype_sections.get(subtype) or {})))
        api_contracts = entry.get("add_api_contracts") or []
        if not isinstance(api_contracts, list) or api_contracts and kind != "specification":
            raise WriterError("invalid_input", f"{label}: add_api_contracts apply to specification only")
        existing_api = [head for head in heads
                        if head["level"] == 3 and head["title"].startswith("API: ") and "API契約" in head["ancestors"]]
        if api_contracts:
            operations = [f"API: {item.get('operation')}" for item in api_contracts if isinstance(item, dict)]
            clash = set(operations) & {head["title"] for head in existing_api}
            if clash or len(set(operations)) != len(operations):
                raise WriterError("duplicate_section", f"{label}: API operations repeat or already exist: {sorted(clash) or operations}")
            anchor = _locate(top, "API契約")
            edits.append((anchor["end"], anchor["end"], [line for item in api_contracts for line in composer.api_block(item)]))
            if "api" not in subtypes:
                subtypes.append("api")
        node["artifact_subtypes"] = [item for item in SUBTYPE_ORDER if item in subtypes]
        before_state = {"subtypes": list(before_node.get("artifact_subtypes") or []),
                        "api_count": len(existing_api), "node": before_node}
        after_state = {"subtypes": node["artifact_subtypes"],
                       "api_count": len(existing_api) + len(api_contracts), "node": node}
        required = list(composer.contract["artifacts"][kind]["required_sections"])
        for index, name in enumerate(required):
            old, new = composer.expected(kind, name, before_state), composer.expected(kind, name, after_state)
            if kind == "feature" and name in MACRO_SECTIONS:
                # A projection always mirrors its frontmatter, so update re-renders it even when the fields
                # did not move: a hand edit or a removed heading is put back, never left to block readiness.
                head = next((item for item in top if item["title"] == name), None)
                if head is None:
                    levels = {title: level for level, title, _ in composer._load(composer.contract["artifacts"][kind]["template"])}
                    after = next((item["line"] for later in required[index + 1:] for item in top if item["title"] == later), None)
                    block = _block(levels.get(name, 2), name, new)
                    edits.append((after, after, block) if after is not None else (len(lines), len(lines), _tail(lines) + block))
                elif _own_text(lines, head).strip("\n") != new.strip("\n"):
                    edits.append((head["line"] + 1, head["own_end"], _body_lines(new)))
                else:
                    continue
                regenerated.append(name)
                continue
            if old == new:
                continue
            head = _locate(top, name)
            if head["line"] in explicit:
                continue
            # Other generated text is regenerated only while it still equals what the writer composed, never over a hand edit.
            if kind != "feature" and _own_text(lines, head).strip("\n") != old.strip("\n"):
                raise WriterError("generated_section_diverged",
                                  f"{label}: {name} was edited by hand, so it is not regenerated; pass set_sections[{name!r}] with the new text")
            edits.append((head["line"] + 1, head["own_end"], _body_lines(new)))
            regenerated.append(name)
        titles = {head["title"] for head in top}
        for key, value in append_sections.items():
            _heading_key(key, f"{label}.append_sections")
            if kind == "feature" and key in MACRO_SECTIONS:
                raise WriterError("macro_section_is_projection", f"{label}: {key} is rendered from macro/depends_on; use macro_patch or node_patch")
            if key in titles:
                raise WriterError("duplicate_section", f"{label}: {key} exists; use set_sections to change it")
            edits.append((len(lines), len(lines), _tail(lines) + _block(2, key, _section_text(value, key))))
            appended.append(key)
        body = _apply_edits(lines, edits, label)
        fill = composer.readiness(kind, node["artifact_subtypes"], body)
        missing = [item["item"] for item in fill]
        node["implementation_readiness"] = {"status": "incomplete" if missing else "complete",
                                            "missing_sections": missing, "checked_at": now}
        unchanged_node = {**node, "updated_at": before_node.get("updated_at"),
                          "implementation_readiness": {**node["implementation_readiness"],
                                                       "checked_at": (before_node.get("implementation_readiness") or {}).get("checked_at")}}
        if body == lines and unchanged_node == before_node:
            continue
        node["updated_at"] = now
        content_fields = {key for key in node if node.get(key) != before_node.get(key)} - {
            "status", "closed_at", "updated_at", "implementation_readiness"}
        if node.get("evaluation_status") == "pass" and (body != lines or content_fields):
            node["evaluation_status"] = "stale"
        unmanaged = _unmanaged_frontmatter(front, keys)
        text = _frontmatter(node, keys, unmanaged) + "".join(body)
        plan.append({"node": node, "before_node": before_node, "path": target, "before": before_bytes, "text": text,
                     "detail": {"graph_node_id": graph_node_id, "file_path": node["file_path"],
                                "sections_replaced": replaced, "sections_appended": appended,
                                "sections_regenerated": regenerated,
                                "subtypes_added": add_subtypes,
                                "api_contracts_added": [item.get("operation") for item in api_contracts if isinstance(item, dict)],
                                "node_fields_patched": sorted(patch),
                                "macro_fields_patched": sorted(macro_patch or {}),
                                "unmanaged_frontmatter_kept": [FRONT_KEY.match(line).group(1) for line in unmanaged if FRONT_KEY.match(line)],
                                "unmanaged_body_preserved": True,
                                "implementation_readiness": node["implementation_readiness"]["status"],
                                "missing_sections": missing, "readiness_fill": fill}})
    return plan


# ---------------------------------------------------------------- transaction

def _findings(proposed: list[dict[str, Any]], baseline: list[dict[str, Any]], changed: set[str],
              staging: Path, root: Path, schema: dict[str, Any], contract: dict[str, Any]) -> list[dict[str, str]]:
    def collect(nodes: list[dict[str, Any]], staged: set[str]) -> list[dict[str, str]]:
        found = [item for index, node in enumerate(nodes) for item in VGS.schema_findings(node, schema, index)]
        found += VGS.domain_findings(nodes)
        found += VGS.artifact_findings([node for node in nodes if node.get("graph_node_id") not in staged], root, contract)
        found += VGS.artifact_findings([node for node in nodes if node.get("graph_node_id") in staged], staging, contract)
        return found

    known = {json.dumps(item, sort_keys=True) for item in collect(baseline, set())}
    return [item for item in collect(proposed, changed)
            if item["node"] in changed or json.dumps(item, sort_keys=True) not in known]


def _transact(args: argparse.Namespace, planner: Callable[..., list[dict[str, Any]]]) -> dict[str, Any]:
    ctx = _context(args.repo_root, args.config)
    root = Path(ctx["repo_root"]).resolve(strict=True)
    # A relative --input is repo-relative, like every other path the writer handles; cwd never matters.
    input_path = contained(Path(args.input) if Path(args.input).is_absolute() else root / args.input, root)
    input_bytes = input_path.read_bytes()
    payload = json.loads(input_bytes)
    if not isinstance(payload, dict):
        raise WriterError("invalid_input", "input must be a JSON object")
    graph_path = contained(Path(ctx["local_state_paths"]["graph"]), root, must_exist=False)
    if not graph_path.is_file():
        raise WriterError("graph_missing", "C24 graph is absent; run run-dev-graph-init first")
    receipts = contained(graph_path.parent / "receipts", root, must_exist=False)
    schema = load_json(VGS.SCHEMA_PATH)
    contract = load_json(VGS.TEMPLATE_CONTRACT_PATH)

    def perform() -> dict[str, Any]:
        graph_bytes = graph_path.read_bytes()
        current = json.loads(graph_bytes)
        nodes = VGS.nodes_of(current) if isinstance(current, dict) and "nodes" in current else None
        if nodes is None:
            raise WriterError("graph_invalid", "graph must be an object with nodes[]")
        revision_before = current.get("graph_revision", 0)
        if isinstance(revision_before, bool) or not isinstance(revision_before, int) or revision_before < 0:
            raise WriterError("graph_invalid", "graph_revision must be a non-negative integer")
        expected = payload.get("expected_graph_revision")
        if expected is None and not args.dry_run:
            # The CAS is what binds an apply to the preview the user saw; an apply without it could land on any revision.
            raise WriterError("missing_expected_graph_revision", "apply needs expected_graph_revision = graph_revision_before of the R2 preview")
        if expected is not None and (isinstance(expected, bool) or not isinstance(expected, int)):
            raise WriterError("invalid_input", "expected_graph_revision must be an integer")
        if expected is not None and expected != revision_before:
            raise WriterError("graph_revision_conflict", f"expected {expected}, graph is at {revision_before}")
        composer = Composer(root, contract)
        now = utc_now()
        plan = planner({key: value for key, value in payload.items() if key != "expected_graph_revision"},
                       nodes, root, ctx, composer, now)
        base = {"owner": OWNER, "operation": args.command, "repository_id": ctx["repository_id"],
                "graph_path": graph_path.relative_to(root).as_posix(), "graph_revision_before": revision_before,
                "input_sha256": _sha256(input_bytes)}
        if not plan:
            return {**base, "status": "noop", "valid": True, "dry_run": bool(args.dry_run), "idempotent": True,
                    "applied_count": 0, "write_count": 0, "graph_revision_after": revision_before}
        changed = {item["node"]["graph_node_id"] for item in plan}
        replacements = {item["node"]["graph_node_id"]: item["node"] for item in plan}
        proposed_nodes = [replacements.pop(node.get("graph_node_id"), node) for node in nodes]
        proposed_nodes += [item["node"] for item in plan if item["before_node"] is None]
        proposed = copy.deepcopy(current)
        proposed["nodes"] = proposed_nodes
        proposed["graph_revision"] = revision_before + 1
        with tempfile.TemporaryDirectory(prefix="dev-graph-node-") as staging_dir:
            staging = Path(staging_dir).resolve()
            for item in plan:
                staged = staging / item["node"]["file_path"]
                staged.parent.mkdir(parents=True, exist_ok=True)
                staged.write_text(item["text"], encoding="utf-8")
            findings = _findings(proposed_nodes, nodes, changed, staging, root, schema, contract)
        if findings:
            raise WriterError("pre_write_validation_failed", f"{len(findings)} validate-graph-schema finding(s)", findings)
        receipt_path = receipts / f"node-r{revision_before + 1:06d}-{args.command}.json"
        receipt = {
            **base, "schema_version": "1.0.0", "status": "applied", "recorded_at": now,
            "graph_revision_after": revision_before + 1, "graph_digest_after": _canonical_digest(proposed),
            "applied_count": len(plan), "node_ids": [item["node"]["graph_node_id"] for item in plan],
            "pre_write_validation": {"validator": "validate-graph-schema.py", "findings": 0},
            "template_sources": sorted(composer.sources),
            "artifacts": [{**item["detail"],
                           "sha256_before": _sha256(item["before"]) if item["before"] is not None else None,
                           "sha256_after": _sha256(item["text"].encode("utf-8"))} for item in plan],
            "receipt_path": receipt_path.relative_to(root).as_posix(),
        }
        if args.dry_run:
            return {**receipt, "status": "preview", "valid": True, "dry_run": True, "planned_count": len(plan),
                    "applied_count": 0, "write_count": 0}
        written: list[tuple[Path, bytes | None]] = []
        graph_written = False
        try:
            for item in plan:
                if item["before"] is not None and item["path"].read_bytes() != item["before"]:
                    raise WriterError("artifact_changed_during_write", item["node"]["file_path"])
                _write_atomic(item["path"], item["text"].encode("utf-8"), create_only=item["before"] is None)
                written.append((item["path"], item["before"]))
            atomic_json(graph_path, proposed)
            graph_written = True
            _create_receipt(receipt_path, receipt)
        except BaseException as exc:
            # Restore every step independently so one failed restore does not strand the others.
            restores = ([(graph_path, graph_bytes)] if graph_written else []) + list(reversed(written))
            failures = []
            for path, before in restores:
                try:
                    if before is None:
                        path.unlink(missing_ok=True)
                    else:
                        _write_atomic(path, before, create_only=False)
                except OSError as error:
                    action = "remove created file" if before is None else f"restore sha256 {_sha256(before)}"
                    failures.append({"node": path.relative_to(root).as_posix(), "code": "rollback_failed",
                                     "detail": f"{action}: {error}"})
            if failures:
                raise WriterError("rollback_incomplete", f"{type(exc).__name__}: {exc}; restore the listed paths by hand", failures) from exc
            raise
        return {**receipt, "valid": True, "dry_run": False, "write_count": len(plan) + 2}

    if args.dry_run:
        return perform()
    with _single_writer(graph_path):
        return perform()


def _create_receipt(path: Path, receipt: dict[str, Any]) -> None:
    data = (json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    try:
        _write_atomic(path, data, create_only=True)
    except WriterError as exc:
        raise WriterError("immutable_receipt_exists", str(path)) from exc


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="C02 single writer for ordinary dev-graph artifacts")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("add", "update"):
        command = sub.add_parser(name)
        command.add_argument("--repo-root", required=True)
        command.add_argument("--input", required=True, help="repo-relative or absolute JSON inside the repo: add={artifacts:[...]}, update={updates:[...]}")
        command.add_argument("--config", default=".dev-graph/config.json")
        command.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        dump(_transact(args, _plan_add if args.command == "add" else _plan_update))
        return 0
    except WriterError as exc:
        broken = exc.code == "rollback_incomplete"
        # A broken rollback leaves the listed paths written, so the write count is unknown rather than 0.
        dump({"valid": False, "status": "error" if broken else "rejected", "code": exc.code, "error": exc.detail,
              "findings": exc.findings, "applied_count": 0, "write_count": None if broken else 0})
        return 2 if broken else 1
    except (ContractError, OSError, json.JSONDecodeError, KeyError, TypeError, ValueError, UnicodeDecodeError) as exc:
        dump({"valid": False, "status": "error", "code": type(exc).__name__, "error": str(exc),
              "applied_count": 0, "write_count": 0})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
