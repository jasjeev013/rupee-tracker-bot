import pytest

from app.bot.parser import ParsedExpense, parse_message


@pytest.mark.parametrize(
    "text,description,paise",
    [
        ("metro 40", "metro", 4000),
        ("lunch ₹250", "lunch", 25000),
        ("rs 40 metro", "metro", 4000),
        ("veggies 1,200", "veggies", 120000),
        ("chai 12.50", "chai", 1250),
        ("lunch 2 people 250", "lunch 2 people", 25000),
        ("  Metro   40 ", "Metro", 4000),
        ("cars 40", "cars", 4000),
    ],
)
def test_parse_message(text, description, paise):
    assert parse_message(text) == ParsedExpense(description, paise)


@pytest.mark.parametrize(
    "text",
    ["hello", "40", "lunch 0", "lunch -5", "lunch 99999999999", "x" * 201 + " 5", ""],
)
def test_parse_rejects(text):
    assert parse_message(text) is None
