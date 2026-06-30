import os
import asyncio
import logging
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, ConversationHandler, filters
)
from meta_api import MetaAdsAPI
from report_generator import ReportGenerator
from database import (
    get_all_clients, get_client, add_client, update_client, delete_client,
    toggle_client, generate_access_code, use_access_code, get_client_by_telegram,
    revoke_client_access, add_payment, get_payments, get_due_summary,
    get_settings, update_settings, next_invoice_number
)

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

ADMIN_IDS = [int(x.strip()) for x in os.environ.get("ALLOWED_USER_IDS", "").split(",") if x.strip()]

meta = MetaAdsAPI()
report_gen = ReportGenerator()

# ─── STATES ───────────────────────────────────────────────
(
    # Report flow
    S_REPORT_CLIENT, S_REPORT_DATE, S_REPORT_LEVEL, S_REPORT_FORMAT,
    # Client management
    S_ADD_CLIENT_NAME, S_ADD_CLIENT_ACCOUNT, S_ADD_CLIENT_PHONE,
    S_CLIENT_MENU, S_CLIENT_SELECT_ACTION,
    # Due tracker
    S_DUE_CLIENT, S_DUE_AMOUNT, S_DUE_NOTE,
    # Invoice
    S_INV_CLIENT, S_INV_SPEND, S_INV_SERVICE, S_INV_EXTRA,
    # Settings
    S_SETTINGS_MENU,
    # Client portal
    S_CLIENT_ACCESS_CODE, S_CLIENT_DATE, S_CLIENT_FORMAT,
    # Alert check
    S_ALERT_CLIENT,
) = range(21)


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def admin_main_menu():
    keyboard = [
        [KeyboardButton("📊 Reports"), KeyboardButton("⚡ Quick Check")],
        [KeyboardButton("👥 Clients"), KeyboardButton("💳 Due Tracker")],
        [KeyboardButton("🧾 Invoice"), KeyboardButton("⚙️ Settings")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def client_main_menu():
    keyboard = [
        [KeyboardButton("📊 My Report"), KeyboardButton("📈 Performance")],
        [KeyboardButton("🌍 GEO Report"), KeyboardButton("📞 Contact Agency")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def date_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Today", callback_data="d_today"),
         InlineKeyboardButton("Yesterday", callback_data="d_yesterday")],
        [InlineKeyboardButton("Last 7 days", callback_data="d_7"),
         InlineKeyboardButton("Last 15 days", callback_data="d_15")],
        [InlineKeyboardButton("Last 30 days", callback_data="d_30"),
         InlineKeyboardButton("Last 90 days", callback_data="d_90")],
        [InlineKeyboardButton("📅 Custom", callback_data="d_custom")],
    ])


def format_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 Text", callback_data="f_text"),
         InlineKeyboardButton("📄 PDF", callback_data="f_pdf")],
        [InlineKeyboardButton("📝+📄 Text + PDF", callback_data="f_both")],
    ])


def level_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎯 Campaign", callback_data="l_campaign")],
        [InlineKeyboardButton("📦 Ad Set", callback_data="l_adset")],
        [InlineKeyboardButton("🖼 Ad", callback_data="l_ad")],
    ])


def clients_keyboard(prefix="rc_", include_all=True):
    clients = get_all_clients()
    active = {k: v for k, v in clients.items() if v.get("active")}
    rows = []
    items = list(active.items())
    for i in range(0, len(items), 2):
        row = [InlineKeyboardButton(items[i][0], callback_data=f"{prefix}{items[i][0]}")]
        if i + 1 < len(items):
            row.append(InlineKeyboardButton(items[i+1][0], callback_data=f"{prefix}{items[i+1][0]}"))
        rows.append(row)
    if include_all:
        rows.append([InlineKeyboardButton("👥 সব Client", callback_data=f"{prefix}__ALL__")])
    return InlineKeyboardMarkup(rows)


# ─── START ────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    first_name = update.effective_user.first_name

    if is_admin(user_id):
        await update.message.reply_text(
            f"স্বাগতম {first_name}! 👋\n\nSKF Boosting Agency Bot এ আপনাকে স্বাগতম।\nনিচের menu থেকে যা দরকার select করুন।",
            reply_markup=admin_main_menu()
        )
        return ConversationHandler.END

    # Check if client
    client_name = get_client_by_telegram(user_id)
    if client_name:
        await update.message.reply_text(
            f"স্বাগতম {first_name}! 👋\nআপনি {client_name} এর account এ logged in আছেন।",
            reply_markup=client_main_menu()
        )
        return ConversationHandler.END

    # New user — ask for access code
    await update.message.reply_text(
        "👋 স্বাগতম!\n\nএই bot টি SKF Boosting Agency এর client দের জন্য।\n\n"
        "আপনার access code দিন:"
    )
    return S_CLIENT_ACCESS_CODE


async def handle_access_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip().upper()
    user_id = update.effective_user.id
    client_name = use_access_code(code, user_id)
    if client_name:
        await update.message.reply_text(
            f"✅ স্বাগতম! আপনি {client_name} হিসেবে login করেছেন।",
            reply_markup=client_main_menu()
        )
        return ConversationHandler.END
    else:
        await update.message.reply_text("❌ Code টি সঠিক নয় বা ইতিমধ্যে ব্যবহার হয়েছে।\nআবার try করুন:")
        return S_CLIENT_ACCESS_CODE


# ─── ADMIN — REPORTS ──────────────────────────────────────

async def menu_reports(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await update.message.reply_text("কোন client এর report চান?", reply_markup=clients_keyboard("rc_"))
    return S_REPORT_CLIENT


async def report_client_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    client_key = query.data.replace("rc_", "")
    if client_key == "__ALL__":
        context.user_data["report_clients"] = list(get_all_clients().keys())
    else:
        context.user_data["report_clients"] = [client_key]
    await query.edit_message_text("Date range select করুন:", reply_markup=date_keyboard())
    return S_REPORT_DATE


async def report_date_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    today = datetime.now().date()
    date_map = {
        "d_today": (today, today, "Today"),
        "d_yesterday": (today - timedelta(1), today - timedelta(1), "Yesterday"),
        "d_7": (today - timedelta(7), today, "Last 7 days"),
        "d_15": (today - timedelta(15), today, "Last 15 days"),
        "d_30": (today - timedelta(30), today, "Last 30 days"),
        "d_90": (today - timedelta(90), today, "Last 90 days"),
    }
    if query.data == "d_custom":
        await query.edit_message_text("Date দিন (YYYY-MM-DD to YYYY-MM-DD):")
        return S_REPORT_DATE
    start, stop, label = date_map[query.data]
    context.user_data.update({"date_start": str(start), "date_stop": str(stop), "date_label": label})
    await query.edit_message_text("Breakdown level:", reply_markup=level_keyboard())
    return S_REPORT_LEVEL


async def report_level_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    level_map = {"l_campaign": "campaign", "l_adset": "adset", "l_ad": "ad"}
    context.user_data["level"] = level_map[query.data]
    await query.edit_message_text("Report format:", reply_markup=format_keyboard())
    return S_REPORT_FORMAT


async def report_format_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    fmt_map = {"f_text": "text", "f_pdf": "pdf", "f_both": "both"}
    context.user_data["format"] = fmt_map[query.data]
    await query.edit_message_text("Report generate হচ্ছে... ⏳")
    await do_generate_report(update, context)
    return ConversationHandler.END


async def do_generate_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    bot = context.bot
    clients = context.user_data.get("report_clients", [])
    date_start = context.user_data.get("date_start")
    date_stop = context.user_data.get("date_stop")
    date_label = context.user_data.get("date_label")
    fmt = context.user_data.get("format", "text")
    level = context.user_data.get("level", "campaign")

    for client_name in clients:
        info = get_client(client_name)
        if not info:
            continue
        try:
            data = meta.get_insights(info["account_id"], date_start, date_stop, level)
            if fmt in ("text", "both"):
                await bot.send_message(chat_id=chat_id,
                                       text=report_gen.build_text_report(client_name, date_label, data),
                                       parse_mode="HTML")
            if fmt in ("pdf", "both"):
                pdf = report_gen.build_pdf_report(client_name, date_label, data)
                with open(pdf, "rb") as f:
                    await bot.send_document(chat_id=chat_id, document=f,
                                            filename=f"{client_name}_{date_start}_{date_stop}.pdf",
                                            caption=f"{client_name} — {date_label}")
                os.remove(pdf)
        except Exception as e:
            await bot.send_message(chat_id=chat_id, text=f"❌ {client_name}: {str(e)}")

    await bot.send_message(chat_id=chat_id, text="✅ সব report পাঠানো হয়েছে!", reply_markup=admin_main_menu())


# ─── ADMIN — QUICK CHECK ──────────────────────────────────

async def menu_quick_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await update.message.reply_text("⏳ সব client এর আজকের data আনছি...")
    today = str(datetime.now().date())
    clients = get_all_clients()
    lines = ["<b>⚡ Quick Check — Today</b>\n"]
    total_spend = 0

    for name, info in clients.items():
        if not info.get("active"):
            continue
        try:
            data = meta.get_insights(info["account_id"], today, today)
            s = data["summary"]
            total_spend += s["total_spend"]
            status = "🟢" if s["total_spend"] > 0 else "🔴"
            lines.append(
                f"{status} <b>{name}</b>\n"
                f"   💸 {s['total_spend']:,.2f} BDT | 🖱 {s['total_clicks']:,} clicks | CTR {s['avg_ctr']:.2f}%"
            )
        except Exception as e:
            lines.append(f"⚠️ <b>{name}</b>: Error")

    lines.append(f"\n<b>Total Spend Today: {total_spend:,.2f} BDT</b>")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML", reply_markup=admin_main_menu())


# ─── ADMIN — CLIENTS ──────────────────────────────────────

async def menu_clients(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ নতুন Client Add", callback_data="cl_add")],
        [InlineKeyboardButton("📋 Client List", callback_data="cl_list")],
        [InlineKeyboardButton("✏️ Client Edit", callback_data="cl_edit")],
        [InlineKeyboardButton("🔑 Access Code Generate", callback_data="cl_code")],
        [InlineKeyboardButton("🚫 Access Revoke", callback_data="cl_revoke")],
    ])
    await update.message.reply_text("👥 Client Management:", reply_markup=keyboard)
    return S_CLIENT_MENU


async def client_menu_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action = query.data

    if action == "cl_add":
        await query.edit_message_text("নতুন client এর নাম দিন:")
        context.user_data["cl_action"] = "add"
        return S_ADD_CLIENT_NAME

    elif action == "cl_list":
        clients = get_all_clients()
        if not clients:
            await query.edit_message_text("কোনো client নেই।")
            return ConversationHandler.END
        lines = ["<b>Client List:</b>\n"]
        for name, info in clients.items():
            status = "🟢" if info.get("active") else "🔴"
            portal = "👤" if info.get("telegram_id") else "🔓"
            lines.append(f"{status} {portal} <b>{name}</b>\n   Account: {info['account_id']}")
        await query.edit_message_text("\n".join(lines), parse_mode="HTML")
        return ConversationHandler.END

    elif action == "cl_code":
        await query.edit_message_text("কোন client এর জন্য code বানাবেন?",
                                       reply_markup=clients_keyboard("code_", include_all=False))
        return S_CLIENT_SELECT_ACTION

    elif action == "cl_revoke":
        await query.edit_message_text("কোন client এর access বন্ধ করবেন?",
                                       reply_markup=clients_keyboard("revoke_", include_all=False))
        return S_CLIENT_SELECT_ACTION

    elif action == "cl_edit":
        await query.edit_message_text("কোন client edit করবেন?",
                                       reply_markup=clients_keyboard("edit_", include_all=False))
        return S_CLIENT_SELECT_ACTION


async def client_select_action_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("code_"):
        client_name = data.replace("code_", "")
        code = generate_access_code(client_name)
        await query.edit_message_text(
            f"✅ Access code generated!\n\n"
            f"Client: <b>{client_name}</b>\n"
            f"Code: <b>{code}</b>\n\n"
            f"Client কে এই message পাঠান:\n\n"
            f"আমাদের Report Bot: t.me/SKFAdsReporterbot\n"
            f"আপনার Access Code: <code>{code}</code>",
            parse_mode="HTML"
        )

    elif data.startswith("revoke_"):
        client_name = data.replace("revoke_", "")
        revoke_client_access(client_name)
        await query.edit_message_text(f"✅ {client_name} এর access বন্ধ করা হয়েছে।")

    elif data.startswith("edit_"):
        client_name = data.replace("edit_", "")
        info = get_client(client_name)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "🔴 Deactivate" if info.get("active") else "🟢 Activate",
                callback_data=f"toggle_{client_name}"
            )],
            [InlineKeyboardButton("🗑 Delete", callback_data=f"delete_{client_name}")],
        ])
        await query.edit_message_text(
            f"<b>{client_name}</b>\nAccount: {info['account_id']}\nStatus: {'Active' if info.get('active') else 'Inactive'}",
            parse_mode="HTML", reply_markup=keyboard
        )

    return ConversationHandler.END


async def toggle_delete_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data.startswith("toggle_"):
        name = query.data.replace("toggle_", "")
        active = toggle_client(name)
        await query.edit_message_text(f"{'🟢 Activated' if active else '🔴 Deactivated'}: {name}")
    elif query.data.startswith("delete_"):
        name = query.data.replace("delete_", "")
        delete_client(name)
        await query.edit_message_text(f"🗑 {name} deleted.")
    return ConversationHandler.END


async def add_client_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_client_name"] = update.message.text.strip()
    await update.message.reply_text("Ad Account ID দিন (act_XXXXXXXXXX):")
    return S_ADD_CLIENT_ACCOUNT


async def add_client_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    account_id = update.message.text.strip()
    if not account_id.startswith("act_"):
        await update.message.reply_text("❌ Format ঠিক নেই। act_ দিয়ে শুরু হওয়া উচিত। আবার দিন:")
        return S_ADD_CLIENT_ACCOUNT
    context.user_data["new_client_account"] = account_id
    await update.message.reply_text("Client এর WhatsApp নম্বর দিন (optional, skip করতে /skip):")
    return S_ADD_CLIENT_PHONE


async def add_client_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = "" if update.message.text.strip() == "/skip" else update.message.text.strip()
    name = context.user_data["new_client_name"]
    account_id = context.user_data["new_client_account"]
    success = add_client(name, account_id, phone=phone, whatsapp=phone)
    if success:
        await update.message.reply_text(
            f"✅ Client added!\n\n<b>{name}</b>\nAccount: {account_id}",
            parse_mode="HTML", reply_markup=admin_main_menu()
        )
    else:
        await update.message.reply_text("❌ এই নামে client আগে থেকেই আছে।", reply_markup=admin_main_menu())
    return ConversationHandler.END


# ─── ADMIN — DUE TRACKER ──────────────────────────────────

async def menu_due(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Due Summary", callback_data="due_summary")],
        [InlineKeyboardButton("✅ Payment Received", callback_data="due_payment")],
        [InlineKeyboardButton("🏦 Meta Account Balance", callback_data="due_meta")],
    ])
    await update.message.reply_text("💳 Due Tracker:", reply_markup=keyboard)
    return S_DUE_CLIENT


async def due_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "due_summary":
        summary = get_due_summary()
        lines = ["<b>💳 Due Summary</b>\n"]
        for item in summary:
            status = "🟢" if item["active"] else "🔴"
            lines.append(
                f"{status} <b>{item['name']}</b>\n"
                f"   Total Paid: {item['total_paid']:,.2f} BDT"
            )
        await query.edit_message_text("\n".join(lines), parse_mode="HTML")
        return ConversationHandler.END

    elif query.data == "due_payment":
        await query.edit_message_text("কোন client payment দিয়েছে?",
                                       reply_markup=clients_keyboard("pay_", include_all=False))
        return S_DUE_CLIENT

    elif query.data == "due_meta":
        await query.edit_message_text("⏳ Meta account balance চেক হচ্ছে...")
        clients = get_all_clients()
        lines = ["<b>🏦 Meta Account Balance</b>\n"]
        for name, info in clients.items():
            if not info.get("active"):
                continue
            try:
                bal = meta.get_account_balance(info["account_id"])
                spent = float(bal.get("amount_spent", 0)) / 100
                balance = float(bal.get("balance", 0)) / 100
                lines.append(f"<b>{name}</b>\n   Spent: {spent:,.2f} | Balance: {balance:,.2f}")
            except:
                lines.append(f"<b>{name}</b>: Error")
        await query.edit_message_text("\n".join(lines), parse_mode="HTML")
        return ConversationHandler.END


async def payment_client_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["pay_client"] = query.data.replace("pay_", "")
    await query.edit_message_text("কত টাকা পেয়েছেন? (BDT):")
    return S_DUE_AMOUNT


async def payment_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text.strip().replace(",", ""))
        context.user_data["pay_amount"] = amount
        await update.message.reply_text("Note দিন (optional, skip করতে /skip):")
        return S_DUE_NOTE
    except:
        await update.message.reply_text("❌ সঠিক পরিমাণ দিন:")
        return S_DUE_AMOUNT


async def payment_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    note = "" if update.message.text.strip() == "/skip" else update.message.text.strip()
    client = context.user_data["pay_client"]
    amount = context.user_data["pay_amount"]
    add_payment(client, amount, note)
    await update.message.reply_text(
        f"✅ Payment recorded!\n{client}: {amount:,.2f} BDT",
        reply_markup=admin_main_menu()
    )
    return ConversationHandler.END


# ─── ADMIN — INVOICE ──────────────────────────────────────

async def menu_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await update.message.reply_text("🧾 কোন client এর invoice বানাবেন?",
                                     reply_markup=clients_keyboard("inv_", include_all=False))
    return S_INV_CLIENT


async def invoice_client_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["inv_client"] = query.data.replace("inv_", "")
    await query.edit_message_text("Ad Spend কত? (BDT):")
    return S_INV_SPEND


async def invoice_spend(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["inv_spend"] = float(update.message.text.strip().replace(",", ""))
        await update.message.reply_text("Service Charge কত? (BDT):")
        return S_INV_SERVICE
    except:
        await update.message.reply_text("❌ সঠিক পরিমাণ দিন:")
        return S_INV_SPEND


async def invoice_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["inv_service"] = float(update.message.text.strip().replace(",", ""))
        await update.message.reply_text("⏳ Invoice generate হচ্ছে...")
        client = context.user_data["inv_client"]
        spend = context.user_data["inv_spend"]
        service = context.user_data["inv_service"]
        pdf = report_gen.build_invoice_pdf(client, [], spend, service)
        with open(pdf, "rb") as f:
            await update.message.reply_document(
                document=f,
                filename=f"Invoice_{client}_{datetime.now().strftime('%Y%m%d')}.pdf",
                caption=f"🧾 Invoice — {client}\nTotal: {spend + service:,.2f} BDT"
            )
        os.remove(pdf)
        return ConversationHandler.END
    except:
        await update.message.reply_text("❌ সঠিক পরিমাণ দিন:")
        return S_INV_SERVICE


# ─── ADMIN — SETTINGS ─────────────────────────────────────

async def menu_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    settings = get_settings()
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏢 Agency Name", callback_data="set_name")],
        [InlineKeyboardButton("📞 Phone/WhatsApp", callback_data="set_phone")],
        [InlineKeyboardButton("⏰ Daily Report Time", callback_data="set_time")],
    ])
    await update.message.reply_text(
        f"⚙️ Settings\n\n"
        f"Agency: {settings['agency_name']}\n"
        f"Phone: {settings.get('agency_phone', 'Not set')}\n"
        f"Daily Report: {settings.get('daily_report_time', '09:00')}",
        reply_markup=keyboard
    )
    return S_SETTINGS_MENU


async def settings_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    prompts = {
        "set_name": ("agency_name", "নতুন agency name দিন:"),
        "set_phone": ("agency_phone", "Phone/WhatsApp number দিন:"),
        "set_time": ("daily_report_time", "Daily report time দিন (HH:MM format, যেমন 09:00):"),
    }
    key, prompt = prompts[query.data]
    context.user_data["setting_key"] = key
    await query.edit_message_text(prompt)
    return S_SETTINGS_MENU


async def settings_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    key = context.user_data.get("setting_key")
    if key:
        update_settings(**{key: update.message.text.strip()})
        await update.message.reply_text(f"✅ Updated!", reply_markup=admin_main_menu())
        context.user_data.pop("setting_key", None)
    return ConversationHandler.END


# ─── CLIENT PORTAL ────────────────────────────────────────

async def client_my_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    client_name = get_client_by_telegram(user_id)
    if not client_name:
        await update.message.reply_text("❌ Access নেই।")
        return
    context.user_data["report_clients"] = [client_name]
    context.user_data["level"] = "campaign"
    await update.message.reply_text("Date range select করুন:", reply_markup=date_keyboard())
    return S_CLIENT_DATE


async def client_date_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    today = datetime.now().date()
    date_map = {
        "cd_today": (today, today, "Today"),
        "cd_7": (today - timedelta(7), today, "Last 7 days"),
        "cd_30": (today - timedelta(30), today, "Last 30 days"),
    }
    if query.data in date_map:
        start, stop, label = date_map[query.data]
        context.user_data.update({"date_start": str(start), "date_stop": str(stop), "date_label": label})
        await query.edit_message_text("Format:", reply_markup=format_keyboard())
        return S_CLIENT_FORMAT
    return S_CLIENT_DATE


async def client_format_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    fmt_map = {"f_text": "text", "f_pdf": "pdf", "f_both": "both"}
    context.user_data["format"] = fmt_map.get(query.data, "text")
    await query.edit_message_text("⏳ Report generate হচ্ছে...")
    await do_generate_report(update, context)
    return ConversationHandler.END


async def client_geo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    client_name = get_client_by_telegram(user_id)
    if not client_name:
        return
    info = get_client(client_name)
    today = str(datetime.now().date())
    last30 = str(datetime.now().date() - timedelta(30))
    try:
        geo = meta.get_geo_insights(info["account_id"], last30, today)
        text = report_gen.build_geo_text(client_name, "Last 30 days", geo)
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=client_main_menu())
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def client_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    settings = get_settings()
    text = f"📞 {settings['agency_name']}\n\n"
    if settings.get("agency_phone"):
        text += f"Phone: {settings['agency_phone']}\n"
    if settings.get("agency_whatsapp"):
        text += f"WhatsApp: wa.me/{settings['agency_whatsapp']}\n"
    text += "\nআমাদের সাথে যোগাযোগ করুন যেকোনো প্রশ্নের জন্য।"
    await update.message.reply_text(text, reply_markup=client_main_menu())


# ─── WEBHOOK / MAIN ───────────────────────────────────────

async def webhook_handler(request):
    from aiohttp.web import Response
    data = await request.json()
    app = request.app["application"]
    update = Update.de_json(data, app.bot)
    await app.process_update(update)
    return Response(text="OK")


async def health_check(request):
    from aiohttp.web import Response
    return Response(text="SKF Ads Reporter v2 running!")


def build_app():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN not set")

    app = Application.builder().token(token).build()

    # Main conversation handler
    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            MessageHandler(filters.Regex("^📊 Reports$"), menu_reports),
            MessageHandler(filters.Regex("^⚡ Quick Check$"), menu_quick_check),
            MessageHandler(filters.Regex("^👥 Clients$"), menu_clients),
            MessageHandler(filters.Regex("^💳 Due Tracker$"), menu_due),
            MessageHandler(filters.Regex("^🧾 Invoice$"), menu_invoice),
            MessageHandler(filters.Regex("^⚙️ Settings$"), menu_settings),
            MessageHandler(filters.Regex("^📊 My Report$"), client_my_report),
            MessageHandler(filters.Regex("^🌍 GEO Report$"), client_geo),
            MessageHandler(filters.Regex("^📞 Contact Agency$"), client_contact),
        ],
        states={
            S_CLIENT_ACCESS_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_access_code)],
            S_REPORT_CLIENT: [CallbackQueryHandler(report_client_cb, pattern="^rc_")],
            S_REPORT_DATE: [CallbackQueryHandler(report_date_cb, pattern="^d_")],
            S_REPORT_LEVEL: [CallbackQueryHandler(report_level_cb, pattern="^l_")],
            S_REPORT_FORMAT: [CallbackQueryHandler(report_format_cb, pattern="^f_")],
            S_CLIENT_MENU: [
                CallbackQueryHandler(client_menu_cb, pattern="^cl_"),
                CallbackQueryHandler(toggle_delete_cb, pattern="^(toggle|delete)_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, settings_input),
            ],
            S_CLIENT_SELECT_ACTION: [
                CallbackQueryHandler(client_select_action_cb, pattern="^(code|revoke|edit)_"),
                CallbackQueryHandler(toggle_delete_cb, pattern="^(toggle|delete)_"),
            ],
            S_ADD_CLIENT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_client_name)],
            S_ADD_CLIENT_ACCOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_client_account)],
            S_ADD_CLIENT_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_client_phone)],
            S_DUE_CLIENT: [
                CallbackQueryHandler(due_cb, pattern="^due_"),
                CallbackQueryHandler(payment_client_cb, pattern="^pay_"),
            ],
            S_DUE_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, payment_amount)],
            S_DUE_NOTE: [MessageHandler(filters.TEXT & ~filters.COMMAND, payment_note)],
            S_INV_CLIENT: [CallbackQueryHandler(invoice_client_cb, pattern="^inv_")],
            S_INV_SPEND: [MessageHandler(filters.TEXT & ~filters.COMMAND, invoice_spend)],
            S_INV_SERVICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, invoice_service)],
            S_SETTINGS_MENU: [
                CallbackQueryHandler(settings_cb, pattern="^set_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, settings_input),
            ],
            S_CLIENT_DATE: [CallbackQueryHandler(client_date_cb, pattern="^(cd_|d_)")],
            S_CLIENT_FORMAT: [CallbackQueryHandler(client_format_cb, pattern="^f_")],
        },
        fallbacks=[CommandHandler("start", start)],
        per_message=False,
        allow_reentry=True,
    )

    app.add_handler(conv)
    return app


async def run_webhook(application, webhook_url, port):
    from aiohttp import web
    await application.initialize()
    await application.bot.set_webhook(url=f"{webhook_url}/webhook", drop_pending_updates=True)
    await application.start()
    web_app = web.Application()
    web_app["application"] = application
    web_app.router.add_post("/webhook", webhook_handler)
    web_app.router.add_get("/", health_check)
    runner = web.AppRunner(web_app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", port).start()
    logger.info(f"Bot running on port {port}")
    await asyncio.Event().wait()


async def run_polling(application):
    await application.initialize()
    await application.start()
    await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
    await asyncio.Event().wait()


async def main():
    application = build_app()
    webhook_url = os.environ.get("WEBHOOK_URL", "").strip()
    if webhook_url:
        await run_webhook(application, webhook_url, int(os.environ.get("PORT", 10000)))
    else:
        await run_polling(application)


if __name__ == "__main__":
    asyncio.run(main())
