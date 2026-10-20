import html

W = 26  # receipt width in monospace characters
MAX_ITEMS = 25  # keeps a busy day under Telegram's 4096-character message limit
BAR_CELLS = 10


def _indian_group(n: int) -> str:
    s = str(n)
    if len(s) <= 3:
        return s
    head, tail = s[:-3], s[-3:]
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    return ",".join(parts) + "," + tail


def rupees(paise: int) -> str:
    whole, frac = divmod(paise, 100)
    out = "₹" + _indian_group(whole)
    return out + f".{frac:02d}" if frac else out


def _fit(text: str, width: int) -> str:
    return text if len(text) <= width else text[: max(width - 1, 0)] + "…"


def _row(left: str, right: str) -> str:
    left = _fit(left, W - len(right) - 1)
    return left.ljust(W - len(right)) + right


def _frame(subtitle: str, body: list[str], total_paise: int) -> str:
    heavy, light = "━" * W, "─" * W
    lines = [heavy, "RUPEE TRACKER".center(W).rstrip(), _fit(subtitle, W).center(W).rstrip(), heavy]
    lines += body or ["No expenses yet".center(W).rstrip()]
    lines += [light, _row("TOTAL", rupees(total_paise)), heavy]
    return "<pre>" + html.escape("\n".join(lines)) + "</pre>"


def receipt_today(data: dict, date_label: str) -> str:
    body: list[str] = []
    for item in data["items"][:MAX_ITEMS]:
        body.append(_row(item["description"], rupees(item["amount_paise"])))
        body.append(_fit("  " + item["category"], W))
    hidden = len(data["items"]) - MAX_ITEMS
    if hidden > 0:
        body.append(f"…and {hidden} more")
    return _frame(date_label, body, data["total_paise"])


def receipt_stats(data: dict, title: str) -> str:
    body: list[str] = []
    for r in data["rows"]:
        filled = (r["percent"] * BAR_CELLS + 50) // 100  # round half up
        bar = "█" * filled + "░" * (BAR_CELLS - filled)
        body.append(f"{_fit(r['category'], 9):<9} {bar} {r['percent']:>3}%")
        body.append(" " * 10 + rupees(r["total_paise"]))
    return _frame(title, body, data["total_paise"])
