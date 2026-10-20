import re
from datetime import datetime
from zoneinfo import ZoneInfo

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    BaseHandler,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from app.bot.client import BackendClient, BackendError
from app.bot.format import receipt_stats, receipt_today, rupees
from app.bot.parser import parse_message

TODAY_LABEL = "Today's Spending"
STATS_LABEL = "Overall Stats"
FEEDBACK_LABEL = "Feedback"
PERIOD_TITLES = {"month": "This month", "last_month": "Last month", "year": "This year"}
IST = ZoneInfo("Asia/Kolkata")
GREETING_WORDS = {"hi", "hii", "hello", "hey", "hola", "yo", "sup", "namaste", "hlo"}

GREETING = (
    "Hi {name}! 👋 I'm your Rupee Tracker.\n\n"
    "I make it easy to keep track of everyday cash spending. No forms, no fuss.\n\n"
    "How it works:\n"
    "• Tell me what you spent and how much, like metro 40 or lunch 250.\n"
    "• I sort it into a category (Travel, Food, Groceries…). If I don't know a word yet, "
    "I'll ask once and remember it.\n"
    "• Tap Today's Spending for a bill of what you've spent today.\n"
    "• Tap Overall Stats to see where your money goes each month.\n"
    "• Tap Feedback to tell me what you think.\n\n"
    "Try it now. Send your first expense!"
)
HELLO_BACK = "Hey {name}! 👋 Ready when you are. Tell me what you spent, like metro 40, or use the buttons below."
HELP = (
    "Hmm, I couldn't find an amount in that. 🤔\n\n"
    "Tell me what you spent and how much, for example:\n"
    "• metro 40\n"
    "• lunch 250\n"
    "• veggies 180\n\n"
    "Or use the buttons below for today's spending, your stats, or feedback."
)
FEEDBACK_PROMPT = (
    "💬 I'd love to hear what you think. What's working, and what's missing?\n"
    "Just type your feedback and send it."
)
FEEDBACK_THANKS = "Thank you! 🙏 Your feedback is saved."
FEEDBACK_TOO_LONG = "That's a bit long. Please keep feedback under 1000 characters and send it again."
FEEDBACK_CAP = "Thanks, I already have plenty of feedback from you for now. 🙏"

MENU = ReplyKeyboardMarkup([[TODAY_LABEL, STATS_LABEL], [FEEDBACK_LABEL]], resize_keyboard=True)
STATS_BUTTONS = InlineKeyboardMarkup(
    [[InlineKeyboardButton(title, callback_data=f"stats:{p}") for p, title in PERIOD_TITLES.items()]]
)
_SAVED_AMOUNT = re.compile(r"Saved (₹[\d,]+(?:\.\d{2})?)")


def _error_text(e: BackendError) -> str:
    return "Slow down a little." if e.status == 429 else "Something went wrong, try again."


def _name(update) -> str:
    return update.effective_user.first_name or "there"


def _is_greeting(text: str) -> bool:
    words = re.findall(r"[a-z]+", text.lower())
    return bool(words) and words[0] in GREETING_WORDS


def make_handlers(client: BackendClient) -> list[BaseHandler]:
    async def start(update, context):
        await update.message.reply_text(GREETING.format(name=_name(update)), reply_markup=MENU)

    async def show_today(update, user_id: int):
        data = await client.today(user_id)
        date_label = datetime.now(IST).strftime("%a, %d %b %Y")
        await update.message.reply_text(receipt_today(data, date_label), parse_mode=ParseMode.HTML)

    async def show_stats(update, user_id: int):
        data = await client.stats(user_id, "month")
        await update.message.reply_text(
            receipt_stats(data, PERIOD_TITLES["month"]),
            reply_markup=STATS_BUTTONS,
            parse_mode=ParseMode.HTML,
        )

    async def log_expense(update, user_id: int, text: str):
        parsed = parse_message(text)
        if parsed is None:
            if _is_greeting(text):
                await update.message.reply_text(HELLO_BACK.format(name=_name(update)), reply_markup=MENU)
            else:
                await update.message.reply_text(HELP, reply_markup=MENU)
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

    async def save_feedback(update, context, user_id: int, text: str):
        try:
            await client.feedback(user_id, text)
        except BackendError as e:
            if e.status == 422:
                await update.message.reply_text(FEEDBACK_TOO_LONG)
                return
            if e.status == 409:
                context.user_data.pop("awaiting_feedback", None)
                await update.message.reply_text(FEEDBACK_CAP)
                return
            raise
        context.user_data.pop("awaiting_feedback", None)
        await update.message.reply_text(FEEDBACK_THANKS)

    async def on_text(update, context):
        text = update.message.text
        if not text:
            return
        user_id = update.effective_user.id
        try:
            if text in (TODAY_LABEL, STATS_LABEL, FEEDBACK_LABEL):
                context.user_data.pop("new_cat_for", None)
                context.user_data.pop("awaiting_feedback", None)
                if text == TODAY_LABEL:
                    await show_today(update, user_id)
                elif text == STATS_LABEL:
                    await show_stats(update, user_id)
                else:
                    context.user_data["awaiting_feedback"] = True
                    await update.message.reply_text(FEEDBACK_PROMPT)
            elif context.user_data.get("awaiting_feedback"):
                await save_feedback(update, context, user_id, text)
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
                m = _SAVED_AMOUNT.search(getattr(q.message, "text", None) or "")
                await q.answer()
                await q.edit_message_text(
                    f"Saved {m.group(1)} to {r['category']}" if m else f"Saved to {r['category']}"
                )
            elif kind == "newcat":
                context.user_data["new_cat_for"] = int(rest)
                await q.answer()
                await q.edit_message_text("Type the name of the new category:")
            elif kind == "stats" and rest in PERIOD_TITLES:
                data = await client.stats(user_id, rest)
                await q.answer()
                await q.edit_message_text(
                    receipt_stats(data, PERIOD_TITLES[rest]),
                    reply_markup=STATS_BUTTONS,
                    parse_mode=ParseMode.HTML,
                )
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
