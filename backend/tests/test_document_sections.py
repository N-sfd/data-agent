"""Document sections (generic profile): a document's narrative — headings
with the paragraphs, bullets and lines under them — read in page order, so
a résumé or memo shows its text, not just its headings."""

from __future__ import annotations

from types import SimpleNamespace

from app.models.document import Document
from app.source_structure.models import StructuredRegion
from app.staging.profiles.generic_business_document import _document_sections

DOC = Document(id="doc-sections", original_filename="Resume.pdf", stored_filename="doc-sections.pdf")


def region(region_id: str, kind: str, text: str, y: float, x: float = 50, height: float | None = None, page: int = 1):
    lines = max(1, len(text.splitlines()))
    return StructuredRegion(
        region_id=region_id,
        region_type=kind,
        text=text,
        normalized_text=text.lower(),
        page=page,
        bbox=(x, y, x + 400, y + (height if height is not None else 12 * lines)),
    )


def sections(*regions) -> list[tuple[str, str]]:
    records = _document_sections(DOC, SimpleNamespace(regions=list(regions)))
    return [(r.values["heading"], r.values["content"]) for r in records]


def test_ruled_headings_split_sections_and_keep_their_text():
    result = sections(
        region("h1", "HEADING", "JANE DOE", 30),
        region("c1", "CONTACT_BLOCK", "Baltimore, MD | jane@example.com", 46),
        region("n1", "NARRATIVE", "Summary__________\nAnalyst with 5 years of experience.", 70),
        region("b1", "PARAGRAPH", "•\n•", 120, x=40),
        region(
            "n2",
            "NARRATIVE",
            "Experience__________\nBuilt pipelines and deep learning\nnetworks.\nLed a team of four.",
            120,
        ),
        region("j1", "HEADING", "Data Engineer", 180),
        region("p1", "PARAGRAPH", "Education__________\nState University", 220),
    )
    assert result == [
        ("JANE DOE", "Baltimore, MD | jane@example.com"),
        ("Summary", "Analyst with 5 years of experience."),
        # A wrapped line rejoins its line; bullet-only lines are dropped; a
        # heading inside a ruled section (a job title) is its text.
        ("Experience", "Built pipelines and deep learning networks.\nLed a team of four.\nData Engineer"),
        ("Education", "State University"),
    ]


def test_side_by_side_text_reads_with_its_line():
    """A date printed at the right of a block's second line reads after that
    line, not after the whole block (lines are placed within their region)."""

    result = sections(
        region("n1", "NARRATIVE", "Education_____\nState University\nMS, Computer Science\nSkills_____\nPython", 100, height=60),
        # Beside "State University" (lines are 12pt: that line spans 112-124).
        region("d1", "PARAGRAPH", "Sep 2009 - Jan 2013", 114, x=450, height=10),
        region("n0", "NARRATIVE", "Summary_____\nText.", 40),
    )
    assert result == [
        ("Summary", "Text."),
        ("Education", "State University\nSep 2009 - Jan 2013\nMS, Computer Science"),
        ("Skills", "Python"),
    ]


def test_without_ruled_headings_heading_regions_start_sections():
    result = sections(
        region("h1", "HEADING", "Purpose", 30),
        region("p1", "PARAGRAPH", "This memo explains the change.", 50),
        region("h2", "HEADING", "Next Steps", 80),
        region("p2", "PARAGRAPH", "• Review the draft\n• Sign by Friday", 100),
    )
    assert result == [
        ("Purpose", "This memo explains the change."),
        ("Next Steps", "Review the draft\nSign by Friday"),
    ]


def test_text_without_headings_is_one_text_section_and_values_are_grounded():
    records = _document_sections(
        DOC,
        SimpleNamespace(regions=[region("p1", "PARAGRAPH", "Opening remarks\nthat continue.", 30)]),
    )
    assert [(r.values["heading"], r.values["content"]) for r in records] == [("Text", "Opening remarks that continue.")]
    # The evidence is the section's own source lines (the value is checked against it).
    assert "Opening remarks" in records[0].provenance.evidence_text
    assert records[0].provenance.source_page == 1


def test_text_before_the_first_heading_is_an_introduction():
    result = sections(
        region("p1", "PARAGRAPH", "Prepared for the review board.", 30),
        region("h1", "HEADING", "Findings", 60),
        region("p2", "PARAGRAPH", "Two issues were found.", 80),
    )
    assert result == [("Introduction", "Prepared for the review board."), ("Findings", "Two issues were found.")]


def test_capital_headings_mark_sections_and_title_case_entries_stay_text():
    """No ruled headings: lines set in capitals are the sections; a degree
    or employer detected as a heading stays inside its section, and the
    contact column joins the name block instead of the text beside it."""

    result = sections(
        region("h0", "HEADING", "Anila Masood", 30),
        region("o1", "HEADING", "OBJECTIVE", 60),
        region("t1", "NARRATIVE", "Dedicated educator with a strong commitment to", 75, height=12),
        region("c1", "CONTACT_BLOCK", "anila@example.com", 76, x=450, height=12),
        region("t2", "NARRATIVE", "student success.", 88, height=12),
        region("e1", "NARRATIVE", "EDUCATION", 120),
        region("d1", "HEADING", "Master's in Urdu", 140),
        region("d2", "NARRATIVE", "Punjab University, Lahore", 155),
        region("x1", "NARRATIVE", "EXPERIENCE", 190),
        region("x2", "HEADING", "Frobel's School", 205),
        region("x3", "PARAGRAPH", "Aug 2014 – Mar 2018", 220),
    )
    assert result == [
        ("Anila Masood", "anila@example.com"),
        ("OBJECTIVE", "Dedicated educator with a strong commitment to student success."),
        ("EDUCATION", "Master's in Urdu\nPunjab University, Lahore"),
        ("EXPERIENCE", "Frobel's School\nAug 2014 – Mar 2018"),
    ]


def test_a_letter_reads_as_paragraphs_under_text():
    body = (
        "I have hands-on experience building large-scale enterprise systems with modern tools\n"
        "and a passion for applied machine learning in regulated industries.\n"
        "Currently, I am developing a large electronic health record platform for clinicians\n"
        "that manages complex data flows securely.\n"
        "Warm regards,\n"
        "Nazia"
    )
    result = sections(
        region("p0", "PARAGRAPH", "Dear,", 30),
        region("n1", "NARRATIVE", body, 50, height=72),
    )
    assert result == [
        (
            "Text",
            "Dear,\n"
            "I have hands-on experience building large-scale enterprise systems with modern tools "
            "and a passion for applied machine learning in regulated industries.\n"
            "Currently, I am developing a large electronic health record platform for clinicians "
            "that manages complex data flows securely.\n"
            "Warm regards,\nNazia",
        )
    ]


def test_flowing_documents_stack_laid_out_pages():
    """A DOCX laid out over more pages than stored keeps every page's words,
    each page continuing below the one before."""

    from app.source_structure.pdf_structure import Word
    from app.source_structure.service import _flowed_words

    class Page:
        def __init__(self, words, height):
            self.words, self.rect = words, SimpleNamespace(height=height)

    pages = [
        Page([Word("first", 10, 100, 40, 110, 10)], 800),
        Page([Word("second", 10, 50, 50, 60, 10)], 800),
        Page([Word("third", 10, 20, 40, 30, 10)], 800),
    ]
    doc = type("Doc", (), {"page_count": 3, "__getitem__": lambda self, i: pages[i]})()

    import app.source_structure.service as service

    original = service.native_words
    service.native_words = lambda page: page.words
    try:
        words = _flowed_words(doc, first=1, offset=800)
    finally:
        service.native_words = original
    assert [(w.text, w.y0) for w in words] == [("second", 850), ("third", 1620)]


def sized(region_obj, size: float):
    region_obj.structural_metadata = {"font_size": size, "line_sizes": [size] * len(region_obj.text.splitlines())}
    return region_obj


def test_large_capital_headings_win_over_capitalised_entries():
    """A template with 23pt headings also capitalises entries at body size:
    the entries stay text, the name's subtitle stays with the name, and a
    heading broken over two stacked lines is one heading."""

    result = sections(
        sized(region("n", "HEADING", "AMMARA FAZAL", 40), 30),
        sized(region("t", "HEADING", "EVENT ORGANIZER", 76), 15),
        sized(region("h1", "HEADING", "EXPERIENCE", 150), 23),
        sized(region("b1", "NARRATIVE", "Online teaching during Covid\nPAF MONTESOORI SCHOOL\nPrepared homework", 180, height=36), 11),
        sized(region("h2", "HEADING", "ADDITIONAL", 300), 23.6),
        sized(region("h3", "HEADING", "SKILLS", 324), 23.6),
        sized(region("b2", "PARAGRAPH", "Microsoft Office Tools", 360), 11),
    )
    assert result == [
        ("AMMARA FAZAL", "EVENT ORGANIZER"),
        ("EXPERIENCE", "Online teaching during Covid\nPAF MONTESOORI SCHOOL\nPrepared homework"),
        ("ADDITIONAL SKILLS", "Microsoft Office Tools"),
    ]


def test_a_two_column_page_reads_its_main_column_first():
    def column(region_obj, side):
        region_obj.structural_metadata = {"column": side}
        return region_obj

    result = sections(
        column(region("s1", "HEADING", "CONTACT", 100, x=20), "left"),
        column(region("s2", "PARAGRAPH", "me@example.com", 120, x=20), "left"),
        column(region("m1", "HEADING", "ABOUT ME", 90, x=260), "right"),
        column(region("m2", "NARRATIVE", "A professional with eight years of experience teaching art.", 110, x=260), "right"),
        column(region("m3", "HEADING", "EDUCATION", 160, x=260), "right"),
        column(region("m4", "PARAGRAPH", "B.A Fine Arts", 180, x=260), "right"),
    )
    assert [heading for heading, _ in result] == ["ABOUT ME", "EDUCATION", "CONTACT"]
