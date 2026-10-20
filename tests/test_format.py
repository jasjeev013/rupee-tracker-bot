import pytest

from app.bot.format import rupees, stats_text, today_text


@pytest.mark.parametrize(
    "paise,text",
    [(4000, "₹40"), (1250, "₹12.50"), (12000000, "₹1,20,000"), (120000, "₹1,200"), (5, "₹0.05"), (0, "₹0")],
)
def test_rupees(paise, text):
    assert rupees(paise) == text


def test_stats_text_rows_and_total():
    data = {
        "rows": [
            {"category": "Food", "total_paise": 180000, "percent": 45},
            {"category": "Travel", "total_paise": 120000, "percent": 30},
        ],
        "total_paise": 400000,
    }
    out = stats_text(data, "This month")
    assert out.splitlines() == [
        "This month",
        "Food ₹1,800 (45%)",
        "Travel ₹1,200 (30%)",
        "Total ₹4,000",
    ]


def test_stats_text_empty():
    assert "No expenses yet" in stats_text({"rows": [], "total_paise": 0}, "This month")


def test_today_text():
    data = {"items": [{"description": "metro", "amount_paise": 4000, "category": "Travel"}], "total_paise": 4000}
    out = today_text(data)
    assert "metro" in out and "₹40" in out and "Travel" in out and "Total ₹40" in out
    assert "No expenses yet" in today_text({"items": [], "total_paise": 0})
