"""academic_transcript@1's controlled vocabulary.

Owned by the transcript profile, never by the universal source extractor:
the extractor (or the profile's own line reconstruction) reports "a label
'Admission No' has value '09/04979'"; this module decides that label means
transcript.student.admission_number and how it is presented.

Matching is EXACT on a normalized label (`normalize_label`), so unrelated
wording is never merged by accident. Nothing here names an institution,
a student or a course: only the generic wording of academic records.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

STUDENT = "Student Information"
PROGRAM = "Program Information"
RECORD = "Academic Record"
SUMMARY = "Academic Summary"
INSTITUTION = "Institution Information"
ACCREDITATION = "Accreditation"
GRADING = "Grading System"
REQUIREMENTS = "Graduation Requirements"
HONORS = "Honors & Awards"
ACTIVITIES = "Activities"
NOTES = "Notes"
RECOMMENDATION = "Recommendation"
CERTIFICATION = "Certification"
OTHER = "Other Information"

_PARENS = re.compile(r"\([^)]*\)")


def normalize_label(label: str | None) -> str:
    """'Date of Birth:' → 'date of birth'; 'Admission No' → 'admission
    number'; 'Program / Degree Name' → 'program degree name';
    'Attempt(s)' → 'attempt'."""

    text = _PARENS.sub(" ", (label or "").lower())
    text = text.replace("#", " number ").replace("&", " and ")
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    text = re.sub(r"\b(no|num|nbr)\b", "number", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\bnumber number\b", "number", text)
    return text


@dataclass(frozen=True)
class FieldSpec:
    field_id: str
    display_label: str
    category: str


def _spec(field_id: str, display: str, category: str, *labels: str) -> dict[str, FieldSpec]:
    spec = FieldSpec(field_id, display, category)
    return {label: spec for label in labels}


# --- scalar label → field ----------------------------------------------------------

FIELD_ALIASES: dict[str, FieldSpec] = {
    # Student
    **_spec("transcript.student.name", "Student Name", STUDENT,
            "name", "names", "student name", "student names", "full name", "student", "name of student",
            "name of the student", "students name", "student s name", "candidate name", "candidate",
            "name of candidate", "learner name", "pupil name", "record of"),
    **_spec("transcript.student.id", "Student ID", STUDENT,
            "student id", "student id number", "id", "id number", "student number", "student identification number",
            "matriculation number", "matric number", "learner id", "pupil id", "enrollment number",
            "enrolment number", "index number"),
    **_spec("transcript.student.registration_number", "Registration Number", STUDENT,
            "registration number", "reg number", "registration id"),
    **_spec("transcript.student.admission_number", "Admission Number", STUDENT, "admission number", "admission"),
    **_spec("transcript.student.roll_number", "Roll Number", STUDENT, "roll number", "roll"),
    **_spec("transcript.student.record_number", "Record Number", STUDENT, "record number", "record id"),
    **_spec("transcript.student.certificate_number", "Certificate Number", STUDENT,
            "certificate number", "certificate serial number"),
    **_spec("transcript.student.state_id", "State ID", STUDENT, "state id", "state id number", "state student id"),
    **_spec("transcript.student.date_of_birth", "Date of Birth", STUDENT,
            "date of birth", "birth date", "birthdate", "dob", "d o b", "born", "born on",
            "date of birth is", "whose date of birth is"),
    **_spec("transcript.student.gender", "Gender", STUDENT, "gender", "sex"),
    **_spec("transcript.student.address", "Address", STUDENT,
            "address", "home address", "student address", "mailing address", "permanent address"),
    **_spec("transcript.student.phone", "Phone", STUDENT,
            "phone", "phone number", "telephone", "telephone number", "tel", "mobile", "mobile number",
            "contact number", "cell"),
    **_spec("transcript.student.email", "Email", STUDENT, "email", "email address", "e mail", "e mail address"),
    **_spec("transcript.student.parent_guardian", "Parent / Guardian Name", STUDENT,
            "parent guardian", "parent", "guardian", "parents", "parent or guardian", "parent guardian name",
            "son daughter of", "son or daughter of", "child of", "ward of"),
    **_spec("transcript.student.grade_level", "Grade Level", STUDENT, "grade", "grade level", "current grade"),
    **_spec("transcript.student.counselor", "Counselor", STUDENT,
            "counselor", "counsellor", "advisor", "adviser", "academic advisor", "academic adviser"),
    # Program
    **_spec("transcript.program.institution", "Institution", PROGRAM,
            "institution", "institution name", "name of institution", "university", "college", "school",
            "school name", "name of school", "school of record", "academy"),
    **_spec("transcript.program.district", "District", PROGRAM, "district", "school district"),
    **_spec("transcript.program.faculty", "Faculty / School", PROGRAM, "faculty", "faculty school", "school faculty"),
    **_spec("transcript.program.department", "Department", PROGRAM, "department", "dept"),
    **_spec("transcript.program.program", "Program / Degree", PROGRAM,
            "program", "programme", "degree", "program degree", "program degree name", "degree name",
            "degree program", "program of study", "programme of study", "course of study", "course",
            "degree awarded", "degree and major awarded", "award", "qualification"),
    **_spec("transcript.program.major", "Major", PROGRAM,
            "major", "major field", "concentration", "specialization", "specialisation", "major subject"),
    **_spec("transcript.program.minor", "Minor", PROGRAM, "minor", "minor subject"),
    **_spec("transcript.program.degree_plan", "Degree Plan", PROGRAM, "degree plan", "study plan"),
    **_spec("transcript.program.graduation_year", "Graduation Year", PROGRAM,
            "year of graduation", "graduation year", "class of", "year of completion", "passing year",
            "year of passing"),
    **_spec("transcript.program.graduation_date", "Graduation Date", PROGRAM,
            "graduation date", "date of graduation", "date graduated", "graduated", "graduated on",
            "expected graduation", "expected graduation date", "completion date"),
    **_spec("transcript.program.start_date", "Start Date", PROGRAM,
            "start date", "entry date", "date of entry", "admission date", "date of admission",
            "enrollment date", "enrolment date", "date enrolled"),
    **_spec("transcript.program.leave_date", "Leave Date", PROGRAM,
            "leave date", "exit date", "withdrawal date", "date left", "date of leaving"),
    **_spec("transcript.program.district_entry_date", "District Entry Date", PROGRAM, "district enter", "district entry"),
    **_spec("transcript.program.school_entry_date", "School Entry Date", PROGRAM, "school enter", "school entry"),
    # Academic summary
    **_spec("transcript.summary.cumulative_gpa", "Cumulative GPA", SUMMARY,
            "cumulative gpa", "cgpa", "cum gpa", "overall gpa", "cumulative grade point average", "gpa",
            "grade point average", "final gpa", "career gpa", "cumulative gpa weighted"),
    **_spec("transcript.summary.term_gpa", "Term GPA", SUMMARY,
            "term gpa", "semester gpa", "academic gpa", "yearly gpa", "sgpa", "year gpa", "annual gpa"),
    **_spec("transcript.summary.weighted_gpa", "Weighted GPA", SUMMARY, "weighted gpa", "weighted cumulative gpa"),
    **_spec("transcript.summary.unweighted_gpa", "Unweighted GPA", SUMMARY, "unweighted gpa"),
    **_spec("transcript.summary.total_credits", "Total Credits", SUMMARY,
            "total credits", "total credit", "total credits earned", "total earned credits", "total units",
            "total credit hours", "total hours", "total credits completed", "cumulative credits"),
    **_spec("transcript.summary.credits_earned", "Credits Earned", SUMMARY,
            "credits earned", "credit earned", "earned credits", "units earned", "hours earned",
            "credit completed", "credits completed"),
    **_spec("transcript.summary.credits_attempted", "Credits Attempted", SUMMARY,
            "credit attempted", "credits attempted", "units attempted", "hours attempted", "attempted credits"),
    **_spec("transcript.summary.gpa_credits", "GPA Credits", SUMMARY, "gpa credits", "gpa hours", "gpa units"),
    **_spec("transcript.summary.quality_points", "Quality Points", SUMMARY,
            "quality points", "gpa points", "total grade points", "total quality points", "grade points total"),
    **_spec("transcript.summary.class_rank", "Class Rank", SUMMARY, "class rank", "rank in class", "rank"),
    **_spec("transcript.summary.academic_standing", "Academic Standing", SUMMARY, "academic standing", "standing"),
    **_spec("transcript.summary.graduation_status", "Graduation Status", SUMMARY, "graduation status"),
    **_spec("transcript.summary.honors", "Honors", SUMMARY, "honors", "honours", "academic honors", "distinction"),
    **_spec("transcript.summary.deans_list", "Dean's List", SUMMARY, "dean s list", "deans list"),
    **_spec("transcript.summary.result", "Result", SUMMARY, "result", "final result", "overall result", "division"),
    # Other information
    **_spec("transcript.other.issue_date", "Issue Date", CERTIFICATION,
            "date issued", "date of issue", "issue date", "issued on", "date of issuance", "issued"),
    **_spec("transcript.other.recommendation", "Recommendation", RECOMMENDATION, "recommendation"),
    **_spec("transcript.other.transcript_number", "Transcript Number", OTHER,
            "transcript number", "transcript id", "serial number", "document number"),
    **_spec("transcript.other.accreditation", "Accreditation", ACCREDITATION,
            "accreditation", "accredited by", "accrediting body"),
    **_spec("transcript.institution.website", "Website", INSTITUTION, "website", "web site", "web", "url"),
    **_spec("transcript.institution.contact", "Contact", INSTITUTION, "contact", "contact person"),
}

# Student contact fields that describe the INSTITUTION when they sit in its
# letterhead or under an institution section heading.
INSTITUTION_VARIANTS: dict[str, FieldSpec] = {
    "transcript.student.name": FieldSpec("transcript.program.institution", "Institution", PROGRAM),
    "transcript.student.address": FieldSpec("transcript.institution.address", "Institution Address", INSTITUTION),
    "transcript.student.phone": FieldSpec("transcript.institution.phone", "Institution Phone", INSTITUTION),
    "transcript.student.email": FieldSpec("transcript.institution.email", "Institution Email", INSTITUTION),
}

# A GPA printed inside one term's block is that term's GPA.
TERM_SCOPED: dict[str, FieldSpec] = {
    "transcript.summary.cumulative_gpa": FieldSpec("transcript.summary.term_gpa", "Term GPA", SUMMARY),
    "transcript.summary.total_credits": FieldSpec("transcript.summary.credits_earned", "Credits Earned", SUMMARY),
}

# Labels that are page furniture, not data.
IGNORED_LABELS = {"page", "signature", "signed", "sign", "date signed", "seal", "stamp"}

# Everyday words that are labels only when the layout says so: printed
# with a separator ("School: …"), as the caption of a two-run label/value
# row, or in a row of captions above their values. Alone beside other text
# ("University  Registrar" under a signature line) they are not labels.
WEAK_LABELS = {
    "university", "college", "school", "academy", "institution", "student", "name", "names", "record of",
    "born", "result", "standing", "rank", "honors", "honours", "distinction", "award", "contact", "issued",
    "admission", "roll", "grade", "course", "program", "programme", "degree", "qualification", "division",
    "major", "minor", "department", "dept", "faculty", "district", "phone", "tel", "cell", "mobile", "email",
    "address", "web", "url", "website", "parent", "parents", "guardian", "graduated", "candidate", "id",
}


def is_weak_label(label: str) -> bool:
    return normalize_label(label) in WEAK_LABELS


def field_spec(label: str) -> FieldSpec | None:
    return FIELD_ALIASES.get(normalize_label(label))


# --- course-table headers ------------------------------------------------------------

@dataclass(frozen=True)
class ColumnRole:
    role: str
    display_label: str


def _columns(role: str, display: str, *headers: str) -> dict[str, ColumnRole]:
    column = ColumnRole(role, display)
    return {header: column for header in headers}


COLUMN_ALIASES: dict[str, ColumnRole] = {
    **_columns("code", "Course Code",
               "course code", "course number", "course id", "crs id", "code", "subject code", "module code",
               "course num", "course nbr", "class code", "paper code", "course no", "crs number"),
    **_columns("code", "Unit Code", "unit code", "unit number"),
    **_columns("department", "Department", "dept", "department"),
    **_columns("title", "Course Title",
               "course title", "title", "course name", "subject", "subject name", "subjects", "course",
               "courses", "module", "module title", "module name", "course description", "description",
               "paper", "paper name", "class", "class name", "subject title"),
    **_columns("title", "Unit Name", "unit name", "unit title"),
    **_columns("term", "Term", "term", "session", "period", "quarter", "trimester"),
    **_columns("term", "Semester", "semester", "sem"),
    **_columns("academic_year", "Academic Year", "academic year", "year", "school year", "session year"),
    **_columns("grade_level", "Grade Level", "grade level", "level", "grade lvl"),
    **_columns("credits", "Credits",
               "credits", "credit", "cr", "credit units", "cred", "credit value", "crs", "cr hrs", "credit points"),
    **_columns("credits", "Credit Hours", "credit hours", "credit hrs", "hours", "hrs", "units", "unit value"),
    **_columns("contact_hours", "Contact Hours", "contact hours", "contact hrs", "contact"),
    **_columns("credits_attempted", "Credits Attempted",
               "attempted", "attempt", "units attempted", "credits attempted", "credit attempted",
               "attempted credits", "hours attempted", "att", "attempted units"),
    **_columns("credits_earned", "Credits Earned",
               "earned", "units earned", "credits earned", "credit earned", "earned credits", "hours earned",
               "ern", "earned units"),
    **_columns("credits_earned", "Credits Completed", "complete", "completed", "credits completed"),
    **_columns("grade", "Grade",
               "grade", "grades", "final grade", "letter grade", "grd", "gr", "result", "final result"),
    **_columns("grade", "Mark", "mark"),
    **_columns("grade_points", "Grade Points",
               "grade points", "points", "quality points", "pts", "gpa points", "grade point", "qp",
               "grade pts", "quality pts"),
    **_columns("score", "Marks",
               "marks", "score", "marks obtained", "obtained marks", "mark obtained", "percentage", "percent",
               "total marks", "scores", "obtained"),
    **_columns("max_score", "Maximum Marks", "max marks", "maximum marks", "full marks", "out of", "max"),
    **_columns("theory", "Theory", "theory"),
    **_columns("practical", "Practical", "practical"),
}

# Roles that identify a course (a row is a course only with one of these).
ITEM_ROLES = {"code", "title"}
# Roles that report a result for the course.
RESULT_ROLES = {
    "credits", "contact_hours", "credits_attempted", "credits_earned", "grade", "grade_points",
    "score", "theory", "practical", "max_score",
}
CONTEXT_ROLES = {"term", "academic_year", "grade_level"}


def column_role(header: str) -> ColumnRole | None:
    return COLUMN_ALIASES.get(normalize_label(header))


# --- section headings ---------------------------------------------------------------

@dataclass(frozen=True)
class Section:
    category: str
    entry_label: str


def _sections(category: str, entry: str, *headings: str) -> dict[str, Section]:
    section = Section(category, entry)
    return {heading: section for heading in headings}


SECTION_HEADINGS: dict[str, Section] = {
    **_sections(GRADING, "Grading Scale",
                "grading scale", "grading system", "key to grading system", "grading key", "grade scale",
                "grading", "grade key", "key to grades", "grading policy", "grade scale key", "grading legend",
                "key to grading"),
    **_sections(REQUIREMENTS, "Requirement",
                "graduation requirements", "requirements", "credit summary", "add on requirements",
                "degree requirements", "requirement summary"),
    **_sections(ACTIVITIES, "Activity",
                "extra curricular activities", "extracurricular activities", "activities", "co curricular activities"),
    **_sections(HONORS, "Award",
                "notable awards", "awards", "honors and awards", "honours and awards", "achievements",
                "awards and honors", "honors", "honours"),
    **_sections(NOTES, "Note", "notes", "note", "remarks", "comments", "commentary", "notes and remarks"),
    **_sections(CERTIFICATION, "Certification", "certification", "certificate", "attestation"),
    **_sections(RECOMMENDATION, "Recommendation", "recommendation", "recommendations"),
    **_sections(ACCREDITATION, "Accreditation", "accreditation", "accreditations"),
    **_sections(OTHER, "Test", "test taken", "tests", "test results", "standardized tests", "test scores",
                "tests taken"),
    **_sections(OTHER, "Health Record", "immunization data", "immunizations", "immunization"),
    **_sections(SUMMARY, "Summary",
                "academic summary", "summary by grade", "cumulative summary", "gpa summary", "summary",
                "academic totals"),
}

# Headings that set context for the label/value pairs beneath them.
STUDENT_CONTEXT = {"student information", "student", "student details", "student data", "personal information",
                   "student record", "student profile"}
INSTITUTION_CONTEXT = {"school information", "institution information", "school of record", "school",
                       "institution", "school details", "institution details", "issuing institution"}
PROGRAM_CONTEXT = {"program information", "degree information", "programme information", "program details"}


def section_for(text: str) -> Section | None:
    return SECTION_HEADINGS.get(normalize_label(text))


# --- value shapes --------------------------------------------------------------------

ACADEMIC_YEAR = re.compile(r"\b((?:19|20)\d{2})\s*[-/–]\s*((?:19|20)?\d{2})\b")
GRADE_LEVEL = re.compile(
    r"\b(\d{1,2})\s*(?:st|nd|rd|th)?\s*(?:grade|gr\.?|std|standard|form|class)\b"
    r"|\bgrade\s*(\d{1,2})\b|\b(freshman|sophomore|junior|senior)\s*(?:year)?\b",
    re.I,
)
TERM = re.compile(
    r"\b(?:fall|spring|summer|winter|autumn)(?:\s+(?:term|semester|quarter|session))?(?:\s+(?:19|20)\d{2})?\b"
    r"|\b(?:semester|term|quarter|trimester)\s*(?:[ivx]{1,4}|\d{1,2})\b"
    r"|\b(?:first|second|third|fourth|1st|2nd|3rd|4th)\s+(?:semester|term|quarter|year)\b",
    re.I,
)
# A letter grade, optionally with a numeric score: "A-", "B+", "94 (A)", "Pass".
LETTER_GRADE = re.compile(r"^(?:\d{1,3}(?:\.\d+)?\s*)?\(?\s*(?:[A-F][+-]?|[SUPEIWN]|NM|NG|IP|AU|CR|NC|PASS|FAIL)\s*\)?$", re.I)
NUMERIC = re.compile(r"^[\s$]*-?\d[\d,]*(?:\.\d+)?\s*%?$")
SCORE = re.compile(r"^\d{1,4}(?:\.\d+)?\s*/\s*\d{1,4}(?:\.\d+)?$")

TOTAL_ROW = re.compile(
    r"^\s*(?:\*\s*)?(?:(?:semester|term|year|yearly|annual|cumulative|grand|overall|career)\s+)?totals?\b"
    r"|^\s*total\s*/\s*summary\b|^\s*summary\b|^\s*(?:weighted|unweighted|cumulative|term|semester)?\s*gpa\b",
    re.I,
)
TITLE_WORDS = re.compile(
    r"\b(?:academic\s+)?transcript\b|\bacademic\s+record\b|\bstatement\s+of\s+(?:marks|grades|results)\b"
    r"|\bmark\s*sheet\b|\bgrade\s+report\b|\breport\s+card\b|\brecord\s+of\s+(?:achievement|study)\b",
    re.I,
)
INSTITUTION_WORDS = re.compile(
    r"\b(?:university|college|school|academy|institute|institution|polytechnic|conservatory|seminary|district)\b",
    re.I,
)
CERTIFICATION_WORDS = re.compile(
    r"\b(?:official\s+transcript|this\s+transcript|valid\s+transcript|invalid\s+unless|not\s+(?:a\s+)?valid|"
    r"hereby\s+(?:self-?)?certif|certify|certified|attest|complete\s+and\s+accurate|issued\s+without|"
    r"cannot\s+be\s+released|educational\s+(?:rights|act))",
    re.I,
)
SIGNATORY_WORDS = re.compile(
    r"\b(?:registrar|representative|administrator|principal|dean|headmaster|headmistress|director|controller"
    r"|examinations?\s+officer|superintendent)\b",
    re.I,
)
