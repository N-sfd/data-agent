import fitz

from app.services.generic_kv_scanner import is_internal_form_name


def extract_page_form_fields(
    page: fitz.Page,
) -> dict[str, str]:
    """
    Extract filled AcroForm/XFA widgets for a page.

    Prefer the widget's visible field_label when present. Raw internal
    paths (topmostSubform[0]...) are still stored for provenance so the
    KV scanner can attempt nearby-label mapping, but they are never
    promoted as human-facing targets by themselves.
    """
    result: dict[str, str] = {}

    widgets = page.widgets()
    if widgets is None:
        return result

    for widget in widgets:
        name = str(widget.field_name or "").strip()
        value = str(widget.field_value or "").strip()
        if not name or not value:
            continue

        visible_label = str(getattr(widget, "field_label", None) or "").strip()
        if (
            visible_label
            and not is_internal_form_name(visible_label)
        ):
            result[visible_label] = value
            continue

        # Keep raw path for provenance / nearby-label mapping only.
        result[name] = value

    return result
