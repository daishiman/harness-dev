# Bundled Python Dependencies

`skill-intake` bundles the Python packages needed by its scripts so a Claude Code
plugin install works without asking users to run `pip install`.

Runtime loader:

- `scripts/_vendor.py`

Bundled packages:

- `jinja2`
- `MarkupSafe` (pure-Python fallback only; compiled speedups are not required)
- `typing_extensions`

JSON Schema validation uses `scripts/_jsonschema_compat.py`, a stdlib fallback
covering the schema keywords used by this plugin. Runtime `pip install` repair is
intentionally not used, so normal execution does not depend on network access or
writable plugin directories.
