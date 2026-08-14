def build_page_context(
    pages,
    *,
    maximum_characters: int = 60000,
) -> str:

    sections: list[str] = []

    used_characters = 0

    for page in pages:

        section = (
            f"\n"
            f"===== PDF PAGE "
            f"{page.page_number} =====\n\n"
            f"{page.final_text or ''}\n"
        )

        if page.form_fields_json:

            section += (
                "\nFORM FIELDS:\n"
                f"{page.form_fields_json}\n"
            )

        if page.tables_json:

            section += (
                "\nTABLES:\n"
                f"{page.tables_json}\n"
            )

        remaining = (
            maximum_characters
            - used_characters
        )

        if remaining <= 0:
            break

        section = section[
            :remaining
        ]

        sections.append(
            section
        )

        used_characters += len(
            section
        )

    return "\n".join(
        sections
    )
