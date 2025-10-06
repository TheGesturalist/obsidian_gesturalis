CSV -> Obsidian Notes Converter
================================

This tiny script converts a CSV (for example exported from Notion) into a
folder of Markdown files suitable for importing into Obsidian. Each CSV row
becomes a Markdown file with YAML front matter and the Description in the body.

Files

- `scripts/csv_to_obsidian.py` — the converter (no external dependencies)

Quick usage

1. Open a terminal in the repository root.
2. Run:

```bash
python3 scripts/csv_to_obsidian.py \
  "/path/to/Digital_Research_Resources_Aug_31_2025.csv" \
  --out "./vault/Resources"
```

Options

- `--out`: output folder (default: `./obsidian_notes`)
- `--dry-run`: show what would be written without creating files

Notes and tips

- The script uses common CSV headers such as `Name`, `ID`, `Slug`, `Description`,
  `Tags`, `URL`, and `Created time`. If your CSV uses different names, edit the
  script's `header_map` or normalize the CSV headers first.

- Filenames are derived from `Slug`, then `Name`, then `ID` — sanitized to be
  filesystem-safe. If a file already exists, a numeric suffix is appended.

- Tags are split on commas/semicolons/pipes and converted to hyphenated tokens
  to work well as Obsidian tags.

If you'd like, I can:

- detect and map your actual CSV headers automatically,
- include more fields in the front matter,
- or directly import into an existing Obsidian vault structure in your repo.
