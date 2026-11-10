#!/usr/bin/env python3
"""Extract a text view for a single source file; does NOT build a tree.

Usage: python scripts/to_text.py INPUT [-o OUTPUT]
Optional dependencies for rich formats: pip install pymupdf python-docx
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys


def extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == '.pdf':
        try:
            import fitz
        except ImportError as exc:
            raise RuntimeError('PDF extraction requires: pip install pymupdf') from exc
        blocks = []
        with fitz.open(path) as doc:
            for page_no, page in enumerate(doc, 1):
                content = page.get_text('text', sort=True).strip()
                if not content:
                    content = '[NO EXTRACTABLE TEXT — page may contain scans, diagrams, or images]'
                blocks.append(f'[[PAGE {page_no}]]\n{content}')
        return '\n\n'.join(blocks) + '\n'

    if suffix == '.docx':
        try:
            from docx import Document
            from docx.oxml.ns import qn
        except ImportError as exc:
            raise RuntimeError('DOCX extraction requires: pip install python-docx') from exc
        doc = Document(path)
        chunks = []
        for block in doc.element.body.iterchildren():
            if block.tag == qn('w:p'):
                # Extract paragraph contents, preserving logical order.
                value = ''.join(el.text or '' for el in block.iter() if el.tag == qn('w:t'))
                if value.strip():
                    chunks.append(value)
            elif block.tag == qn('w:tbl'):
                chunks.append('[[TABLE]]')
                for row in block.findall(qn('w:tr')):
                    cells = []
                    for cell in row.findall(qn('w:tc')):
                        text = ''.join(el.text or '' for el in cell.iter() if el.tag == qn('w:t'))
                        cells.append(text.replace('\n', ' '))
                    chunks.append(' | '.join(cells))
                chunks.append('[[/TABLE]]')
        return '\n'.join(chunks) + '\n'

    try:
        return path.read_text(encoding='utf-8-sig')
    except UnicodeDecodeError as exc:
        raise RuntimeError(f'Cannot decode as UTF-8: {path}. Convert its encoding or use a format-specific extractor.') from exc


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('input', type=Path)
    ap.add_argument('-o', '--output', type=Path)
    args = ap.parse_args()
    if not args.input.is_file():
        ap.error(f'File does not exist: {args.input}')
    output = args.output or args.input.with_suffix('.extracted.txt')
    try:
        content = extract_text(args.input)
    except Exception as exc:
        print(f'Extraction failed: {exc}', file=sys.stderr)
        return 1
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding='utf-8')
    print(f'Wrote: {output} ({len(content.splitlines())} lines; {len(content):,} characters)')
    if args.input.suffix.lower() in {'.pdf', '.docx'}:
        print('Note: text extraction may omit diagrams, images, layout, and some tables; review source if needed.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
