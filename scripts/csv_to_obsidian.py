#!/usr/bin/env python3
"""
csv_to_obsidian.py

Convert a Notion-exported CSV (or other CSV) into an Obsidian-compatible
folder of Markdown files. Each row becomes one Markdown file with YAML
front matter containing key fields (title, id, slug, tags, url, created)
and the Description as the note body.

Usage:
    python3 csv_to_obsidian.py input.csv --out ./obsidian_notes

The script is intentionally dependency-free (uses stdlib only).
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from datetime import datetime
from typing import Dict, Iterable, List, Optional


# Pre-compile regex patterns for performance
_SLASHES_RE = re.compile(r"[\\/]+")
_SPACES_RE = re.compile(r"\s+")
_UNWANTED_CHARS_RE = re.compile(r"[^0-9A-Za-z\-_.]")

def sanitize_filename(s: str, max_len: int = 200) -> str:
    """Make a filesystem-safe filename from a string.
    Keeps letters, numbers, dash, underscore, and spaces (converted to dashes).
    Trims length and strips leading/trailing punctuation.
    """
    if not s:
        s = "note"
    s = s.strip()
    # Replace spaces and slashes with dashes
    s = _SLASHES_RE.sub("-", s)
    s = _SPACES_RE.sub("-", s)
    # Remove characters we don't want
    s = _UNWANTED_CHARS_RE.sub("", s)
    s = s.strip("-_.")
    if len(s) > max_len:
        s = s[:max_len]
    if not s:
        s = "note"
    return s


def parse_tags(field: Optional[str]) -> List[str]:
    if not field:
        return []
    # Common delimiters: comma, semicolon, pipe
    parts = re.split(r"[,;|]", field)
    tags = []
    for p in parts:
        t = p.strip()
        if not t:
            continue
        # Obsidian tags often are single tokens; convert spaces to hyphens
        t = t.replace(" ", "-")
        # remove leading/trailing # if present
        t = t.lstrip("#")
        tags.append(t)
    return tags


def detect_header_map(fieldnames: Iterable[str]) -> Dict[str, str]:
    """Auto-detect common header name variants and return a canonical->actual map."""
    # Normalize available names (lowercase, stripped)
    norm = {fn.strip().lower(): fn for fn in fieldnames}

    # Variants for canonical names
    variants = {
        "title": ["name", "title"],
        "id": ["id", "uuid"],
        "slug": ["slug", "slugify"],
        "description": ["description", "desc", "details", "body"],
        "tags": ["tags", "tag", "labels"],
        "url": ["url", "link", "links", "website"],
        "created": ["created time", "created", "created_time", "created at", "date"],
        "resource_type": ["resource type", "resource_type", "resource type"],
        "resource_type_original": ["resource_type_original", "resource type original"],
        "resource_type_10": ["resource_type_10", "resource_type_10"],
    }

    header_map: Dict[str, str] = {}
    for canon, opts in variants.items():
        for o in opts:
            if o in norm:
                header_map[canon] = norm[o]
                break
    return header_map


def front_matter_for_row(
    row: Dict[str, str], header_map: Dict[str, str], include_summary: bool = False, summary_len: int = 200
) -> str:
    # header_map maps canonical names to actual CSV header keys
    title = row.get(header_map.get("title", "Name"), "").strip()
    idv = row.get(header_map.get("id", "ID"), "").strip()
    slug = row.get(header_map.get("slug", "Slug"), "").strip()
    tags_field = row.get(header_map.get("tags", "Tags"), "").strip()
    url = row.get(header_map.get("url", "URL"), "").strip()
    created = row.get(header_map.get("created", "Created time"), "").strip()
    resource_type = row.get(header_map.get("resource_type", "Resource Type"), "").strip()
    resource_type_original = row.get(header_map.get("resource_type_original", "resource_type_original"), "").strip()
    resource_type_10 = row.get(header_map.get("resource_type_10", "resource_type_10"), "").strip()
    description = row.get(header_map.get("description", "Description"), "").strip()

    tags = parse_tags(tags_field)

    fm_lines = ["---"]
    fm_lines.append(f"title: \"{title}\"")
    if idv:
        fm_lines.append(f"id: \"{idv}\"")
    if slug:
        fm_lines.append(f"slug: \"{slug}\"")
    if url:
        fm_lines.append(f"url: \"{url}\"")
    if created:
        fm_lines.append(f"created: \"{created}\"")
    if resource_type:
        fm_lines.append(f"resource_type: \"{resource_type}\"")
    if resource_type_original:
        fm_lines.append(f"resource_type_original: \"{resource_type_original}\"")
    if resource_type_10:
        fm_lines.append(f"resource_type_10: \"{resource_type_10}\"")

            summary_esc = summary.replace('"', '\\"')
    if include_summary:
        summary = (description[:summary_len] + "...") if len(description) > summary_len else description
        if summary:
            # Escape quotes
            summary_esc = summary.replace('"', "\"")
            fm_lines.append(f"summary: \"{summary_esc}\"")

    # keep a small aliases list
    fm_lines.append("aliases:")
    if title:
        fm_lines.append(f"  - \"{title}\"")
    fm_lines.append("---\n")

    return "\n".join(fm_lines)


def row_body(row: Dict[str, str], header_map: Dict[str, str], inline_tags: bool = False) -> str:
    # Use Description as main body; fallback to empty string
    desc = row.get(header_map.get("description", "Description"), "").strip()
    # Add a small metadata block at bottom (URL)
    url = row.get(header_map.get("url", "URL"), "").strip()
    lines = []
    if desc:
        lines.append(desc)
    if url:
        lines.append("\n---\n")
        lines.append(f"Source: [{url}]({url})")
    # Optionally append inline Obsidian tags (e.g., #tag)
    if inline_tags:
        tags_field = row.get(header_map.get("tags", "Tags"), "").strip()
        tags = parse_tags(tags_field)
        if tags:
            tag_tokens = " ".join(f"#{t}" for t in tags)
            # ensure a blank line before tags if body exists
            if lines:
                lines.append("\n")
            lines.append(tag_tokens)
    return "\n".join(lines)


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def convert_csv(
    csv_path: str,
    out_dir: str,
    filename_column_priorities: Iterable[str] = ("Slug", "Name", "ID"),
    header_map: Optional[Dict[str, str]] = None,
    dry_run: bool = False,
    inline_tags: bool = False,
    include_summary: bool = False,
    summary_len: int = 200,
) -> int:
    header_map = header_map or {}
    ensure_dir(out_dir)
    created = 0
    with open(csv_path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        # If header_map not provided, detect common variants
        if not header_map:
            detected = detect_header_map(reader.fieldnames or [])
            header_map.update(detected)
        for rownum, row in enumerate(reader, start=1):
            # Choose filename base from priority columns
            base = None
            for col in filename_column_priorities:
                val = row.get(header_map.get(col.lower(), col), "") or row.get(col, "")
                if val:
                    base = val.strip()
                    break
            if not base:
                base = f"note-{rownum}"

            filename_base = sanitize_filename(base)
            filename = f"{filename_base}.md"
            out_path = os.path.join(out_dir, filename)

            # Avoid overwriting: if exists, append a numeric suffix
            if os.path.exists(out_path):
                i = 1
                while True:
                    candidate = os.path.join(out_dir, f"{filename_base}-{i}.md")
                    if not os.path.exists(candidate):
                        out_path = candidate
                        break
                    i += 1

            fm = front_matter_for_row(row, header_map, include_summary=include_summary, summary_len=summary_len)
            body = row_body(row, header_map, inline_tags=inline_tags)
            content = fm + body + "\n"

            if dry_run:
                print(f"DRY: would write {out_path}")
            else:
                with open(out_path, "w", encoding="utf-8") as outfh:
                    outfh.write(content)
            created += 1

    return created


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Convert CSV rows to Obsidian markdown notes")
    p.add_argument("csv", help="Input CSV file")
    p.add_argument("--out", default="./obsidian_notes", help="Output folder for markdown notes")
    p.add_argument("--dry-run", action="store_true", help="Don't write files, just show what would happen")
    p.add_argument("--inline-tags", action="store_true", help="Append inline Obsidian tags (e.g., #tag) to the note body")
    p.add_argument("--summary", action="store_true", help="Include a micro-summary field in front matter")
    p.add_argument("--summary-len", type=int, default=200, help="Max length for micro-summary (default: 200)")
    args = p.parse_args(argv)

    csv_path = args.csv
    out_dir = args.out

    if not os.path.isfile(csv_path):
        print(f"Input CSV not found: {csv_path}")
        return 2

    print(f"Converting {csv_path} -> {out_dir}")
    created = convert_csv(
        csv_path,
        out_dir,
        dry_run=args.dry_run,
        inline_tags=args.inline_tags,
        include_summary=args.summary,
        summary_len=args.summary_len,
    )
    print(f"Processed {created} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
