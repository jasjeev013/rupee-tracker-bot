import re
from dataclasses import dataclass
from decimal import Decimal

MAX_TEXT_LEN = 200
MAX_AMOUNT_PAISE = 1_00_00_000 * 100

_AMOUNT = re.compile(
    r"(?<![A-Za-z])(?:₹|rs\.?)?\s*(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d{1,2}))?",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ParsedExpense:
    description: str
    amount_paise: int


def parse_message(text: str) -> ParsedExpense | None:
    if len(text) > MAX_TEXT_LEN:
        return None
    matches = list(_AMOUNT.finditer(text))
    if not matches:
        return None
    m = matches[-1]
    if m.start() > 0 and text[m.start() - 1] == "-":
        return None
    amount = Decimal(m.group(1).replace(",", "") + "." + (m.group(2) or "0"))
    paise = int(amount * 100)
    if paise <= 0 or paise > MAX_AMOUNT_PAISE:
        return None
    description = " ".join((text[: m.start()] + " " + text[m.end():]).split())
    if not description:
        return None
    return ParsedExpense(description, paise)
