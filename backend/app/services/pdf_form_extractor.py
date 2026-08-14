import fitz


def extract_page_form_fields(
    page: fitz.Page,
) -> dict[str, str]:

    result: dict[str, str] = {}

    widgets = page.widgets()

    if widgets is None:
        return result

    for widget in widgets:

        name = str(
            widget.field_name or ""
        ).strip()

        value = str(
            widget.field_value or ""
        ).strip()

        if not name or not value:
            continue

        result[name] = value

    return result