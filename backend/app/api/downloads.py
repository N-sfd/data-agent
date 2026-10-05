"""Download headers that survive any filename.

HTTP headers are Latin-1: a document name such as "Contract (27).pdf →
SF1442 Award.pdf" cannot go into `filename="…"` as-is (the response
fails). The header carries an ASCII fallback plus the exact UTF-8 name
(RFC 6266 / RFC 5987), which browsers prefer.
"""

from __future__ import annotations

import codecs
import re
from urllib.parse import quote


def attachment_header(filename: str) -> str:
    fallback = re.sub(r'[^\x20-\x7e]|["\\]', "_", filename).strip() or "download"
    return f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{quote(filename, safe='')}"


def excel_csv(text: str | bytes) -> bytes:
    """UTF-8 CSV with a byte-order mark: without it Excel reads the file as
    Windows-1252 and "›" or "’" turn into "â€º" / "â€™"."""

    data = text.encode("utf-8") if isinstance(text, str) else text
    return data if data.startswith(codecs.BOM_UTF8) else codecs.BOM_UTF8 + data
