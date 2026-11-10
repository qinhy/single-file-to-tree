# Single File to Tree (LLM-first Agent Skill)

This skill instructs a coding agent to turn one code or document file into a recursively structured JSON information tree. The LLM finds boundaries; helper scripts only extract text and check JSON structure.

## Install

**Codex:** copy this directory to `your-repo/.agents/skills/single-file-to-tree/`.

**Claude Code:** copy this directory to `your-repo/.claude/skills/single-file-to-tree/`.

## Invoke

Codex prompt:

`$single-file-to-tree Convert src/db.c into src/db.tree.json, recursively down to meaningful functions and blocks.`

Claude Code prompt:

`/single-file-to-tree Convert docs/manual.md into docs/manual.tree.json, down to meaningful topics and passages.`

If direct skill invocation is unavailable, point the agent to `SKILL.md` and ask it to follow the instructions.

## Extract text from PDF/DOCX

```bash
pip install pymupdf python-docx
python scripts/to_text.py path/to/manual.pdf -o path/to/manual.extracted.txt
```

Then request conversion of that text view, while retaining the PDF as original source metadata. PDFs with scans, diagrams, charts, or unusual layouts may need additional visual review; the text helper does not perform OCR.

## Validate an output tree

```bash
python scripts/validate_tree.py examples/cooling_manual.tree.json --text examples/cooling_manual.md
```

The validator checks ranges and nesting only. It cannot prove that the LLM understood the source or captured every meaningful unit.
