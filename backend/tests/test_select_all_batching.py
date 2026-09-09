"""Select All / batch-size regression for extraction jobs.

Users must never hit the 50-target sync API limit when selecting
1, 10, 50, 51, or 100+ human-readable targets. The job runner chunks
internally; these tests lock that contract.

Also verifies XFA internal paths stay out of Select All counts after
the multi-signal filtering fix.
"""

from app.services.extraction_job_runner import EXTRACTION_BATCH_SIZE, _chunk
from app.services.generic_kv_scanner import is_internal_form_name


def test_batch_size_remains_fifty() -> None:
    assert EXTRACTION_BATCH_SIZE == 50


def test_chunk_one_target() -> None:
    batches = _chunk(["t1"], EXTRACTION_BATCH_SIZE)
    assert batches == [["t1"]]


def test_chunk_ten_targets() -> None:
    ids = [f"t{i}" for i in range(10)]
    batches = _chunk(ids, EXTRACTION_BATCH_SIZE)
    assert len(batches) == 1
    assert len(batches[0]) == 10


def test_chunk_exactly_fifty() -> None:
    ids = [f"t{i}" for i in range(50)]
    batches = _chunk(ids, EXTRACTION_BATCH_SIZE)
    assert len(batches) == 1
    assert len(batches[0]) == 50


def test_chunk_fifty_one() -> None:
    ids = [f"t{i}" for i in range(51)]
    batches = _chunk(ids, EXTRACTION_BATCH_SIZE)
    assert len(batches) == 2
    assert len(batches[0]) == 50
    assert len(batches[1]) == 1
    assert [item for batch in batches for item in batch] == ids


def test_chunk_one_hundred_plus() -> None:
    ids = [f"t{i}" for i in range(117)]
    batches = _chunk(ids, EXTRACTION_BATCH_SIZE)
    assert len(batches) == 3
    assert [len(batch) for batch in batches] == [50, 50, 17]
    assert [item for batch in batches for item in batch] == ids


def test_select_all_excludes_internal_xfa_paths() -> None:
    """After XFA filtering, Select All must only count human-readable keys."""
    discovered = [
        "Solicitation No.",
        "Contract Number",
        "topmostSubform[0].Page1[0].PG11I[0]",
        "CheckBox1",
        "WAWF Payment Office",
        "form1[0].TextField[3]",
        "Effective Date",
    ]
    selectable = [name for name in discovered if not is_internal_form_name(name)]
    assert selectable == [
        "Solicitation No.",
        "Contract Number",
        "WAWF Payment Office",
        "Effective Date",
    ]
    assert all(not is_internal_form_name(name) for name in selectable)
