#!/usr/bin/env python3
"""Extract the UI template (and its i18n object literal) out of
flows/robot_ui_flow.json into standalone source files under src/.

This is the counterpart to tools/build_flow.py, which re-injects those
source files back into the flow JSON. Run this script whenever the
template has been edited directly in the Node-RED editor, to re-sync
src/ with the current flows/robot_ui_flow.json.

Outputs:
  - src/ui/main_template.html      verbatim `format` string of
                                    node_ui_template_main, with the
                                    `scope.i18n = {...}` object literal
                                    replaced by the marker __I18N__.
  - src/i18n.js                    the extracted i18n object literal,
                                    verbatim (kept as a JS object
                                    literal, not converted to JSON, so
                                    the round trip is byte-exact).
  - src/flows/robot_ui_flow.skeleton.json
                                    the full flow JSON with the
                                    node_ui_template_main "format"
                                    field replaced by the placeholder
                                    string "__MAIN_TEMPLATE__".
  - manifest.json                  records the injection mapping used
                                    by tools/build_flow.py.
"""
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FLOW_PATH = REPO_ROOT / "flows" / "robot_ui_flow.json"
TARGET_NODE_ID = "node_ui_template_main"
TARGET_FIELD = "format"

TEMPLATE_HTML_PATH = REPO_ROOT / "src" / "ui" / "main_template.html"
I18N_JS_PATH = REPO_ROOT / "src" / "i18n.js"
SKELETON_PATH = REPO_ROOT / "src" / "flows" / "robot_ui_flow.skeleton.json"
MANIFEST_PATH = REPO_ROOT / "manifest.json"

SKELETON_PLACEHOLDER = "__MAIN_TEMPLATE__"
I18N_MARKER = "__I18N__"
I18N_ASSIGN_PREFIX = "scope.i18n = "


def find_matching_brace(text, open_index):
    """Given the index of an opening '{' in `text`, return the index of
    its matching closing '}', respecting JS string literals (', ", `)
    so that braces appearing inside strings are not counted.

    Raises ValueError if no matching brace is found.
    """
    assert text[open_index] == "{"
    depth = 0
    i = open_index
    n = len(text)
    in_string = None  # None, or the quote character currently open
    while i < n:
        ch = text[i]
        if in_string is not None:
            if ch == "\\":
                i += 2
                continue
            if ch == in_string:
                in_string = None
            i += 1
            continue
        if ch in ("'", '"', "`"):
            in_string = ch
            i += 1
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise ValueError("No matching closing brace found for i18n object literal")


def extract_i18n(template_text):
    """Locate `scope.i18n = { ... };` in template_text and split it into
    (template_with_marker, i18n_object_literal_text).

    Returns None if the assignment cannot be located (caller should then
    fall back to extracting the whole template without the i18n split).
    """
    assign_index = template_text.find(I18N_ASSIGN_PREFIX)
    if assign_index == -1:
        return None
    brace_start = assign_index + len(I18N_ASSIGN_PREFIX)
    if brace_start >= len(template_text) or template_text[brace_start] != "{":
        return None
    try:
        brace_end = find_matching_brace(template_text, brace_start)
    except ValueError:
        return None

    i18n_literal = template_text[brace_start:brace_end + 1]
    template_with_marker = (
        template_text[:brace_start] + I18N_MARKER + template_text[brace_end + 1:]
    )
    return template_with_marker, i18n_literal


def main():
    if not FLOW_PATH.exists():
        print(f"error: {FLOW_PATH} not found", file=sys.stderr)
        return 1

    flow_text = FLOW_PATH.read_text(encoding="utf-8")
    flow_data = json.loads(flow_text)

    target_node = None
    for node in flow_data:
        if node.get("id") == TARGET_NODE_ID:
            target_node = node
            break
    if target_node is None:
        print(f"error: node id {TARGET_NODE_ID!r} not found in {FLOW_PATH}", file=sys.stderr)
        return 1
    if TARGET_FIELD not in target_node:
        print(f"error: node {TARGET_NODE_ID!r} has no {TARGET_FIELD!r} field", file=sys.stderr)
        return 1

    template_text = target_node[TARGET_FIELD]

    result = extract_i18n(template_text)
    injections = [{"node_id": TARGET_NODE_ID, "field": TARGET_FIELD, "source": "src/ui/main_template.html"}]

    if result is not None:
        template_with_marker, i18n_literal = result
        TEMPLATE_HTML_PATH.parent.mkdir(parents=True, exist_ok=True)
        TEMPLATE_HTML_PATH.write_text(template_with_marker, encoding="utf-8")
        I18N_JS_PATH.parent.mkdir(parents=True, exist_ok=True)
        I18N_JS_PATH.write_text(i18n_literal, encoding="utf-8")
        injections[0]["nested"] = [{"marker": I18N_MARKER, "source": "src/i18n.js"}]
        print(f"wrote {TEMPLATE_HTML_PATH.relative_to(REPO_ROOT)} ({len(template_with_marker)} chars, with {I18N_MARKER} marker)")
        print(f"wrote {I18N_JS_PATH.relative_to(REPO_ROOT)} ({len(i18n_literal)} chars)")
    else:
        # Fallback: extract the whole template verbatim, no i18n split.
        TEMPLATE_HTML_PATH.parent.mkdir(parents=True, exist_ok=True)
        TEMPLATE_HTML_PATH.write_text(template_text, encoding="utf-8")
        if I18N_JS_PATH.exists():
            I18N_JS_PATH.unlink()
        print(f"wrote {TEMPLATE_HTML_PATH.relative_to(REPO_ROOT)} ({len(template_text)} chars, i18n split NOT applied - fallback mode)")

    # Build skeleton: full flow with the target field replaced by a placeholder.
    skeleton_data = json.loads(flow_text)
    for node in skeleton_data:
        if node.get("id") == TARGET_NODE_ID:
            node[TARGET_FIELD] = SKELETON_PLACEHOLDER
            break
    SKELETON_PATH.parent.mkdir(parents=True, exist_ok=True)
    SKELETON_PATH.write_text(json.dumps(skeleton_data, indent=4, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {SKELETON_PATH.relative_to(REPO_ROOT)}")

    manifest = {
        "target": "flows/robot_ui_flow.json",
        "skeleton": "src/flows/robot_ui_flow.skeleton.json",
        "injections": injections,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {MANIFEST_PATH.relative_to(REPO_ROOT)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
