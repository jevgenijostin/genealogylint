"""Inclusive Gregorian intervals; None represents an unbounded endpoint."""
import calendar
import re
from dataclasses import dataclass
from datetime import date, timedelta

MONTHS = "JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split()


@dataclass(frozen=True)
class DateRange:
    lower: date | None
    upper: date | None
    text: str


def parse_date(value: str) -> DateRange:
    value = " ".join(value.upper().split())
    def plain(text):
        parts = text.split()
        if not re.fullmatch(r"(?:\d{1,2} )?(?:[A-Z]{3} )?\d{4}", text):
            raise ValueError(f"Unsupported date: {text}")
        year = int(parts[-1])
        month = MONTHS.index(parts[-2]) + 1 if len(parts) > 1 else None
        day = int(parts[0]) if len(parts) == 3 else None
        return (date(year, month or 1, day or 1),
                date(year, month or 12, day or (calendar.monthrange(year, month)[1] if month else 31)))
    if value.startswith("BET "):
        pieces = value[4:].split(" AND ")
        if len(pieces) != 2:
            raise ValueError(f"Invalid date range: {value}")
        low, high = plain(pieces[0])[0], plain(pieces[1])[1]
    else:
        qualifier = value[:3] if value[:4] in ("ABT ", "BEF ", "AFT ") else None
        low, high = plain(value[4:] if qualifier else value)
        if qualifier == "BEF":
            low, high = None, low - timedelta(days=1)
        elif qualifier == "AFT":
            low, high = high + timedelta(days=1), None
        elif qualifier == "ABT":
            low, high = date(max(1, low.year - 1), 1, 1), date(min(9999, high.year + 1), 12, 31)
    if low and high and low > high:
        raise ValueError(f"Reversed date range: {value}")
    return DateRange(low, high, value)


def before(a, b):
    return bool(a and b and a.upper and b.lower and a.upper < b.lower)


def age(earlier, later):
    return later.year - earlier.year - ((later.month, later.day) < (earlier.month, earlier.day))
