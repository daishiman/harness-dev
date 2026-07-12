from __future__ import annotations

# /// script
# name: test-extract-system-blueprint-mermaid
# purpose: C10 mermaid-validate の必須5図・構文・usage CLI 契約を検証する
# inputs:
#   - C10 module / Markdown Mermaid fixtures
# outputs:
#   - pytest assertions and coverage evidence
# contexts: [C, E]
# network: false
# write-scope: pytest tmp_path only
# dependencies: [pytest]
# ///


VALID_DOC = """
# Blueprint diagrams

<!-- blueprint-diagram: system-architecture -->
```mermaid
flowchart LR
  Browser[Browser] --> API[API]
```

<!-- blueprint-diagram: fact-inference-layers -->
```mermaid
flowchart TB
  Fact[Fact] --> Inference[Inference]
```

<!-- blueprint-diagram: screen-flow -->
```mermaid
stateDiagram-v2
  [*] --> Home
```

```mermaid
%% blueprint-diagram: data-flow-sequence
sequenceDiagram
  Browser->>API: GET /
  API-->>Browser: 200
```

```mermaid
%% blueprint-diagram: data-model
erDiagram
  USER ||--o{ ORDER : places
```
"""


def test_mermaid_cli_valid_contract(mermaid, tmp_path, capsys):
    (tmp_path / "blueprint.md").write_text(VALID_DOC, encoding="utf-8")
    assert mermaid.main(["--docs-dir", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "OK" in out and "required=5/5" in out


def test_mermaid_reports_missing_and_syntax(mermaid, tmp_path, capsys):
    (tmp_path / "broken.md").write_text(
        "<!-- blueprint-diagram: system-architecture -->\n"
        "```mermaid\nflowchart ZZ\nsubgraph DUP\nsubgraph DUP\nA[broken --> B\n```\n",
        encoding="utf-8",
    )
    assert mermaid.main(["--docs-dir", str(tmp_path)]) == 1
    err = capsys.readouterr().err
    assert "MISSING DIAGRAM TYPE" in err and "SYNTAX VIOLATION" in err
    assert mermaid.main(["--docs-dir", str(tmp_path / "absent")]) == 2


def test_mermaid_extract_and_secondary_kinds(mermaid):
    diagrams = mermaid.extract_md_diagrams("~~~mermaid\nclassDiagram\nclass A\n~~~", "x.md")
    assert len(diagrams) == 1
    assert mermaid.classify(diagrams[0]) == "data-model"
    assert mermaid.validate_syntax(diagrams[0]) == []
    assert mermaid.validate_syntax(mermaid.Diagram("x", 1, ["sequenceDiagram"]))
    assert mermaid.validate_syntax(mermaid.Diagram("x", 1, ["stateDiagram-v2", "state A"]))
    assert mermaid.validate_syntax(mermaid.Diagram("x", 1, ["unknownDiagram", "A --> B"]))
