"""Parse the STATIC_AIRES JS array out of index.html into plain Python dicts.

STATIC_AIRES is a JS object literal, not strict JSON: unquoted keys and bare
`null`. We isolate the array source and rewrite it into valid JSON rather than
pulling in a JS engine.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

_ARRAY_START_RE = re.compile(r"const\s+STATIC_AIRES\s*=\s*\[")
_UNQUOTED_KEY_RE = re.compile(r"([{,]\s*)([A-Za-z_][A-Za-z0-9_]*)(\s*:)")


@dataclass
class Aire:
    # id is None for a synthetic candidate representing a not-yet-integrated
    # "new aire" proposal (see output.load_new_aire_candidates) - it isn't a
    # real STATIC_AIRES row (yet).
    id: int | None
    nom: str
    lat: float
    lng: float
    km: str | None
    note: float | None
    equip: dict

    @property
    def equip_keys(self) -> set:
        return set(self.equip.keys())


def _extract_array_source(html: str) -> str:
    m = _ARRAY_START_RE.search(html)
    if not m:
        raise ValueError("STATIC_AIRES declaration not found in index.html")
    start = m.end() - 1  # position of the opening '['
    depth = 0
    for i in range(start, len(html)):
        c = html[i]
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                return html[start : i + 1]
    raise ValueError("Unterminated STATIC_AIRES array in index.html")


def _to_json(array_src: str) -> str:
    src = _UNQUOTED_KEY_RE.sub(r'\1"\2"\3', array_src)
    src = re.sub(r"\bnull\b", "null", src)
    src = re.sub(r",\s*([}\]])", r"\1", src)  # trailing commas
    return src


def load_aires(index_html_path: str | Path) -> list[Aire]:
    html = Path(index_html_path).read_text(encoding="utf-8")
    array_src = _extract_array_source(html)
    json_src = _to_json(array_src)
    raw = json.loads(json_src)
    aires = []
    for row in raw:
        aires.append(
            Aire(
                id=row["id"],
                nom=row["nom"],
                lat=row["lat"],
                lng=row["lng"],
                km=row.get("km"),
                note=row.get("note"),
                equip=row.get("equip") or {},
            )
        )
    return aires
