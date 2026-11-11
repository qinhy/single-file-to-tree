#!/usr/bin/env python3
"""Check the structure of a single-file-to-tree JSON document (schema 1.0).

Usage: python scripts/validate_tree.py FILE.tree.json [--text TEXT_VIEW] [--renumber]

--renumber rewrites every id by position (0, 0.1, 0.1.2, ...) in the file before
checking, so ids never need to be maintained by hand after inserting or removing nodes.

Errors (exit code 1): JSON shape, positional ids, line bounds, nesting, sibling order.
Notes  (exit code 0): things to review by eye, such as content lines that no leaf covers.

A clean run shows that the ranges are consistent. It does not show that titles and
summaries are faithful to the source or that the splits are sensible.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

TOP_KEYS = {'schema_version', 'source', 'root'}
SOURCE_KEYS = {'path', 'text_view', 'total_lines', 'complete', 'warnings'}
NODE_KEYS = {'id', 'kind', 'title', 'origin', 'range', 'summary', 'children'}
# Lines that may sit outside every leaf without review: punctuation-only lines
# (closing braces, rules) and the markers that scripts/to_text.py writes.
DELIMITER = re.compile(r'[\W_]*$|\[\[(PAGE \d+|/?TABLE)\]\]$|\[NO EXTRACTABLE TEXT\b')
MAX_LISTED = 25


def split_lines(text: str) -> list[str]:
    """Split the way the viewer and `cat -n` do: on \\r\\n, \\n or \\r only.

    str.splitlines() also breaks on form feeds and a few other characters,
    which would put this count out of step with editors and the viewer.
    """
    lines = re.split(r'\r\n|\n|\r', text)
    if lines and lines[-1] == '':
        lines.pop()
    return lines


def renumber(node, node_id: str = '0'):
    """Return the node with positional ids assigned throughout its subtree."""
    if not isinstance(node, dict):
        return node
    out = {'id': node_id, **{k: v for k, v in node.items() if k != 'id'}}
    if isinstance(out.get('children'), list):
        out['children'] = [renumber(c, f'{node_id}.{i}') for i, c in enumerate(out['children'], 1)]
    return out


def is_line_number(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def validate(doc, lines: list[str] | None = None) -> tuple[list[str], list[str], int, int]:
    """Return (errors, notes, node_count, max_depth). `lines` is the text view, if known."""
    errors: list[str] = []
    notes: list[str] = []
    seen: set[str] = set()
    in_leaf: set[int] = set()
    parent_first_lines: set[int] = set()
    n_nodes = 0
    max_depth = 0

    if not isinstance(doc, dict):
        return ['top level must be an object'], notes, 0, 0
    if doc.get('schema_version') != '1.0':
        errors.append('schema_version must be "1.0"')
    if set(doc) - TOP_KEYS:
        notes.append(f'top level has fields outside the contract: {sorted(set(doc) - TOP_KEYS)}')

    source = doc.get('source')
    if not isinstance(source, dict):
        errors.append('source must be an object')
        source = {}
    for key in ('path', 'text_view'):
        if not isinstance(source.get(key), str) or not source.get(key):
            errors.append(f'source.{key} must be a non-empty string')
    declared = source.get('total_lines')
    if not is_line_number(declared):
        errors.append('source.total_lines must be an integer')
        declared = None
    complete, warnings = source.get('complete'), source.get('warnings')
    if not isinstance(complete, bool):
        errors.append('source.complete must be a boolean')
    if not isinstance(warnings, list) or not all(isinstance(w, str) for w in warnings):
        errors.append('source.warnings must be a list of strings')
    elif complete is False and not warnings:
        errors.append('source.complete is false, so source.warnings must say what was not examined')
    if set(source) - SOURCE_KEYS:
        notes.append(f'source has fields outside the contract: {sorted(set(source) - SOURCE_KEYS)}')

    total = len(lines) if lines is not None else declared
    if lines is not None and declared is not None and declared != total:
        errors.append(f'source.total_lines={declared} does not match the text view ({total} lines)')

    def visit(node, expected_id: str, parent: tuple[int, int] | None, depth: int):
        nonlocal n_nodes, max_depth
        n_nodes += 1
        max_depth = max(max_depth, depth)
        if not isinstance(node, dict):
            errors.append(f'{expected_id}: node must be an object')
            return None
        node_id = node.get('id')
        if node_id != expected_id:
            errors.append(f'{expected_id}: id is {node_id!r}; expected {expected_id!r}')
        if isinstance(node_id, str) and node_id in seen:
            errors.append(f'{expected_id}: duplicate id')
        seen.add(node_id)
        for key in ('kind', 'title'):
            if not isinstance(node.get(key), str) or not node[key].strip():
                errors.append(f'{expected_id}: {key} must be a non-empty string')
        if not isinstance(node.get('summary'), str):
            errors.append(f'{expected_id}: summary must be a string (use "" when none is possible)')
        if node.get('origin') not in ('explicit', 'inferred'):
            errors.append(f'{expected_id}: origin must be explicit or inferred')
        if set(node) - NODE_KEYS:
            notes.append(f'{expected_id}: fields outside the contract: {sorted(set(node) - NODE_KEYS)}')

        rng = node.get('range')
        region = None
        if isinstance(rng, dict):
            s, e = rng.get('start_line'), rng.get('end_line')
            if is_line_number(s) and is_line_number(e) and 1 <= s <= e:
                region = (s, e)
                if total is not None and e > total:
                    errors.append(f'{expected_id}: range ends beyond the last line ({e} > {total})')
                if parent and (s < parent[0] or e > parent[1]):
                    errors.append(f'{expected_id}: range {s}-{e} is outside its parent {parent[0]}-{parent[1]}')
            else:
                errors.append(f'{expected_id}: start_line and end_line must be integers with 1 <= start <= end')
        else:
            errors.append(f'{expected_id}: range must be an object')

        children = node.get('children')
        if not isinstance(children, list):
            errors.append(f'{expected_id}: children must be a list ([] on leaves)')
            return region
        if region:
            if children:
                parent_first_lines.add(region[0])
            else:
                in_leaf.update(range(region[0], region[1] + 1))
        last_end = 0
        for i, child in enumerate(children, 1):
            child_region = visit(child, f'{expected_id}.{i}', region, depth + 1)
            if child_region:
                if child_region[0] <= last_end:
                    errors.append(f'{expected_id}.{i}: starts at line {child_region[0]}, '
                                  f'but the previous sibling ends at line {last_end}')
                last_end = max(last_end, child_region[1])
                if len(children) == 1 and child_region == region:
                    notes.append(f'{expected_id}: its only child has the same range; merge the two')
        return region

    root_span = visit(doc.get('root'), '0', None, 0)
    if total and root_span and root_span != (1, total):
        errors.append(f'root range must be 1-{total} (the whole text view), not {root_span[0]}-{root_span[1]}')

    if lines is not None and not errors:
        loose = [i for i in range(1, total + 1)
                 if i not in in_leaf and i not in parent_first_lines
                 and not DELIMITER.match(lines[i - 1].strip())]
        if loose:
            groups: list[list[int]] = []
            for i in loose:
                if groups and i == groups[-1][1] + 1:
                    groups[-1][1] = i
                else:
                    groups.append([i, i])
            notes.append(f'{len(loose)} content line(s) sit in no leaf. Give each a node unless it is '
                         'part of a parent heading or signature:')
            for a, b in groups[:MAX_LISTED]:
                label = f'L{a}' if a == b else f'L{a}-{b}'
                notes.append(f'    {label}: {lines[a - 1].strip()[:90]}')
            if len(groups) > MAX_LISTED:
                notes.append(f'    ... and {len(groups) - MAX_LISTED} more group(s)')
    return errors, notes, n_nodes, max_depth


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('tree', type=Path)
    ap.add_argument('--text', type=Path, help='text view that the line ranges refer to')
    ap.add_argument('--renumber', action='store_true', help='rewrite positional ids in FILE before checking')
    args = ap.parse_args()
    try:
        doc = json.loads(args.tree.read_text(encoding='utf-8'))
        lines = None
        if args.text:
            lines = split_lines(args.text.read_bytes().decode('utf-8-sig', errors='replace'))
    except (OSError, ValueError) as exc:
        ap.error(str(exc))
    if args.renumber and isinstance(doc, dict) and 'root' in doc:
        doc['root'] = renumber(doc['root'])
        args.tree.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        print(f'Renumbered ids in {args.tree}')
    errors, notes, count, depth = validate(doc, lines)
    print(f'Nodes: {count}; max depth: {depth}; errors: {len(errors)}')
    for error in errors:
        print(f' - {error}')
    if notes:
        print('Notes to review (not errors):')
        for note in notes:
            print(f' * {note}')
    if errors:
        return 1
    if lines is None:
        print('Structure OK, but line counts and coverage were not checked. Rerun with --text.')
    else:
        print('Structure OK. Titles, summaries and coverage still need a read against the source.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
