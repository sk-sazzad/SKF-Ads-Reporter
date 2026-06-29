import os
import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, ConversationHandler, MessageHandler, filters
)
from datetime import datetime, timedelta
from meta_api import MetaAdsAPI
from report_generator import ReportGenerator
from config import CLIENTS, ALLOWED_USER_IDS

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

CHOOSE_DATE, CHOOSE_FORMAT = range(2)
meta = MetaAdsAPI()
report_gen = ReportGenerator()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USER_IDS:
        await update.message.reply_text("Access denied.")
        return
    await update.message.reply_text(
        "SKF Boosting Automation Bot\n\n"
        "/report — সব client এর report\n"
        "/report ClientName — নির্দিষ্ট client\n"
        "/clients — client list\n"
        "/help — সাহায্য"
    )


async def clients_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USER_IDS:
        return
    lines = ["Client List:\n"]
    for name, info in CLIENTS.items():
        status = "Active" if info.get("active") else "Inactive"
        lines.append(f"• {name} ({status})")
    await update.message.reply_text("\n".join(lines))


async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USER_IDS:
        await update.message.reply_text("Access denied.")
        return

    args = context.args
    if args:
        client_name = " ".join(args)
        matched = None
        for name in CLIENTS:
            if name.lower() == client_name.lower():
                matched = name
                break
        if not matched:
            close = [n for n in CLIENTS if client_name.lower() in n.lower()]
            if close:
                matched = close[0]
        if not matched:
            await update.message.reply_text(
                f"Client '{client_name}' পাওয়া যায়নি।\n/clients দিয়ে list দেখুন।"
            )
            return
        context.user_data["selected_clients"] = [matched]
    else:
        context.user_data["selected_clients"] = list(CLIENTS.keys())

    return await ask_date_range(update, context)


async def ask_date_range(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("Today", callback_data="date_today"),
            InlineKeyboardButton("Yesterday", callback_data="date_yesterday"),
        ],
        [
            InlineKeyboardButton("Last 7 days", callback_data="date_7d"),
            InlineKeyboardButton("Last 15 days", callback_data="date_15d"),
        ],
        [
            InlineKeyboardButton("Last 30 days", callback_data="date_30d"),
            InlineKeyboardButton("Last 90 days", callback_data="date_90d"),
        ],
        [InlineKeyboardButton("Custom range", callback_data="date_custom")],
    ]
    msg = update.message or update.callback_query.message
    await msg.reply_text("Date range select করুন:", reply_markup=InlineKeyboardMarkup(keyboard))
    return CHOOSE_DATE


async def date_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    today = datetime.now().date()

    date_map = {
        "date_today": (today, today, "Today"),
        "date_yesterday": (today - timedelta(days=1), today - timedelta(days=1), "Yesterday"),
        "date_7d": (today - timedelta(days=7), today, "Last 7 days"),
        "date_15d": (today - timedelta(days=15), today, "Last 15 days"),
        "date_30d": (today - timedelta(days=30), today, "Last 30 days"),
        "date_90d": (today - timedelta(days=90), today, "Last 90 days"),
    }

    if data in date_map:
        start, stop, label = date_map[data]
        context.user_data["date_start"] = str(start)
        context.user_data["date_stop"] = str(stop)
        context.user_data["date_label"] = label
        return await ask_format(update, context)
    elif data == "date_custom":
        await query.edit_message_text(
            "Custom date range দিন:\nFormat: YYYY-MM-DD to YYYY-MM-DD\n"
            "Example: 2026-06-01 to 2026-06-28"
        )
        return CHOOSE_DATE


async def handle_custom_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        parts = text.split(" to ")
        date_start = datetime.strptime(parts[0].strip(), "%Y-%m-%d").date()
        date_stop = datetime.strptime(parts[1].strip(), "%Y-%m-%d").date()
        context.user_data["date_start"] = str(date_start)
        context.user_data["date_stop"] = str(date_stop)
        context.user_data["date_label"] = f"{date_start} to {date_stop}"
        return await ask_format(update, context)
    except Exception:
        await update.message.reply_text(
            "Format ঠিক নেই। আবার try করুন:\nExample: 2026-06-01 to 2026-06-28"
        )
        return CHOOSE_DATE


async def ask_format(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("Text only", callback_data="fmt_text"),
            InlineKeyboardButton("PDF only", callback_data="fmt_pdf"),
        ],
        [InlineKeyboardButton("Text + PDF", callback_data="fmt_both")],
    ]
    msg = update.callback_query.message if update.callback_query else update.message
    await msg.reply_text("Report format select করুন:", reply_markup=InlineKeyboardMarkup(keyboard))
    return CHOOSE_FORMAT


async def format_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    fmt_map = {"fmt_text": "text", "fmt_pdf": "pdf", "fmt_both": "both"}
    context.user_data["format"] = fmt_map[query.data]
    await query.edit_message_text("Report generate হচ্ছে, একটু অপেক্ষা করুন...")
    await generate_and_send(update, context)
    return ConversationHandler.END


async def generate_and_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    bot = context.bot
    selected_clients = context.user_data.get("selected_clients", [])
    date_start = context.user_data.get("date_start")
    date_stop = context.user_data.get("date_stop")
    date_label = context.user_data.get("date_label")
    fmt = context.user_data.get("format", "text")

    for client_name in selected_clients:
        client_info = CLIENTS.get(client_name)
        if not client_info:
            continue
        try:
            data = meta.get_insights(
                account_id=client_info["account_id"],
                date_start=date_start,
                date_stop=date_stop,
            )
            if fmt in ("text", "both"):
                await bot.send_message(
                    chat_id=chat_id,
                    text=report_gen.build_text_report(client_name, date_label, data),
                    parse_mode="HTML"
                )
            if fmt in ("pdf", "both"):
                pdf_path = report_gen.build_pdf_report(client_name, date_label, data)
                with open(pdf_path, "rb") as f:
                    await bot.send_document(
                        chat_id=chat_id,
                        document=f,
                        filename=f"{client_name}_report_{date_start}_{date_stop}.pdf",
                        caption=f"{client_name} — {date_label} report",
                    )
                os.remove(pdf_path)
        except Exception as e:
            logger.error(f"Error for {client_name}: {e}")
            await bot.send_message(
                chat_id=chat_id,
                text=f"{client_name} এর report generate করতে সমস্যা।\nError: {str(e)}"
            )

    await bot.send_message(chat_id=chat_id, text="সব report পাঠানো হয়েছে!")


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cancel করা হয়েছে।")
    return ConversationHandler.END


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "SKF Boosting Bot — Help\n\n"
        "/report — সব client এর report\n"
        "/report SKF Boosting — নির্দিষ্ট client\n"
        "/clients — client list\n"
        "/cancel — বাতিল\n\n"
        "Date: Today, Yesterday, 7/15/30/90 days, Custom\n"
        "Format: Text, PDF, Text+PDF"
    )


async def webhook_handler(request):
    from aiohttp.web import Response
    data = await request.json()
    application = request.app["application"]
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return Response(text="OK")


async def health_check(request):
    from aiohttp.web import Response
    return Response(text="SKF Ads Reporter Bot is running!")


def build_application():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN not set")

    app = Application.builder().token(token).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("report", report_command)],
        states={
            CHOOSE_DATE: [
                CallbackQueryHandler(date_callback, pattern="^date_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_custom_date),
            ],
            CHOOSE_FORMAT: [
                CallbackQueryHandler(format_callback, pattern="^fmt_"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False,
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("clients", clients_command))
    app.add_handler(conv_handler)
    return app


async def run_webhook(application, webhook_url, port):
    from aiohttp import web

    await application.initialize()
    await application.bot.set_webhook(
        url=f"{webhook_url}/webhook",
        drop_pending_updates=True,
    )
    await application.start()

    web_app = web.Application()
    web_app["application"] = application
    web_app.router.add_post("/webhook", webhook_handler)
    web_app.router.add_get("/", health_check)

    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Webhook running on port {port}")
    await asyncio.Event().wait()


async def run_polling(application):
    logger.info("Bot starting in polling mode...")
    await application.initialize()
    await application.start()
    await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
    await asyncio.Event().wait()


async def main():
    application = build_application()
    webhook_url = os.environ.get("WEBHOOK_URL", "").strip()

    if webhook_url:
        port = int(os.environ.get("PORT", 10000))
        await run_webhook(application, webhook_url, port)
    else:
        await run_polling(application)


if __name__ == "__main__":
    asyncio.run(main())
