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


def today_text(data: dict) -> str:
    if not data["items"]:
        return "No expenses yet today."
    lines = ["Today"]
    for i in data["items"]:
        lines.append(f"{i['description']} {rupees(i['amount_paise'])} ({i['category']})")
    lines.append(f"Total {rupees(data['total_paise'])}")
    return "\n".join(lines)


def stats_text(data: dict, title: str) -> str:
    if not data["rows"]:
        return f"{title}\nNo expenses yet."
    lines = [title]
    for r in data["rows"]:
        lines.append(f"{r['category']} {rupees(r['total_paise'])} ({r['percent']}%)")
    lines.append(f"Total {rupees(data['total_paise'])}")
    return "\n".join(lines)
