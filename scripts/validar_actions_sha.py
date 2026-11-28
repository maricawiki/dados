#!/usr/bin/env python3
"""Exigir SHA de 40 caracteres nas referências a Actions remotas."""
import re
from pathlib import Path
root=Path(__file__).resolve().parents[1]
files=sorted((root/".github/workflows").glob("*.y*ml"))
refs=0
for path in files:
    for line in path.read_text(encoding="utf-8").splitlines():
        match=re.match(r"^\s*(?:-\s*)?uses:\s*([^\s#]+)",line)
        if not match:continue
        value=match.group(1).strip("'\"")
        if value.startswith("./"):continue
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.\-/]+@[a-f0-9]{40}",value):
            raise SystemExit(f"Dependência sem SHA: {path.name}: {value}")
        refs+=1
print(f"SHA_OK: {len(files)} workflows; {refs} referências externas fixadas")
