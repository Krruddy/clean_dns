#!/usr/bin/env python3
"""Prepend a $ORIGIN directive to every BIND master zone file that lacks one."""

import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass
class Zone:
    name: str
    zone_type: str
    file: str

    @property
    def origin(self) -> str:
        return self.name if self.name.endswith('.') else f"{self.name}."


def run_named_checkconf() -> str:
    result = subprocess.run(
        ["named-checkconf", "-p"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        sys.exit(f"named-checkconf failed:\n{result.stderr.strip()}")
    return result.stdout


def _extract_block(text: str, open_brace: int) -> str:
    """Return the content between the '{' at open_brace and its matching '}'."""
    depth = 0
    for i in range(open_brace, len(text)):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                return text[open_brace + 1:i]
    raise ValueError("Unmatched brace in named-checkconf output")


def parse_zones(config: str) -> List[Zone]:
    zones: List[Zone] = []
    zone_header_re = re.compile(r'zone\s+"([^"]+)"\s+\w+\s*\{', re.IGNORECASE)

    for m in zone_header_re.finditer(config):
        block = _extract_block(config, m.end() - 1)
        type_m = re.search(r'\btype\s+(\w+)\s*;', block, re.IGNORECASE)
        file_m = re.search(r'\bfile\s+"([^"]+)"\s*;', block, re.IGNORECASE)
        if type_m and file_m:
            zones.append(Zone(
                name=m.group(1),
                zone_type=type_m.group(1).lower(),
                file=file_m.group(1),
            ))
    return zones


def prepend_origin(zone: Zone) -> None:
    path = Path(zone.file)
    try:
        content = path.read_text()
    except OSError as exc:
        print(f"  ERROR  {zone.name}: cannot read {zone.file}: {exc}", file=sys.stderr)
        return

    if re.search(r'^\$ORIGIN\b', content, re.IGNORECASE | re.MULTILINE):
        print(f"  SKIP   {zone.name}: $ORIGIN already present")
        return

    new_content = f"$ORIGIN {zone.origin}\n{content}"

    try:
        fd, tmp_path = tempfile.mkstemp(dir=path.parent)
        try:
            with os.fdopen(fd, 'w') as fh:
                fh.write(new_content)
            os.chmod(tmp_path, path.stat().st_mode)
            os.replace(tmp_path, path)
        except Exception:
            os.unlink(tmp_path)
            raise
    except OSError as exc:
        print(f"  ERROR  {zone.name}: cannot write {zone.file}: {exc}", file=sys.stderr)
        return

    print(f"  ADDED  $ORIGIN {zone.origin}  →  {zone.file}")


def main() -> None:
    config = run_named_checkconf()
    zones = parse_zones(config)

    masters = [z for z in zones if z.zone_type == 'master']
    print(f"Zones found: {len(zones)} total, {len(masters)} master")

    for zone in masters:
        prepend_origin(zone)


if __name__ == "__main__":
    main()
