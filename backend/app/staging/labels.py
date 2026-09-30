"""Source label → display label.

A staged value keeps its label exactly as the document printed it
(`source_label`, provenance). What the UI shows is the professional
`display_label`: the same wording, cleaned — separators dropped,
abbreviations spelled out, capitalisation normalised. Meaning is never
changed here; a profile's vocabulary may choose a different display label
when the label's meaning is established (e.g. "whose date of birth is" →
"Date of Birth").
"""

from __future__ import annotations

import re

# Kept upper-case wherever they appear.
_ACRONYMS = {
    "id", "gpa", "cgpa", "sgpa", "dob", "ssn", "po", "us", "uk", "usa", "cp", "ap", "ib",
    "gcse", "sat", "act", "ged", "url", "vat", "gst", "tin", "ein", "mba", "bsc", "msc", "phd",
}
_SMALL_WORDS = {"of", "and", "the", "in", "for", "to", "by", "on", "at", "or", "a", "an", "per", "with"}


def _title_word(word: str, first: bool) -> str:
    bare = re.sub(r"[^A-Za-z]", "", word).lower()
    if bare in _ACRONYMS:
        return word.upper()
    # Short or vowel-less capitals are abbreviations ("DTP", "MMR", "HS").
    if word.isupper() and bare and bare not in _SMALL_WORDS and (len(bare) <= 3 or not re.search(r"[aeiouy]", bare)):
        return word
    if not first and bare in _SMALL_WORDS:
        return word.lower()
    return word[:1].upper() + word[1:].lower()


def humanize_label(label: str | None) -> str:
    """'Certificate No.' → 'Certificate Number'; 'Attempt(s)' → 'Attempt';
    'UNIT CODE' → 'Unit Code'; 'Student ID#:' → 'Student ID'."""

    text = re.sub(r"\s+", " ", label or "").strip()
    # Leading/trailing separators and OCR rule glyphs are layout, not wording.
    text = re.sub(r"^[\s:=\-–—|_*#.]+", "", text)
    text = re.sub(r"[\s:=\-–—|_*]+$", "", text)
    # Plural markers: "Attempt(s)" → "Attempt".
    text = re.sub(r"(?<=[A-Za-z])\((?:s|es)\)", "", text, flags=re.I)
    # Number abbreviations: "No." / "No" / "#" as a word → "Number".
    text = re.sub(r"(?<![A-Za-z])(?:No|Nbr|Num)\.?(?![A-Za-z])", "Number", text, flags=re.I)
    text = re.sub(r"\s*#\s*$", " Number", text)
    text = re.sub(r"\bID\s*Number\b", "ID", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip(" .")
    if not text:
        return ""
    letters = [ch for ch in text if ch.isalpha()]
    uniform = letters and (all(ch.isupper() for ch in letters) or all(ch.islower() for ch in letters))
    words = text.split(" ")
    if uniform:
        words = [_title_word(word, index == 0) for index, word in enumerate(words)]
    else:
        # Mixed case is the document's own styling; only fix acronyms and
        # the first letter.
        words = [
            word.upper() if re.sub(r"[^A-Za-z]", "", word).lower() in _ACRONYMS else word
            for word in words
        ]
        words[0] = words[0][:1].upper() + words[0][1:]
    return " ".join(words)
