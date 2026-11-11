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

## Explore the information tree visually

Open `tools/tree-explorer.html` in a web browser. Use **Load tree JSON** to select the `.tree.json`, then **Load source file** to select the exact source text view. No web server, build step, or network access is needed. You can also drag-and-drop both files.

The UI offers a collapsible hierarchy, line-span overview, selected-node summaries, source-line navigation, structural diagnostics, and a **keyword-only path preview** over tree titles and summaries. The latter is *not* LLM semantic question answering or goal-order planning.

To bundle one tree and its source into a shareable standalone HTML file:

```bash
python scripts/build_viewer.py src/acl.tree.json --source src/acl.c -o acl-view.html
```

Open `acl-view.html` in any modern browser. The generated HTML embeds the full supplied source text, so **do not publish it** when source content is private or subject to distribution restrictions. The generic unbundled viewer does not upload files; all processing remains in the browser.
