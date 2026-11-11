#!/usr/bin/env python3
"""Extract the text view of one source file. This does NOT build a tree.

Usage: python scripts/to_text.py INPUT [-o OUTPUT]
Default output: <input-stem>.extracted.txt beside the input.
Optional dependencies for rich formats: pip install pymupdf python-docx

Markers written into the text view:
  [[PAGE n]]                 first line of each PDF page
  [NO EXTRACTABLE TEXT ...]  a PDF page with no text layer (scan, diagram, image)
  # / ## / ###               DOCX paragraphs styled Title or Heading 1-9
  [[TABLE]] ... [[/TABLE]]   a DOCX table, one row per line, cells joined by " | "
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

NO_TEXT = '[NO EXTRACTABLE TEXT — page may contain scans, diagrams, or images]'
# Characters that some tools treat as line breaks and others do not. Turning them
# into plain newlines keeps every tool's line numbers in step.
ODD_BREAKS = re.compile('\r\n|[\r\x0b\x0c\x1c\x1d\x1e\x85\u2028\u2029]')


def count_lines(text: str) -> int:
    return len(text.split('\n')) - (1 if text.endswith('\n') else 0)


def extract_pdf(path: Path) -> tuple[str, list[str]]:
    try:
        import pymupdf
    except ImportError:
        try:
            import fitz as pymupdf  # older PyMuPDF releases
        except ImportError as exc:
            raise RuntimeError('PDF extraction requires: pip install pymupdf') from exc
    blocks, empty_pages = [], []
    with pymupdf.open(path) as doc:
        for page_no, page in enumerate(doc, 1):
            content = page.get_text('text', sort=True).strip()
            if not content:
                content = NO_TEXT
                empty_pages.append(str(page_no))
            blocks.append(f'[[PAGE {page_no}]]\n{content}')
    limits = []
    if empty_pages:
        limits.append(f'no extractable text on page(s) {", ".join(empty_pages)}')
    return '\n\n'.join(blocks) + '\n', limits


def extract_docx(path: Path) -> tuple[str, list[str]]:
    try:
        from docx import Document
        from docx.oxml.ns import qn
    except ImportError as exc:
        raise RuntimeError('DOCX extraction requires: pip install python-docx') from exc
    doc = Document(path)
    style_names = {s.style_id: (s.name or '').lower() for s in doc.styles}
    T, TAB, BR = qn('w:t'), qn('w:tab'), qn('w:br')

    def text_of(element) -> str:
        parts = []
        for el in element.iter():
            if el.tag == T:
                parts.append(el.text or '')
            elif el.tag == TAB:
                parts.append('\t')
            elif el.tag == BR:
                parts.append('\n')
        return ''.join(parts)

    def style_name(paragraph) -> str:
        style = paragraph.find(f"{qn('w:pPr')}/{qn('w:pStyle')}")
        return style_names.get(style.get(qn('w:val')), '') if style is not None else ''

    body = list(doc.element.body.iterchildren())
    # With a Title paragraph present, Heading 1 becomes "##" so it nests under the title.
    shift = 1 if any(b.tag == qn('w:p') and style_name(b) == 'title' for b in body) else 0

    def heading_prefix(paragraph) -> str:
        name = style_name(paragraph)
        match = re.fullmatch(r'heading ([1-9])', name)
        if match:
            return '#' * (int(match.group(1)) + shift) + ' '
        return '# ' if name == 'title' else ''

    chunks = []
    for block in body:
        if block.tag == qn('w:p'):
            value = text_of(block).strip()
            if value:
                prefix = heading_prefix(block)
                chunks.append(prefix + (' '.join(value.split()) if prefix else value))
        elif block.tag == qn('w:tbl'):
            chunks.append('[[TABLE]]')
            for row in block.findall(qn('w:tr')):
                cells = [' '.join(text_of(cell).split()) for cell in row.findall(qn('w:tc'))]
                chunks.append(' | '.join(cells))
            chunks.append('[[/TABLE]]')
    limits = []
    pictures = sum(1 for el in doc.element.body.iter() if el.tag in (qn('w:drawing'), qn('w:pict')))
    if pictures:
        limits.append(f'{pictures} embedded image(s) or drawing(s) were not extracted')
    return '\n'.join(chunks) + '\n', limits


def extract_text(path: Path) -> tuple[str, list[str]]:
    """Return (text view, limitations to record in source.warnings)."""
    suffix = path.suffix.lower()
    if suffix in ('.pdf', '.docx'):
        text, limits = extract_pdf(path) if suffix == '.pdf' else extract_docx(path)
        text = ODD_BREAKS.sub('\n', text)
        return '\n'.join(line.rstrip() for line in text.split('\n')), limits
    try:
        # Plain text is passed through unchanged so its lines match the original file.
        return path.read_text(encoding='utf-8-sig'), []
    except UnicodeDecodeError as exc:
        raise RuntimeError(f'Cannot decode as UTF-8: {path}. Convert its encoding or use a '
                           'format-specific extractor.') from exc


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('input', type=Path)
    ap.add_argument('-o', '--output', type=Path)
    args = ap.parse_args()
    if not args.input.is_file():
        ap.error(f'File does not exist: {args.input}')
    output = args.output or args.input.with_suffix('.extracted.txt')
    try:
        content, limits = extract_text(args.input)
    except Exception as exc:
        print(f'Extraction failed: {exc}', file=sys.stderr)
        return 1
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding='utf-8')
    print(f'Wrote: {output} ({count_lines(content)} lines; {len(content):,} characters)')
    for limit in limits:
        print(f'LIMITATION: {limit}. Set source.complete to false and add this to source.warnings.')
    if args.input.suffix.lower() in {'.pdf', '.docx'}:
        print('Note: extraction can also lose layout, diagrams and some tables; compare with the original if in doubt.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
