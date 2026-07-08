#!/usr/bin/env python3
"""Rebuild flows/robot_ui_flow.json from the externalized source files
under src/, per the mapping recorded in manifest.json.

This is the counterpart to tools/extract_flow.py. The UI template
should be edited in src/ui/main_template.html (and src/i18n.js) rather
than in flows/robot_ui_flow.json directly; run this script to
regenerate the flow JSON.

Usage:
  python3 tools/build_flow.py             # write flows/robot_ui_flow.json
  python3 tools/build_flow.py --out PATH  # write to PATH instead
  python3 tools/build_flow.py --check     # build in-memory and diff
                                           # against the current flow
                                           # file; exit 0 if identical,
                                           # 1 otherwise (no file written)
"""
import argparse
import difflib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = REPO_ROOT / "manifest.json"


def build(manifest):
    target_path = REPO_ROOT / manifest["target"]
    skeleton_path = REPO_ROOT / manifest["skeleton"]

    skeleton_data = json.loads(skeleton_path.read_text(encoding="utf-8"))

    for injection in manifest["injections"]:
        node_id = injection["node_id"]
        field = injection["field"]
        source_path = REPO_ROOT / injection["source"]
        content = source_path.read_text(encoding="utf-8")

        for marker_spec in injection.get("nested", []):
            marker = marker_spec["marker"]
            nested_source_path = REPO_ROOT / marker_spec["source"]
            nested_content = nested_source_path.read_text(encoding="utf-8")
            if marker not in content:
                raise ValueError(f"marker {marker!r} not found in {source_path}")
            content = content.replace(marker, nested_content)

        node = None
        for candidate in skeleton_data:
            if candidate.get("id") == node_id:
                node = candidate
                break
        if node is None:
            raise ValueError(f"node id {node_id!r} not found in {skeleton_path}")
        node[field] = content

    return target_path, json.dumps(skeleton_data, indent=4, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="diff against the current flow file instead of writing")
    parser.add_argument("--out", type=str, default=None, help="write output to this path instead of the manifest target")
    args = parser.parse_args()

    if not MANIFEST_PATH.exists():
        print(f"error: {MANIFEST_PATH} not found", file=sys.stderr)
        return 1
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    target_path, built_text = build(manifest)

    if args.check:
        if not target_path.exists():
            print(f"error: {target_path} does not exist to check against", file=sys.stderr)
            return 1
        current_text = target_path.read_text(encoding="utf-8")
        if built_text == current_text:
            print(f"OK: rebuilt output is byte-identical to {target_path.relative_to(REPO_ROOT)}")
            return 0
        diff = difflib.unified_diff(
            current_text.splitlines(keepends=True),
            built_text.splitlines(keepends=True),
            fromfile=str(target_path.relative_to(REPO_ROOT)),
            tofile="rebuilt",
        )
        diff_lines = list(diff)
        print(f"MISMATCH: rebuilt output differs from {target_path.relative_to(REPO_ROOT)}", file=sys.stderr)
        for line in diff_lines[:60]:
            print(line, end="" if line.endswith("\n") else "\n", file=sys.stderr)
        if len(diff_lines) > 60:
            print(f"... ({len(diff_lines) - 60} more diff lines)", file=sys.stderr)
        return 1

    out_path = Path(args.out).resolve() if args.out else target_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(built_text, encoding="utf-8")
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
