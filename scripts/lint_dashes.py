#!/usr/bin/env python3
"""Fail if any em dash (U+2014) or en dash (U+2013) appears in copy.

Scans data, docs, src and the top-level markdown files. Binary files and
dependencies are skipped.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCAN = ["data", "docs", "src", "ingest", "scripts", "README.md", "CONTRIBUTING.md"]
EXTS = {".md", ".yaml", ".yml", ".csv", ".json", ".astro", ".ts", ".mjs", ".js", ".css", ".py", ".txt"}
BAD = {chr(0x2014): "em dash", chr(0x2013): "en dash"}


def main() -> int:
    hits = 0
    for target in SCAN:
        p = ROOT / target
        files = [p] if p.is_file() else (f for f in p.rglob("*") if f.is_file() and f.suffix in EXTS) if p.exists() else []
        for f in files:
            try:
                text = f.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for i, line in enumerate(text.splitlines(), 1):
                for ch, name in BAD.items():
                    if ch in line:
                        hits += 1
                        print(f"{f.relative_to(ROOT)}:{i}: {name}")
    print(f"lint_dashes: {hits} occurrence(s)")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
