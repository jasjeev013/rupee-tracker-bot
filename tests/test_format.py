import pytest

from app.bot.format import W, receipt_stats, receipt_today, rupees


@pytest.mark.parametrize(
    "paise,text",
    [(4000, "₹40"), (1250, "₹12.50"), (12000000, "₹1,20,000"), (120000, "₹1,200"), (5, "₹0.05"), (0, "₹0")],
)
def test_rupees(paise, text):
    assert rupees(paise) == text


def body(html: str) -> list[str]:
    assert html.startswith("<pre>") and html.endswith("</pre>")
    return html[len("<pre>") : -len("</pre>")].split("\n")


TODAY = {
    "items": [
        {"description": "metro", "amount_paise": 4000, "category": "Travel"},
        {"description": "lunch", "amount_paise": 25000, "category": "Food"},
    ],
    "total_paise": 29000,
}


def test_receipt_today_layout():
    lines = body(receipt_today(TODAY, "Tue, 20 Oct 2026"))
    assert lines[0] == "━" * W
    assert lines[1].strip() == "RUPEE TRACKER"
    assert lines[2].strip() == "Tue, 20 Oct 2026"
    assert lines[4] == "metro" + " " * (W - len("metro") - len("₹40")) + "₹40"
    assert lines[5] == "  Travel"
    assert lines[6].startswith("lunch") and lines[6].endswith("₹250")
    assert lines[8] == "─" * W
    assert lines[9] == "TOTAL" + " " * (W - len("TOTAL") - len("₹290")) + "₹290"
    assert lines[-1] == "━" * W
    assert all(len(line) <= W for line in lines)


def test_receipt_today_empty():
    out = receipt_today({"items": [], "total_paise": 0}, "Tue, 20 Oct 2026")
    assert "No expenses yet" in out and "TOTAL" in out


def test_receipt_escapes_html_and_truncates_long_descriptions():
    data = {
        "items": [{"description": "<b>" + "x" * 80, "amount_paise": 100, "category": "A&B"}],
        "total_paise": 100,
    }
    out = receipt_today(data, "d")
    assert "<b>" not in out.replace("<pre>", "")
    assert "&lt;b&gt;" in out and "A&amp;B" in out
    assert "…" in out
    # visible width (after unescaping) never exceeds W
    import html

    assert all(len(line) <= W for line in html.unescape(out[5:-6]).split("\n"))


def test_receipt_today_caps_item_count():
    items = [{"description": f"i{n}", "amount_paise": 100, "category": "Food"} for n in range(60)]
    out = receipt_today({"items": items, "total_paise": 6000}, "d")
    assert "and 35 more" in out
    assert "₹60" in out  # total still covers every entry
    assert len(out) < 4096


STATS = {
    "rows": [
        {"category": "Food", "total_paise": 180000, "percent": 45},
        {"category": "Travel", "total_paise": 120000, "percent": 30},
    ],
    "total_paise": 400000,
}


def test_receipt_stats_layout():
    lines = body(receipt_stats(STATS, "This month"))
    assert lines[2].strip() == "This month"
    assert lines[4] == "Food      " + "█" * 5 + "░" * 5 + "  45%"
    assert lines[5] == " " * 10 + "₹1,800"
    assert lines[6].startswith("Travel") and "30%" in lines[6]
    assert lines[-2].startswith("TOTAL") and lines[-2].endswith("₹4,000")
    assert all(len(line) <= W for line in lines)


def test_receipt_stats_empty():
    out = receipt_stats({"rows": [], "total_paise": 0}, "This month")
    assert "No expenses yet" in out and "TOTAL" in out


def test_receipt_stats_single_category_full_bar():
    data = {"rows": [{"category": "Food", "total_paise": 100, "percent": 100}], "total_paise": 100}
    assert "█" * 10 in receipt_stats(data, "This year")
