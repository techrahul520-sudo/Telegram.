"""
💼 WhatsApp Work Bot 💼
Version: 4.0 — Optimized & Smooth
"""

import logging
import json
import os
from datetime import datetime
from functools import wraps
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# ══════════════════════════════════════════════
#  CONFIGURATION — env variables se lo (secure)
# ══════════════════════════════════════════════
BOT_TOKEN  = os.getenv("BOT_TOKEN", "8845688989:AAF36EoXtUpsx63ITpTCbxNkytmsQDUNTts")
ADMIN_ID   = int(os.getenv("ADMIN_ID", "8563648693"))

GROUP_1 = "https://t.me/your_group_1"
GROUP_2 = "https://t.me/your_group_2"
GROUP_3 = "https://t.me/your_group_3"

INVITE_RATE  = 0.5
WA_SELL_RATE = 0.030
WA_RENT_MIN  = 0.030
WA_RENT_MAX  = 0.036
WITHDRAW_MIN = 1.0
BOT_LINK     = "https://t.me/YourBotUsername"

USERS_FILE    = "users_data.json"
MESSAGES_FILE = "messages_log.json"
BLOCKED_FILE  = "blocked_users.json"

# ══════════════════════════════════════════════
#  IN-MEMORY CACHE — disk I/O kam karo
# ══════════════════════════════════════════════
_cache: dict[str, dict] = {}

def load_json(f: str) -> dict:
    """Cache se load karo — sirf pehli baar disk padhega."""
    if f not in _cache:
        if os.path.exists(f):
            with open(f, "r", encoding="utf-8") as fp:
                _cache[f] = json.load(fp)
        else:
            _cache[f] = {}
    return _cache[f]

def save_json(f: str, data: dict) -> None:
    """Cache update karo + disk pe save karo."""
    _cache[f] = data
    with open(f, "w", encoding="utf-8") as fp:
        json.dump(data, fp, ensure_ascii=False, indent=2)

def invalidate_cache(f: str) -> None:
    """Kisi file ka cache hata do (forceful reload ke liye)."""
    _cache.pop(f, None)

# ══════════════════════════════════════════════
#  LOGGING
# ══════════════════════════════════════════════
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════

def is_admin(uid: int) -> bool:
    return uid == ADMIN_ID

def is_blocked(uid: int) -> bool:
    return str(uid) in load_json(BLOCKED_FILE)

def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def register_user(user, ref_id=None) -> dict:
    """
    User register karo. Ek hi baar load_json call.
    Returns: current user dict.
    """
    users = load_json(USERS_FILE)
    uid   = str(user.id)

    if uid not in users:
        users[uid] = {
            "id":            user.id,
            "name":          user.full_name,
            "username":      f"@{user.username}" if user.username else "N/A",
            "joined":        now_str(),
            "last_seen":     now_str(),
            "message_count": 0,
            "invite_income": 0.0,
            "work_income":   0.0,
            "total_wallet":  0.0,
            "invites":       0,
            "referred_by":   str(ref_id) if ref_id else None,
            "joined_groups": False,
        }
        # Referral bonus — ek hi save mein dono update
        ref = str(ref_id) if ref_id else None
        if ref and ref in users and ref != uid:
            users[ref]["invite_income"] = round(users[ref].get("invite_income", 0) + INVITE_RATE, 2)
            users[ref]["total_wallet"]  = round(users[ref].get("total_wallet",  0) + INVITE_RATE, 2)
            users[ref]["invites"]       = users[ref].get("invites", 0) + 1
    else:
        users[uid]["last_seen"] = now_str()
        users[uid]["name"]      = user.full_name

    save_json(USERS_FILE, users)
    return users[uid]

def get_user(uid) -> dict:
    return load_json(USERS_FILE).get(str(uid), {})

def update_user(uid, data: dict) -> None:
    users = load_json(USERS_FILE)
    if str(uid) in users:
        users[str(uid)].update(data)
        save_json(USERS_FILE, users)

def log_message(user, text: str) -> None:
    """Messages + user message_count — ek saath update."""
    logs  = load_json(MESSAGES_FILE)
    users = load_json(USERS_FILE)
    uid   = str(user.id)

    if uid not in logs:
        logs[uid] = {"name": user.full_name, "messages": []}
    logs[uid]["messages"].append({"text": text, "time": now_str()})
    logs[uid]["messages"] = logs[uid]["messages"][-50:]
    save_json(MESSAGES_FILE, logs)

    if uid in users:
        users[uid]["message_count"] = users[uid].get("message_count", 0) + 1
        save_json(USERS_FILE, users)

# ══════════════════════════════════════════════
#  DECORATORS — boilerplate hatao
# ══════════════════════════════════════════════

def admin_only(func):
    """Sirf admin use kar sake."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not is_admin(update.effective_user.id):
            await update.message.reply_text("🚫 Sirf admin!")
            return
        return await func(update, context)
    return wrapper

def block_check(func):
    """Blocked users ko rok do."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if is_blocked(update.effective_user.id):
            msg = update.message or (update.callback_query and update.callback_query.message)
            if msg:
                await msg.reply_text("🚫 Aap block hain.")
            return
        return await func(update, context)
    return wrapper

# ══════════════════════════════════════════════
#  KEYBOARDS
# ══════════════════════════════════════════════

def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👤 Account",   callback_data="account"),
            InlineKeyboardButton("💰 Wallet",    callback_data="wallet"),
        ],
        [
            InlineKeyboardButton("🔗 Invite",    callback_data="invite"),
            InlineKeyboardButton("👥 Team",      callback_data="team"),
        ],
        [
            InlineKeyboardButton("📢 Channel",   callback_data="channel"),
            InlineKeyboardButton("💼 Work List", callback_data="worklist"),
        ],
    ])

def groups_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📌 Group 1 Join", url=GROUP_1)],
        [InlineKeyboardButton("📌 Group 2 Join", url=GROUP_2)],
        [InlineKeyboardButton("📌 Group 3 Join", url=GROUP_3)],
        [InlineKeyboardButton("✅ Maine Join Kar Liya — Next ▶️", callback_data="joined_groups")],
    ])

def back_keyboard(target: str = "main_menu") -> list:
    return [[InlineKeyboardButton("🔙 Back", callback_data=target)]]

def admin_panel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👥 Users",    callback_data="admin_users"),
            InlineKeyboardButton("📊 Stats",    callback_data="admin_stats"),
        ],
        [
            InlineKeyboardButton("💬 Activity", callback_data="admin_activity"),
            InlineKeyboardButton("🚫 Blocked",  callback_data="admin_blocked"),
        ],
        [InlineKeyboardButton("❌ Close", callback_data="admin_close")],
    ])

# ══════════════════════════════════════════════
#  SEND HELPER — message ya callback dono handle
# ══════════════════════════════════════════════

async def send_or_edit(update: Update, text: str, keyboard=None, edit=False):
    """Callback mein edit karo, command mein reply karo."""
    markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    if edit and update.callback_query:
        await update.callback_query.edit_message_text(
            text, parse_mode="Markdown", reply_markup=markup
        )
    elif update.callback_query:
        await update.callback_query.message.reply_text(
            text, parse_mode="Markdown", reply_markup=markup
        )
    else:
        await update.message.reply_text(
            text, parse_mode="Markdown", reply_markup=markup
        )

# ══════════════════════════════════════════════
#  /start COMMAND
# ══════════════════════════════════════════════

@block_check
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user   = update.effective_user
    args   = context.args
    ref_id = int(args[0]) if args and args[0].isdigit() else None
    u      = register_user(user, ref_id)   # ek hi call — register + return

    if not u.get("joined_groups"):
        await update.message.reply_text(
            "👋 *Welcome to WhatsApp Work Bot!* 👋\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ *Bot use karne ke liye pehle*\n"
            "*3 groups join karna COMPULSORY hai!*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "👇 Neeche teen groups join karo,\n"
            "phir *'Maine Join Kar Liya'* button dabao:",
            parse_mode="Markdown",
            reply_markup=groups_keyboard(),
        )
        return

    await show_main_menu(update, context)


async def show_main_menu(update: Update, context, edit=False):
    user = update.effective_user
    text = (
        f"👋 *Welcome to WhatsApp Work Bot!*\n\n"
        f"Hello *{user.first_name}!* 😊\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "💼 Yahan aap WhatsApp se paise kama sakte hain!\n"
        "Neeche se apna option chunein:\n"
        "━━━━━━━━━━━━━━━━━━━━━━"
    )
    await send_or_edit(update, text, main_menu_keyboard().inline_keyboard, edit=edit)

# ══════════════════════════════════════════════
#  CALLBACK SECTIONS — har section alag function
# ══════════════════════════════════════════════

async def cb_account(query, user, u):
    text = (
        "👤 *MY ACCOUNT*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📛 *Name:*      {u.get('name','N/A')}\n"
        f"🆔 *User ID:*   `{user.id}`\n"
        f"👤 *Username:*  {u.get('username','N/A')}\n"
        f"📅 *Joined:*    {u.get('joined','N/A')[:10]}\n"
        f"🕐 *Last Seen:* {u.get('last_seen','N/A')[:10]}\n"
        f"🔗 *Invites:*   {u.get('invites',0)}\n"
        "━━━━━━━━━━━━━━━━━━━━━━"
    )
    await query.edit_message_text(
        text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(back_keyboard())
    )

async def cb_wallet(query, u):
    invite_inc = u.get("invite_income", 0.0)
    work_inc   = u.get("work_income",   0.0)
    total      = u.get("total_wallet",  0.0)
    text = (
        "💰 *MY WALLET*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔗 *Invite Income:* ${invite_inc:.2f}\n"
        f"💼 *Work Income:*   ${work_inc:.2f}\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💵 *Total Balance:* ${total:.2f}\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚠️ *Min Withdraw:*  ${WITHDRAW_MIN:.2f}"
    )
    keyboard = [
        [InlineKeyboardButton("💸 Withdraw", callback_data="withdraw")],
        [InlineKeyboardButton("🔙 Back",     callback_data="main_menu")],
    ]
    await query.edit_message_text(
        text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def cb_withdraw(query, u):
    total = u.get("total_wallet", 0.0)
    if total < WITHDRAW_MIN:
        await query.edit_message_text(
            f"❌ *Withdraw Nahi Ho Sakta!*\n\n"
            f"Aapka balance: *${total:.2f}*\n"
            f"Minimum chahiye: *${WITHDRAW_MIN:.2f}*\n\n"
            "Aur invite karo ya work karo! 💪",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(back_keyboard())
        )
        return
    keyboard = [
        [InlineKeyboardButton("🇮🇳 INR (Bank/UPI)", callback_data="withdraw_inr")],
        [InlineKeyboardButton("💎 USDT (Crypto)",   callback_data="withdraw_usdt")],
        [InlineKeyboardButton("🔙 Back",            callback_data="wallet")],
    ]
    await query.edit_message_text(
        f"💸 *WITHDRAW REQUEST*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💵 *Available:* ${total:.2f}\n\n"
        "Withdrawal method chunein:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def cb_withdraw_method(query, context, data, u, user):
    method = "INR (Bank/UPI)" if data == "withdraw_inr" else "USDT (Crypto)"
    total  = u.get("total_wallet", 0.0)
    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                "💸 *NEW WITHDRAW REQUEST!*\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 *Name:*     {u.get('name')}\n"
                f"🆔 *User ID:*  `{user.id}`\n"
                f"👤 *Username:* {u.get('username','N/A')}\n"
                f"💵 *Amount:*   ${total:.2f}\n"
                f"💳 *Method:*   {method}\n"
                f"🕐 *Time:*     {now_str()}\n"
                "━━━━━━━━━━━━━━━━━━━━━━"
            ),
            parse_mode="Markdown",
        )
    except Exception:
        pass
    context.user_data["withdraw_method"] = method
    context.user_data["awaiting_withdraw_details"] = True
    detail_hint = "UPI ID / Bank Account Number" if data == "withdraw_inr" else "USDT Wallet Address (TRC20)"
    await query.edit_message_text(
        f"✅ *{method} Withdraw Request*\n\n"
        f"💵 Amount: *${total:.2f}*\n\n"
        f"Ab apni *{detail_hint}*\nyahan type karke bhejo 👇",
        parse_mode="Markdown",
    )

async def cb_invite(query, user, u):
    invite_link = f"{BOT_LINK}?start={user.id}"
    await query.edit_message_text(
        "🔗 *INVITE & EARN*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 *Per Invite:* ${INVITE_RATE:.2f}\n\n"
        f"📤 Apna invite link share karo:\n\n"
        f"`{invite_link}`\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ *Aapke Total Invites:* {u.get('invites',0)}\n"
        f"💵 *Invite Income:*       ${u.get('invite_income',0.0):.2f}\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "👆 Link copy karo aur dosto ko bhejo!\n"
        "Jab woh join karein — turant $0.50 milenge! 🎉",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(back_keyboard())
    )

async def cb_team(query, user, u):
    users_db = load_json(USERS_FILE)
    uid      = str(user.id)
    team     = [v for v in users_db.values() if v.get("referred_by") == uid]
    text = (
        "👥 *MY TEAM*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔗 *Total Members:* {len(team)}\n"
        f"💵 *Invite Income:* ${u.get('invite_income',0.0):.2f}\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
    )
    if team:
        text += "*Aapki Team:*\n\n"
        for i, m in enumerate(team[:15], 1):
            text += f"{i}. {m['name']} | {m.get('username','N/A')}\n"
        if len(team) > 15:
            text += f"\n_...aur {len(team)-15} aur members_"
    else:
        text += "😔 Abhi koi member nahi.\nInvite karo aur team banao!"
    await query.edit_message_text(
        text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(back_keyboard())
    )

async def cb_channel(query):
    keyboard = [
        [InlineKeyboardButton("📢 Channel Join Karo", url=GROUP_1)],
        [InlineKeyboardButton("🔙 Back", callback_data="main_menu")],
    ]
    await query.edit_message_text(
        "📢 *OFFICIAL CHANNEL*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "Hamare official channel join karo\n"
        "latest updates ke liye! 🔔\n"
        "━━━━━━━━━━━━━━━━━━━━━━",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def cb_worklist(query):
    keyboard = [
        [InlineKeyboardButton("📱 WhatsApp Rent",        callback_data="work_rent")],
        [InlineKeyboardButton("💰 WhatsApp Sell",        callback_data="work_sell")],
        [InlineKeyboardButton("🛒 WhatsApp Account Buy", callback_data="work_buy")],
        [InlineKeyboardButton("⚙️ Other Works",          callback_data="work_other")],
        [InlineKeyboardButton("🔙 Back",                 callback_data="main_menu")],
    ]
    await query.edit_message_text(
        "💼 *WORK LIST*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "Kaam chunein aur paise kamao! 💰",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

WORK_PAGES = {
    "work_rent": (
        "📱 *WHATSAPP RENT*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "Apna WhatsApp number rent pe do\n"
        f"aur har message pe paise kamao!\n\n"
        f"💵 *Rate:* ${WA_RENT_MIN:.4f} – ${WA_RENT_MAX:.4f} per message\n"
        "        (₹2.5 – ₹3.0 per message)\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📩 Apply karne ke liye admin se contact karo.\n"
        "Admin: @AdminUsername"
    ),
    "work_sell": (
        "💰 *WHATSAPP SELL*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "Apna WhatsApp number sell karo\n"
        "aur ek baar mein paise kamao!\n\n"
        f"💵 *Rate:* ${WA_SELL_RATE:.4f} per number\n"
        "        (₹2.5 per number)\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📩 Apply karne ke liye admin se contact karo.\n"
        "Admin: @AdminUsername"
    ),
    "work_buy": (
        "🛒 *WHATSAPP ACCOUNT BUY*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "Hum WhatsApp accounts khareedte hain!\n\n"
        "📋 *Requirements:*\n"
        "• Fresh / Old accounts dono chalenge\n"
        "• Number active hona chahiye\n"
        "• Price negotiate ho sakta hai\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📩 Admin se contact karo details ke liye."
    ),
}

async def cb_work_page(query, data):
    text = WORK_PAGES.get(data, "")
    if data == "work_other":
        await query.edit_message_text(
            "⚙️ *OTHER WORKS*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "🚧 *Coming Soon...*\n\n"
            "Yeh section abhi available nahi hai.\n"
            "Jald hi update aayega! 🔔\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "Updates ke liye channel join karo!",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(back_keyboard("worklist"))
        )
        return
    btn_label = "📩 Apply Now" if data in ("work_rent","work_sell") else "📩 Contact Admin"
    keyboard = [
        [InlineKeyboardButton(btn_label, url=f"https://t.me/{ADMIN_ID}")],
        [InlineKeyboardButton("🔙 Back", callback_data="worklist")],
    ]
    await query.edit_message_text(
        text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ══════════════════════════════════════════════
#  ADMIN PANEL HELPERS
# ══════════════════════════════════════════════

async def show_admin_panel(query):
    users   = load_json(USERS_FILE)
    blocked = load_json(BLOCKED_FILE)
    await query.edit_message_text(
        "🛡️ *ADMIN PANEL* 🛡️\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 *Total Users:* `{len(users)}`\n"
        f"✅ *Active:*      `{len(users)-len(blocked)}`\n"
        f"🚫 *Blocked:*     `{len(blocked)}`\n"
        "━━━━━━━━━━━━━━━━━━━━━━",
        parse_mode="Markdown",
        reply_markup=admin_panel_keyboard()
    )

async def show_admin_users(query):
    users   = load_json(USERS_FILE)
    blocked = load_json(BLOCKED_FILE)
    text    = "👥 *All Users:*\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for i, (uid, u) in enumerate(list(users.items())[:20], 1):
        s     = "🚫" if uid in blocked else "✅"
        text += f"{i}. {s} *{u['name']}*\n   🆔`{uid}` | {u.get('username','N/A')} | 💬{u.get('message_count',0)}\n\n"
    if len(users) > 20:
        text += f"_...aur {len(users)-20} users_"
    await query.edit_message_text(
        text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(back_keyboard("admin_panel"))
    )

async def show_admin_stats(query):
    users      = load_json(USERS_FILE)
    blocked    = load_json(BLOCKED_FILE)
    logs       = load_json(MESSAGES_FILE)
    total_msgs = sum(len(v.get("messages", [])) for v in logs.values())
    top5       = sorted(users.values(), key=lambda x: x.get("message_count", 0), reverse=True)[:5]
    text = (
        "📊 *BOT STATS:*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 Total Users:   `{len(users)}`\n"
        f"✅ Active:        `{len(users)-len(blocked)}`\n"
        f"🚫 Blocked:       `{len(blocked)}`\n"
        f"💬 Total Msgs:    `{total_msgs}`\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "🏆 *Top 5 Active:*\n\n"
    )
    for i, u in enumerate(top5, 1):
        text += f"{i}. *{u['name']}* — {u.get('message_count',0)} msgs\n"
    await query.edit_message_text(
        text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(back_keyboard("admin_panel"))
    )

async def show_admin_activity(query):
    logs  = load_json(MESSAGES_FILE)
    text  = "💬 *Recent Activity:*\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    count = 0
    for uid, data in logs.items():
        if count >= 10: break
        msgs = data.get("messages", [])
        if msgs:
            last  = msgs[-1]
            text += f"👤 *{data['name']}* (`{uid}`)\n📝 {last['text'][:50]}\n🕐 {last['time']}\n\n"
            count += 1
    text += "\n💡 Full activity: `/activity <user_id>`"
    await query.edit_message_text(
        text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(back_keyboard("admin_panel"))
    )

async def show_admin_blocked(query):
    blocked = load_json(BLOCKED_FILE)
    if not blocked:
        text = "🚫 *Blocked Users*\n\nKoi blocked nahi."
    else:
        text = "🚫 *Blocked Users:*\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
        for i, (uid, d) in enumerate(blocked.items(), 1):
            text += f"{i}. *{d.get('name','?')}* | `{uid}`\n"
        text += "\n✅ Unblock: `/unblock <id>`"
    await query.edit_message_text(
        text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(back_keyboard("admin_panel"))
    )

# ══════════════════════════════════════════════
#  MAIN CALLBACK HANDLER (dispatch table)
# ══════════════════════════════════════════════

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data  = query.data
    user  = update.effective_user

    if is_blocked(user.id):
        await query.answer("🚫 Aap block hain.", show_alert=True)
        return

    u = get_user(user.id)   # cache hit — fast

    # ── Dispatch Table — if/elif chain se fast ──
    if data == "joined_groups":
        update_user(user.id, {"joined_groups": True})
        await query.edit_message_text(
            "✅ *Shukriya! Groups join karne ke liye!*\n\n"
            "Ab aap bot use kar sakte hain! 🎉",
            parse_mode="Markdown",
        )
        await show_main_menu(update, context)

    elif data == "main_menu":
        await show_main_menu(update, context, edit=True)

    elif data == "account":    await cb_account(query, user, u)
    elif data == "wallet":     await cb_wallet(query, u)
    elif data == "withdraw":   await cb_withdraw(query, u)
    elif data in ("withdraw_inr", "withdraw_usdt"):
        await cb_withdraw_method(query, context, data, u, user)
    elif data == "invite":     await cb_invite(query, user, u)
    elif data == "team":       await cb_team(query, user, u)
    elif data == "channel":    await cb_channel(query)
    elif data == "worklist":   await cb_worklist(query)
    elif data in ("work_rent", "work_sell", "work_buy", "work_other"):
        await cb_work_page(query, data)

    # ── Admin ──
    elif data == "admin_panel":
        if is_admin(user.id): await show_admin_panel(query)
    elif data == "admin_users":
        if is_admin(user.id): await show_admin_users(query)
    elif data == "admin_stats":
        if is_admin(user.id): await show_admin_stats(query)
    elif data == "admin_activity":
        if is_admin(user.id): await show_admin_activity(query)
    elif data == "admin_blocked":
        if is_admin(user.id): await show_admin_blocked(query)
    elif data == "admin_close":
        await query.edit_message_text("✅ Admin panel band ho gaya.")

# ══════════════════════════════════════════════
#  ADMIN COMMANDS
# ══════════════════════════════════════════════

@admin_only
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    users   = load_json(USERS_FILE)
    blocked = load_json(BLOCKED_FILE)
    await update.message.reply_text(
        "🛡️ *ADMIN PANEL* 🛡️\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 *Total Users:* `{len(users)}`\n"
        f"✅ *Active:*      `{len(users)-len(blocked)}`\n"
        f"🚫 *Blocked:*     `{len(blocked)}`\n"
        "━━━━━━━━━━━━━━━━━━━━━━",
        parse_mode="Markdown",
        reply_markup=admin_panel_keyboard()
    )

@admin_only
async def block_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Usage: `/block 123456789`", parse_mode="Markdown")
        return
    uid     = context.args[0]
    users   = load_json(USERS_FILE)
    blocked = load_json(BLOCKED_FILE)
    name    = users.get(uid, {}).get("name", "Unknown")
    blocked[uid] = {"name": name, "blocked_at": now_str()}
    save_json(BLOCKED_FILE, blocked)
    await update.message.reply_text(f"🚫 `{uid}` ({name}) block!", parse_mode="Markdown")

@admin_only
async def unblock_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Usage: `/unblock 123456789`", parse_mode="Markdown")
        return
    uid     = context.args[0]
    blocked = load_json(BLOCKED_FILE)
    if uid in blocked:
        name = blocked.pop(uid).get("name", uid)
        save_json(BLOCKED_FILE, blocked)
        await update.message.reply_text(f"✅ `{uid}` ({name}) unblock!", parse_mode="Markdown")
    else:
        await update.message.reply_text("❌ Blocked nahi hai.")

@admin_only
async def activity_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Usage: `/activity 123456789`", parse_mode="Markdown")
        return
    uid  = context.args[0]
    logs = load_json(MESSAGES_FILE)
    if uid not in logs:
        await update.message.reply_text("❌ Koi activity nahi mili.")
        return
    msgs = logs[uid]["messages"][-10:]
    text = f"💬 *{logs[uid]['name']} ki Activity:*\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for i, m in enumerate(reversed(msgs), 1):
        text += f"{i}. `{m['time']}`\n   📝 {m['text'][:60]}\n\n"
    await update.message.reply_text(text, parse_mode="Markdown")

@admin_only
async def addbalance_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) < 2:
        await update.message.reply_text("Usage: `/addbalance 123456789 5.0`", parse_mode="Markdown")
        return
    uid, amt = context.args[0], float(context.args[1])
    users = load_json(USERS_FILE)
    if uid not in users:
        await update.message.reply_text("❌ User nahi mila.")
        return
    users[uid]["work_income"]  = round(users[uid].get("work_income",  0) + amt, 2)
    users[uid]["total_wallet"] = round(users[uid].get("total_wallet", 0) + amt, 2)
    save_json(USERS_FILE, users)
    name = users[uid]["name"]
    await update.message.reply_text(
        f"✅ `{name}` ko *${amt:.2f}* work income add ho gaya!",
        parse_mode="Markdown"
    )
    try:
        await context.bot.send_message(
            chat_id=int(uid),
            text=f"🎉 *${amt:.2f} aapke wallet mein add ho gaya!*\n\nWork income credited! 💰",
            parse_mode="Markdown",
        )
    except Exception:
        pass

# ══════════════════════════════════════════════
#  MESSAGE HANDLER
# ══════════════════════════════════════════════

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    register_user(user)   # cache hit — no extra disk read

    if is_blocked(user.id):
        await update.message.reply_text("🚫 Aap block hain.")
        return

    msg = update.message.text
    log_message(user, msg)

    # Withdraw details pending?
    if context.user_data.get("awaiting_withdraw_details"):
        method = context.user_data.get("withdraw_method", "N/A")
        u      = get_user(user.id)
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=(
                    "💸 *WITHDRAW DETAILS RECEIVED!*\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"👤 *Name:*    {u.get('name')}\n"
                    f"🆔 *User ID:* `{user.id}`\n"
                    f"💵 *Amount:*  ${u.get('total_wallet',0):.2f}\n"
                    f"💳 *Method:*  {method}\n"
                    f"📋 *Details:* `{msg}`\n"
                    "━━━━━━━━━━━━━━━━━━━━━━"
                ),
                parse_mode="Markdown",
            )
        except Exception:
            pass
        context.user_data["awaiting_withdraw_details"] = False
        await update.message.reply_text(
            "✅ *Withdraw request submit ho gayi!*\n\n"
            "Admin 24 ghante mein process karega. 🙏",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(),
        )
        return

    # Admin ko notification
    if not is_admin(user.id):
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=(
                    f"📩 *New Message!*\n"
                    f"👤 {user.full_name} | `{user.id}`\n"
                    f"📝 {msg[:100]}"
                ),
                parse_mode="Markdown",
            )
        except Exception:
            pass

    await update.message.reply_text(
        "✅ Message mila!\n\n/start karein ya neeche menu se option chunein.",
        reply_markup=main_menu_keyboard(),
    )

# ══════════════════════════════════════════════
#  ERROR HANDLER
# ══════════════════════════════════════════════

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f"Error: {context.error}", exc_info=context.error)

# ══════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════

def main() -> None:
    print("💼 WhatsApp Work Bot v4.0 (Optimized) shuru ho raha hai...")
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start",      start_command))
    app.add_handler(CommandHandler("admin",      admin_command))
    app.add_handler(CommandHandler("block",      block_command))
    app.add_handler(CommandHandler("unblock",    unblock_command))
    app.add_handler(CommandHandler("activity",   activity_command))
    app.add_handler(CommandHandler("addbalance", addbalance_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)

    print("✅ Bot chal raha hai!\n")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
