import re

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import (
    BaseHandler,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from app.bot.client import BackendClient, BackendError
from app.bot.format import rupees, stats_text, today_text
from app.bot.parser import parse_message

TODAY_LABEL = "Today's Spending"
STATS_LABEL = "Overall Stats"
HINT = "Send it like: metro 40"
PERIOD_TITLES = {"month": "This month", "last_month": "Last month", "year": "This year"}

MENU = ReplyKeyboardMarkup([[TODAY_LABEL, STATS_LABEL]], resize_keyboard=True)
STATS_BUTTONS = InlineKeyboardMarkup(
    [[InlineKeyboardButton(title, callback_data=f"stats:{p}") for p, title in PERIOD_TITLES.items()]]
)
_SAVED_AMOUNT = re.compile(r"Saved (₹[\d,]+(?:\.\d{2})?)")


def _error_text(e: BackendError) -> str:
    return "Slow down a little." if e.status == 429 else "Something went wrong, try again."


def make_handlers(client: BackendClient) -> list[BaseHandler]:
    async def start(update, context):
        await update.message.reply_text(
            "Send an expense like: metro 40\nI'll sort it into a category for you.",
            reply_markup=MENU,
        )

    async def show_stats(update, user_id: int):
        data = await client.stats(user_id, "month")
        await update.message.reply_text(
            stats_text(data, PERIOD_TITLES["month"]), reply_markup=STATS_BUTTONS
        )

    async def log_expense(update, user_id: int, text: str):
        parsed = parse_message(text)
        if parsed is None:
            await update.message.reply_text(HINT)
            return
        r = await client.add_expense(user_id, parsed.description, parsed.amount_paise)
        amount = rupees(parsed.amount_paise)
        if r["category"] is not None:
            await update.message.reply_text(f"Saved {amount} to {r['category']}")
            return
        cats = await client.categories(user_id)
        buttons = [
            InlineKeyboardButton(c["name"], callback_data=f"cat:{r['expense_id']}:{c['id']}")
            for c in cats
        ]
        buttons.append(InlineKeyboardButton("+ New category", callback_data=f"newcat:{r['expense_id']}"))
        rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
        await update.message.reply_text(
            f'Saved {amount}. Which category for "{r["word"]}"?',
            reply_markup=InlineKeyboardMarkup(rows),
        )

    async def new_category_name(update, context, user_id: int, text: str):
        expense_id = context.user_data["new_cat_for"]
        try:
            cat = await client.create_category(user_id, text)
        except BackendError as e:
            if e.status == 422:
                await update.message.reply_text("Category names must be 1-30 characters. Try again.")
                return
            context.user_data.pop("new_cat_for", None)
            if e.status == 409:
                await update.message.reply_text("You've reached the category limit.")
                return
            raise
        context.user_data.pop("new_cat_for", None)
        await client.assign_category(user_id, expense_id, cat["id"])
        await update.message.reply_text(f"Saved to {cat['name']}")

    async def on_text(update, context):
        text = update.message.text
        if not text:
            return
        user_id = update.effective_user.id
        try:
            if text in (TODAY_LABEL, STATS_LABEL):
                context.user_data.pop("new_cat_for", None)
                if text == TODAY_LABEL:
                    await update.message.reply_text(today_text(await client.today(user_id)))
                else:
                    await show_stats(update, user_id)
            elif "new_cat_for" in context.user_data:
                await new_category_name(update, context, user_id, text)
            else:
                await log_expense(update, user_id, text)
        except BackendError as e:
            await update.message.reply_text(_error_text(e))

    async def on_callback(update, context):
        q = update.callback_query
        user_id = update.effective_user.id
        kind, _, rest = q.data.partition(":")
        try:
            if kind == "cat":
                expense_id, category_id = (int(x) for x in rest.split(":"))
                r = await client.assign_category(user_id, expense_id, category_id)
                m = _SAVED_AMOUNT.search(q.message.text or "")
                await q.answer()
                await q.edit_message_text(f"Saved {m.group(1)} to {r['category']}" if m else f"Saved to {r['category']}")
            elif kind == "newcat":
                context.user_data["new_cat_for"] = int(rest)
                await q.answer()
                await q.edit_message_text("Type the name of the new category:")
            elif kind == "stats" and rest in PERIOD_TITLES:
                data = await client.stats(user_id, rest)
                await q.answer()
                await q.edit_message_text(stats_text(data, PERIOD_TITLES[rest]), reply_markup=STATS_BUTTONS)
            else:
                await q.answer()
        except BackendError as e:
            if e.status == 404:
                await q.answer("That entry no longer exists.", show_alert=True)
            else:
                await q.answer(_error_text(e), show_alert=True)

    return [
        CommandHandler("start", start),
        CallbackQueryHandler(on_callback, pattern=r"^(cat|newcat|stats):"),
        MessageHandler(filters.TEXT & ~filters.COMMAND, on_text),
    ]
