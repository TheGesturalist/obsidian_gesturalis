#!/usr/bin/env python3
"""
normalize_and_index.py

Scan the converted Markdown files folder, normalize tags, produce a mapping
report (CSV), and generate a small INDEX.md listing entries with links,
summaries, and tags.

This script is dependency-free and designed to work with the output of
scripts/csv_to_obsidian.py in scripts/drop_off/converted/.
"""
from __future__ import annotations

import csv
import os
import re
from typing import List, Optional, Tuple
from datetime import datetime


CONVERTED_DIR = "scripts/drop_off/converted"
MAPPING_CSV = "scripts/drop_off/mapping_report.csv"
INDEX_MD = os.path.join(CONVERTED_DIR, "INDEX.md")


def read_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def write_file(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)


def parse_front_matter(text: str) -> Tuple[Optional[str], str]:
    """Return (front_matter_text or None, rest_of_text)
    front_matter_text includes the delimiters '---' lines if present.
    """
    if text.startswith("---"):
        parts = text.split("---", 2)
        # parts[0] == '' , parts[1] == fm content, parts[2] == rest
        if len(parts) >= 3:
            fm = parts[1].strip()
            rest = parts[2].lstrip("\n")
            return fm, rest
    return None, text


# Compile regex patterns at module level for performance
YAML_FIELD_PATTERN = re.compile(r"^([A-Za-z0-9_]+):\s*(?:\"(.*)\"|(.*))?")
YAML_LIST_ITEM_PATTERN = re.compile(r"^\s*[-]\s+\"?")

def parse_fm_fields(fm_text: str) -> dict:
    # Very small YAML-ish parser for our simple front matter
    d = {}
    lines = fm_text.splitlines()
    key = None
    for line in lines:
        if YAML_LIST_ITEM_PATTERN.match(line):
            # list item continuation
            if key:
                val = re.sub(r"^\s*[-]\s+\"?", "", line).rstrip('\"')
                # If current value is a string, convert to list (even if empty)
                if key in d and isinstance(d[key], str):
                    if d[key] == "":
                        d[key] = []
                    else:
                        d[key] = [d[key]]
                d.setdefault(key, []).append(val)
            continue
        m = YAML_FIELD_PATTERN.match(line)
        if m:
            k = m.group(1)
            v = m.group(2) if m.group(2) is not None else (m.group(3) or "")
            d[k] = v
            key = k
        else:
            # skip unknown lines
INLINE_TAG_PATTERN = re.compile(r"(?<!\w)#([A-Za-z0-9_\-]+)")

def find_inline_tags(text: str) -> List[str]:
    # Find hashtag tokens anywhere; restrict to word chars, hyphen, underscore
    tags = INLINE_TAG_PATTERN.findall(text)
    return tags
def find_inline_tags(text: str) -> List[str]:
    # Find hashtag tokens anywhere; restrict to word chars, hyphen, underscore
    tags = re.findall(r"(?<!\w)#([A-Za-z0-9_\-]+)", text)
    return tags


def normalize_tag(t: str) -> str:
    t = t.strip().lstrip("#")
    t = t.replace("_", "-")
    t = t.replace(" ", "-")
    t = t.lower()
    t = re.sub(r"[^a-z0-9\-]", "", t)
    t = re.sub(r"-+", "-", t)
    t = t.strip("-")
    return t


def normalize_tags_list(tags: List[str]) -> List[str]:
    seen = set()
    out = []
    for t in tags:
        n = normalize_tag(t)
        if not n:
            continue
        if n in seen:
            continue
        seen.add(n)
        out.append(n)
    return out

# Compile regex patterns at module level for performance
TRAILING_HASHTAGS_PATTERN = re.compile(r"^\s*(#[-\w]+(?:\s+#[-\w]+)*)\s*$")

def rewrite_file_with_tags(path: str, fm_text: Optional[str], rest: str, normalized_tags: List[str]) -> None:
    # Build new front matter (preserve existing fm fields where possible)
    fm_fields = parse_fm_fields(fm_text) if fm_text else {}

    # Ensure tags are present in fm_fields as a YAML list
    fm_lines = []
    # Reconstruct some known fields in a stable order
    order = ["title", "id", "slug", "url", "created", "resource_type", "resource_type_original", "resource_type_10", "summary"]
    for k in order:
        if k in fm_fields and fm_fields[k] != "":
            fm_lines.append(f'{k}: "{fm_fields[k]}"')

    if normalized_tags:
        fm_lines.append("tags:")
        for t in normalized_tags:
            fm_lines.append(f'  - "{t}"')

    # Keep aliases if present
    if "aliases" in fm_fields:
        fm_lines.append("aliases:")
        # fm_fields["aliases"] may be list or string
        aliases = fm_fields.get("aliases")
        if isinstance(aliases, list):
            for a in aliases:
                fm_lines.append(f'  - "{a}"')
        elif aliases:
            fm_lines.append(f'  - "{aliases}"')

    new_fm = "---\n" + "\n".join(fm_lines) + "\n---\n\n"

    # Remove any trailing lines consisting only of hashtags or blank lines
    rest_lines = rest.splitlines()
    while rest_lines and TRAILING_HASHTAGS_PATTERN.match(rest_lines[-1]):
        rest_lines.pop()
    # Also strip trailing blank lines
    while rest_lines and rest_lines[-1].strip() == "":
        rest_lines.pop()

    # Append normalized inline tags as a single line
    if normalized_tags:
        rest_lines.append("")
        rest_lines.append(" ".join(f"#{t}" for t in normalized_tags))

    new_rest = "\n".join(rest_lines) + "\n"
    new_text = new_fm + new_rest
    write_file(path, new_text)
    write_file(path, new_text)


def generate_index(entries: List[dict]) -> str:
    lines = ["# Converted Notes Index", "", f"Generated: ", ""]
    for e in entries:
        fname = e["filename"]
        title = e.get("title") or fname
        summary = e.get("summary") or ""
        tags = e.get("tags_after") or ""
        url = e.get("url") or ""
        lines.append(f"- [{title}]({fname})")
        if summary:
            lines.append(f"  - {summary}")
        if tags:
            lines.append(f"  - Tags: {tags}")
        if url:
            lines.append(f"  - Source: {url}")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    if not os.path.isdir(CONVERTED_DIR):
        print(f"Converted directory not found: {CONVERTED_DIR}")
        return 1

    entries = []
    for fname in sorted(os.listdir(CONVERTED_DIR)):
        if not fname.endswith(".md"):
            continue
        path = os.path.join(CONVERTED_DIR, fname)
        text = read_file(path)
        fm_text, rest = parse_front_matter(text)
        fm_fields = parse_fm_fields(fm_text) if fm_text else {}

        # Collect tags from fm if present and inline
        fm_tags = fm_fields.get("tags") or []
        if isinstance(fm_tags, str) and fm_tags:
            # single string, treat as single tag
            fm_tags = [fm_tags]

        inline_tags = find_inline_tags(text)

        tags_before = list(dict.fromkeys([*fm_tags, *inline_tags]))
        tags_after = normalize_tags_list(tags_before)

        # write normalized tags back into file
        summary = fm_fields.get("summary", "")

        rewrite_file_with_tags(path, fm_text, rest, tags_after)

        entries.append({
            "filename": fname,
            "title": fm_fields.get("title", ""),
            "id": fm_fields.get("id", ""),
            "slug": fm_fields.get("slug", ""),
            "url": fm_fields.get("url", ""),
            "created": fm_fields.get("created", ""),
            "tags_before": ";".join(tags_before),
            "tags_after": ";".join(tags_after),
            "summary": summary,
        })

    # Write mapping CSV
    with open(MAPPING_CSV, "w", newline="", encoding="utf-8") as mch:
        writer = csv.writer(mch)
        writer.writerow(["filename", "title", "id", "slug", "url", "created", "tags_before", "tags_after"])
        for e in entries:
            writer.writerow([e["filename"], e["title"], e["id"], e["slug"], e["url"], e["created"], e["tags_before"], e["tags_after"]])

    # Write index
    idx_text = generate_index(entries)
    write_file(INDEX_MD, idx_text)

    print(f"Processed {len(entries)} files")
    print(f"Mapping written to: {MAPPING_CSV}")
    print(f"Index written to: {INDEX_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
