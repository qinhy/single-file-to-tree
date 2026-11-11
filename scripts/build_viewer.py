#!/usr/bin/env python3
"""Build a standalone offline HTML snapshot that embeds a tree and, optionally, its text view.

Usage:
    python scripts/build_viewer.py path/to/input.tree.json --source path/to/input.c -o tree-view.html

The result opens offline in any browser. You can also open the blank
tools/tree-explorer.html and load local files with its two file controls.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parent.parent / 'tools' / 'tree-explorer.html'
PLACEHOLDER = re.compile(r'const PRELOADED_(TREE|SOURCE) = null;')


def encoded(obj) -> str:
    # Safe even if the document contains </script> or other HTML-like text.
    return json.dumps(obj, ensure_ascii=True).replace('<', '\\u003c')


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('tree', type=Path)
    ap.add_argument('--source', type=Path, help='text view that the line ranges refer to')
    ap.add_argument('-o', '--output', type=Path, required=True)
    args = ap.parse_args()
    try:
        doc = json.loads(args.tree.read_text(encoding='utf-8'))
        # Decode like the viewer's own file loader does, so odd bytes cannot abort the build.
        source = args.source.read_bytes().decode('utf-8-sig', errors='replace') if args.source else None
        template = TEMPLATE.read_text(encoding='utf-8')
    except (OSError, ValueError) as exc:
        ap.error(str(exc))
    if not isinstance(doc, dict) or 'root' not in doc or 'source' not in doc:
        ap.error('Expected a single-file-to-tree schema 1.0 JSON with root and source.')
    if sorted(PLACEHOLDER.findall(template)) != ['SOURCE', 'TREE']:
        ap.error(f'{TEMPLATE} does not contain the PRELOADED_TREE and PRELOADED_SOURCE placeholders.')
    values = {'TREE': doc, 'SOURCE': source}
    # One pass over the template, so embedded text that happens to contain a
    # placeholder (for example this skill's own files) is never substituted again.
    html = PLACEHOLDER.sub(lambda m: f'const PRELOADED_{m.group(1)} = {encoded(values[m.group(1)])};', template)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(html, encoding='utf-8')
    print(f'Wrote standalone HTML snapshot: {args.output}')


if __name__ == '__main__':
    main()
