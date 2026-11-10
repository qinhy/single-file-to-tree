#!/usr/bin/env python3
"""Check the structural validity of an LLM-generated file-to-tree JSON.

Usage: python scripts/validate_tree.py FILE.tree.json [--text FILE.txt]
This checks JSON shapes, nesting, IDs, source bounds and sibling order.
It cannot establish semantic correctness or complete source coverage.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def validate(doc: dict, total_lines: int | None = None) -> tuple[list[str], int, int]:
    errors: list[str] = []
    seen: set[str] = set()
    n_nodes = 0
    max_depth = 0

    if doc.get('schema_version') != '1.0':
        errors.append('schema_version must be 1.0')
    source = doc.get('source')
    if not isinstance(source, dict):
        errors.append('source must be an object')
        source = {}
    declared_lines = source.get('total_lines')
    if total_lines is None and isinstance(declared_lines, int):
        total_lines = declared_lines
    if not isinstance(source.get('complete'), bool):
        errors.append('source.complete must be a boolean')
    if not isinstance(source.get('warnings'), list):
        errors.append('source.warnings must be a list')

    def visit(node, expected_id: str, parent: tuple[int, int] | None, depth: int) -> tuple[int, int] | None:
        nonlocal n_nodes, max_depth
        n_nodes += 1
        max_depth = max(max_depth, depth)
        if not isinstance(node, dict):
            errors.append(f'{expected_id}: node must be an object')
            return None
        node_id = node.get('id')
        if node_id != expected_id:
            errors.append(f'{expected_id}: id is {node_id!r}; expected {expected_id!r}')
        if node_id in seen:
            errors.append(f'{expected_id}: duplicate id')
        seen.add(node_id)
        for key in ('kind', 'title', 'summary'):
            if not isinstance(node.get(key), str):
                errors.append(f'{expected_id}: {key} must be a string')
        if node.get('origin') not in ('explicit', 'inferred'):
            errors.append(f'{expected_id}: origin must be explicit or inferred')
        rng = node.get('range')
        region = None
        if isinstance(rng, dict):
            s, e = rng.get('start_line'), rng.get('end_line')
            if isinstance(s, int) and isinstance(e, int) and 1 <= s <= e:
                region = (s, e)
                if total_lines is not None and e > total_lines:
                    errors.append(f'{expected_id}: range ends beyond source line count ({e}>{total_lines})')
                if parent and (s < parent[0] or e > parent[1]):
                    errors.append(f'{expected_id}: range is outside parent')
            else:
                errors.append(f'{expected_id}: invalid start_line/end_line')
        else:
            errors.append(f'{expected_id}: range must be an object')
        children = node.get('children')
        if not isinstance(children, list):
            errors.append(f'{expected_id}: children must be a list')
            return region
        last_end = 0
        for i, child in enumerate(children, 1):
            child_region = visit(child, f'{expected_id}.{i}', region, depth + 1)
            if child_region:
                if child_region[0] <= last_end:
                    errors.append(f'{expected_id}: children out of order or overlapping near {i}')
                last_end = child_region[1]
        return region

    root_span = visit(doc.get('root'), '0', None, 0)
    if total_lines is not None and isinstance(declared_lines, int) and declared_lines != total_lines:
        errors.append(f'source.total_lines={declared_lines} does not match actual text lines={total_lines}')
    if source.get('complete') is True and total_lines is not None and root_span != (1, total_lines):
        errors.append(f'complete source should have root range (1, {total_lines}), not {root_span}')
    return errors, n_nodes, max_depth


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('tree', type=Path)
    ap.add_argument('--text', type=Path, help='Source text view used for spans')
    args = ap.parse_args()
    try:
        doc = json.loads(args.tree.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        ap.error(str(exc))
    total_lines = len(args.text.read_text(encoding='utf-8').splitlines()) if args.text else None
    errors, count, depth = validate(doc, total_lines)
    print(f'Nodes: {count}; max depth: {depth}; errors: {len(errors)}')
    for error in errors:
        print(f' - {error}')
    if errors:
        return 1
    print('Structure OK. Note: semantic faithfulness and actual coverage still require review.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
