"""Staging profile definitions.

A profile declares WHAT its workbook contains (datasets, fields, stable
canonical ids, validation rules, exports) plus one adapter that reads the
profile's persisted domain tables into `RawRecord`s. Everything else —
cell validation, review status, provenance defaults, outcome, QA summary,
generic exports — is shared engine code, so adding a profile (invoice@1,
purchase_order@1, …) is a registration, not a change to the engine or UI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal

from sqlalchemy.orm import Session

from app.models.document import Document
from app.staging.models import (
    Cardinality,
    CellProvenance,
    SourceColumn,
    SourceColumnValue,
    DatasetRole,
    ExportCapability,
    ValueType,
)

# Whether a profile's adapter consumes the schema-neutral source structure
# (app/source_structure/). The extraction job builds that structure only
# when the resolved profile needs it (see app/staging/preparation.py):
#   required  the adapter reads it — always built
#   optional  the adapter works without it — built only if resolution
#             wasn't confident (the document may really be generic)
#   none      never used by this profile
SourceStructureRequirement = Literal["required", "optional", "none"]

# How a populated value must relate to its evidence to be Verified:
#   evidence  the value itself must appear in the evidence text
#   derived   the value is classified/normalized from the evidence (e.g.
#             "Basic IDIQ", "5 years"); evidence must exist, not contain it
#   system    a fact about the file itself (page count, filename)
#   none      not a business value (QA/source inspection columns) — no
#             review status at all
Grounding = Literal["evidence", "derived", "system", "none"]


@dataclass(frozen=True)
class FieldRule:
    """A field-specific business validation. `rule` is one of:
    positive_amount     money/number must be > 0
    evidence_mentions   evidence must contain one of `terms` (case-insensitive)
    pattern             value must fully match regex `pattern`
    """

    rule: str
    terms: tuple[str, ...] = ()
    pattern: str | None = None
    message: str | None = None


@dataclass(frozen=True)
class FieldDefinition:
    # Stable integration key, e.g. "contract.minimum_guarantee" or
    # "contract.clin.max_amount". Later the LEFT side of Oracle mappings.
    # Never derived from display_label.
    canonical_field: str
    # Attribute/column key in the adapter's raw record.
    key: str
    display_label: str
    value_type: ValueType = "text"
    # Expected fields that are empty are shown as Missing. Optional
    # columns of repeating records are simply blank.
    expected: bool = False
    grounding: Grounding = "evidence"
    rules: tuple[FieldRule, ...] = ()


@dataclass(frozen=True)
class DatasetDefinition:
    dataset_id: str
    display_name: str
    cardinality: Cardinality
    fields: tuple[FieldDefinition, ...]
    role: DatasetRole = "business"
    description: str | None = None
    identity_fields: tuple[str, ...] = ()


@dataclass
class RawRecord:
    """What an adapter produces for one record, before validation."""

    record_id: str
    values: dict[str, Any]
    # Row-level provenance — used for every cell that has no own entry in
    # `cell_provenance`.
    provenance: CellProvenance | None = None
    cell_provenance: dict[str, CellProvenance] = field(default_factory=dict)
    # The domain builder's own record-level QA verdict ("Verified" /
    # "Needs Review"), when it has one. A flagged record can never have
    # Verified cells.
    builder_status: str | None = None
    links_to_dataset: str | None = None
    # Table-derived records: the original column per mapped cell, and every
    # original column value (mapped or not).
    cell_source_columns: dict[str, SourceColumn] = field(default_factory=dict)
    source_columns: list[SourceColumnValue] = field(default_factory=list)


@dataclass
class AdapterResult:
    records: dict[str, list[RawRecord]]
    # Extraction outcome inputs the adapter knows about (e.g. contract_v3's
    # v3_extraction provenance record).
    outcome_provenance: dict | None = None


AdapterFn = Callable[[Session, Document], AdapterResult]


@dataclass(frozen=True)
class StagingProfile:
    profile_id: str
    profile_version: int
    display_name: str
    description: str
    # Document families (app/services/structure_detection.py
    # DOCUMENT_FAMILIES keys) this profile is the staging schema for.
    document_families: tuple[str, ...]
    datasets: tuple[DatasetDefinition, ...]
    adapter: AdapterFn
    export_capabilities: tuple[ExportCapability, ...]
    oracle_mapping_capability: Literal["planned", "available", "none"] = "none"
    # When set, the engine fills this dataset (which must use the standard
    # qa.* fields) from the validated business datasets, instead of the
    # adapter supplying QA rows.
    auto_qa_dataset: str | None = None
    source_structure: SourceStructureRequirement = "none"

    @property
    def key(self) -> str:
        return f"{self.profile_id}@{self.profile_version}"

    def dataset(self, dataset_id: str) -> DatasetDefinition:
        for dataset in self.datasets:
            if dataset.dataset_id == dataset_id:
                return dataset
        raise KeyError(f"{self.key} has no dataset {dataset_id!r}")
