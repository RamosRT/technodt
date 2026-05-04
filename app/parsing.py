from datetime import date


def optional_query_date(value: str | None) -> date | None:
    """Map query string to date; blank or missing becomes None.

    HTML ``<input type="date">`` submits an empty string when cleared, which
    must not be validated as a date.
    """
    if value is None:
        return None
    s = value.strip()
    if not s:
        return None
    return date.fromisoformat(s)
