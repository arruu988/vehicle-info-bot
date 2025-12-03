import re
import sqlite3
import requests
import telebot
import time
from telebot import types
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import logging
import os
from datetime import date
import datetime
from threading import Thread
from flask import Flask

# Bot Token
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8133993773:AAHUPt2Irj1LXC7QjV-tl00t-uo0fGbjyoc")
bot = telebot.TeleBot(BOT_TOKEN)

# Config
ADMIN_ID = int(os.environ.get("ADMIN_ID", "8472134640"))
DB_FILE = "users.db"

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Database
class Database:
    def __init__(self, db_file):
        self.db_file = db_file
        self._create_tables()
    
    def get_cursor(self):
        conn = sqlite3.connect(self.db_file)
        return conn.cursor()
    
    def _create_tables(self):
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users
                     (user_id INTEGER PRIMARY KEY, credits INTEGER DEFAULT 5, 
                      last_credit_date TEXT, is_blocked INTEGER DEFAULT 0)''')
        c.execute('''CREATE TABLE IF NOT EXISTS history
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, 
                      query TEXT, api_type TEXT, ts TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS blocked_users
                     (user_id INTEGER PRIMARY KEY, blocked_by INTEGER, 
                      reason TEXT, blocked_at TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS profile_views 
                     (user_id INTEGER, date TEXT, count INTEGER, PRIMARY KEY (user_id, date))''')
        conn.commit()
        conn.close()

db = Database(DB_FILE)

# Special Users
SPECIAL_USERS = [{"id": 8472134640, "name": "Admin"}]

def is_admin(user_id):
    return user_id == ADMIN_ID

def is_special_user(user_id):
    return any(user["id"] == user_id for user in SPECIAL_USERS)

def init_user(user_id):
    cur = db.get_cursor()
    cur.execute("INSERT OR IGNORE INTO users (user_id, credits) VALUES (?, 5)", (user_id,))
    cur.connection.commit()

def get_credits(user_id):
    cur = db.get_cursor()
    cur.execute("SELECT credits FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    return row[0] if row else 0

def set_credits(user_id, credits):
    cur = db.get_cursor()
    cur.execute("UPDATE users SET credits=? WHERE user_id=?", (credits, user_id))
    cur.connection.commit()

def change_credits(user_id, amount):
    cur = db.get_cursor()
    cur.execute("UPDATE users SET credits = credits + ? WHERE user_id=?", (amount, user_id))
    cur.connection.commit()
    return get_credits(user_id)

def add_history(user_id, query, api_type):
    cur = db.get_cursor()
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    cur.execute("INSERT INTO history (user_id, query, api_type, ts) VALUES (?, ?, ?, ?)",
                (user_id, query, api_type, ts))
    cur.connection.commit()

def refund_credit(user_id):
    cur = db.get_cursor()
    cur.execute("UPDATE users SET credits = credits + 1 WHERE user_id=?", (user_id,))
    cur.connection.commit()

def is_user_blocked(user_id):
    cur = db.get_cursor()
    cur.execute("SELECT is_blocked FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    return row and row[0] == 1

def block_user(user_id, blocked_by, reason=""):
    try:
        cur = db.get_cursor()
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        cur.execute("INSERT OR REPLACE INTO blocked_users (user_id, blocked_by, reason, blocked_at) VALUES (?, ?, ?, ?)",
                    (user_id, blocked_by, reason, ts))
        cur.execute("UPDATE users SET is_blocked=1 WHERE user_id=?", (user_id,))
        cur.connection.commit()
        return True
    except Exception as e:
        logger.error(f"Error blocking user {user_id}: {e}")
        return False

def unblock_user(user_id):
    try:
        cur = db.get_cursor()
        cur.execute("DELETE FROM blocked_users WHERE user_id=?", (user_id,))
        cur.execute("UPDATE users SET is_blocked=0 WHERE user_id=?", (user_id,))
        cur.connection.commit()
        return True
    except Exception as e:
        logger.error(f"Error unblocking user {user_id}: {e}")
        return False

def get_last_credit_date(user_id):
    cur = db.get_cursor()
    cur.execute("SELECT last_credit_date FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    return row[0] if row else None

def check_and_give_daily_credits(user_id):
    today = date.today().isoformat()
    last_date = get_last_credit_date(user_id)
    if last_date != today:
        cur = db.get_cursor()
        cur.execute("UPDATE users SET credits=credits+10, last_credit_date=? WHERE user_id=?", 
                   (today, user_id))
        cur.connection.commit()
        return True
    return False

def send_long(chat_id, text, max_length=4096):
    if len(text) <= max_length:
        bot.send_message(chat_id, text, parse_mode="HTML")
    else:
        parts = [text[i:i+max_length] for i in range(0, len(text), max_length)]
        for part in parts:
            bot.send_message(chat_id, part, parse_mode="HTML")
            time.sleep(0.1)

def make_request(url, timeout=30):
    try:
        session = requests.Session()
        retry = Retry(total=3, backoff_factor=0.1, status_forcelist=[500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        response = session.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        try:
            return response.json()
        except ValueError:
            return response.text
    except Exception as e:
        logger.error(f"Request error for {url}: {e}")
        return None

def handle_errors(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {e}", exc_info=True)
            try:
                if len(args) > 0 and hasattr(args[0], 'chat') and hasattr(args[0].chat, 'id'):
                    bot.send_message(args[0].chat.id, "❌ An error occurred. Please try again later.")
            except:
                pass
    return wrapper

def clean(text):
    if text is None:
        return None
    text = str(text).strip()
    if not text or text.lower() in ['null', 'none', 'nil', 'nan', '']:
        return None
    return text

@handle_errors
def ensure_and_charge(uid: int, chat_id: int) -> bool:
    if is_user_blocked(uid):
        bot.send_message(chat_id, "⚠️ Your account has been blocked. Contact @Maarjauky")
        return False
    init_user(uid)
    if is_special_user(uid):
        return True
    credits = get_credits(uid)
    if credits <= 0:
        kb = types.InlineKeyboardMarkup(row_width=1)
        btn1 = types.InlineKeyboardButton("💳 Buy Credits", callback_data="buy_credits")
        kb.add(btn1)
        bot.send_message(chat_id, "❌ No credits left. Buy from @Maarjauky", reply_markup=kb)
        return False
    set_credits(uid, credits - 1)
    return True

# Start Command
@bot.message_handler(commands=["start"])
@handle_errors
def cmd_start(m):
    try:
        uid = m.from_user.id
        chat_id = m.chat.id
        if is_user_blocked(uid):
            bot.send_message(chat_id, "⚠️ Account blocked. Contact @Maarjauky")
            return
        init_user(uid)
        if is_special_user(uid):
            set_credits(uid, 999)
        if not is_special_user(uid):
            check_and_give_daily_credits(uid)
        credits = get_credits(uid)
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        kb.add(types.KeyboardButton("👤 Telegram ID Info"), types.KeyboardButton("🇮🇳 India Number Info"))
        kb.add(types.KeyboardButton("📱 Pakistan Number Info"), types.KeyboardButton("📮 Pincode Info"))
        kb.add(types.KeyboardButton("🚘 Vehicle Info"), types.KeyboardButton("🆔 Aadhaar Info"))
        kb.add(types.KeyboardButton("🧪 ICMR Number Info"), types.KeyboardButton("🏦 IFSC Code Info"))
        kb.add(types.KeyboardButton("💸 UPI ID Info"), types.KeyboardButton("📋 Ration Card Info"))
        kb.add(types.KeyboardButton("🌐 IP Info"), types.KeyboardButton("🎮 Free Fire Info"))
        kb.add(types.KeyboardButton("👀 Free Fire Views"), types.KeyboardButton("💳 My Credits"))
        kb.add(types.KeyboardButton("💳 Buy Credits"), types.KeyboardButton("🎁 Get Daily Credits"), types.KeyboardButton("📜 My History"))
        kb.add(types.KeyboardButton("📞 Contact Admin"), types.KeyboardButton("🆔 My ID"))
        if is_admin(uid):
            kb.add(types.KeyboardButton("⚙️ Admin Panel"))
        start_text = f"""🤖 <b>InfoBot</b>
━━━━━━━━━━━━━━━━━━
🔍 Available Services:
• 👤 Telegram ID Info • 🇮🇳 India Number Info
• 📱 Pakistan Number Info • 📮 Pincode Details
• 🚘 Vehicle Info • 🆔 Aadhaar Info
• 🧪 ICMR Number Info • 🏦 IFSC Code Info
• 💸 UPI ID Info • 📋 Ration Card Info
• 🌐 IP Info • 🎮 Free Fire Info
• 👀 Free Fire Views

💳 Your Credits: {credits}
🎁 Daily Credits: 10 free daily
📞 Contact: @Maarjauky
━━━━━━━━━━━━━━━━━━"""
        bot.send_message(chat_id, start_text, reply_markup=kb, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error in start: {e}")
        bot.send_message(m.chat.id, "🚀 Welcome to InfoBot!")

# Basic Buttons
@bot.message_handler(func=lambda c: c.text == "🆔 My ID")
@handle_errors
def btn_myid(m):
    bot.send_message(m.chat.id, f"🆔 Your ID: <code>{m.from_user.id}</code>", parse_mode="HTML")

@bot.message_handler(func=lambda c: c.text == "💳 My Credits")
@handle_errors
def my_credits_btn(m):
    uid = m.from_user.id
    credits = get_credits(uid)
    if is_special_user(uid):
        bot.send_message(m.chat.id, f"💳 Credits: <b>{credits}</b> (Special User)", parse_mode="HTML")
    else:
        bot.send_message(m.chat.id, f"💳 Credits: <b>{credits}</b>", parse_mode="HTML")

@bot.message_handler(func=lambda c: c.text == "📞 Contact Admin")
@handle_errors
def contact_admin_btn(m):
    kb = types.InlineKeyboardMarkup()
    btn = types.InlineKeyboardButton("📞 Contact", url="https://t.me/Maarjauky")
    kb.add(btn)
    bot.send_message(m.chat.id, "Contact @Maarjauky", reply_markup=kb)

@bot.message_handler(func=lambda c: c.text == "🎁 Get Daily Credits")
@handle_errors
def daily_credits_btn(m):
    uid = m.from_user.id
    init_user(uid)
    if is_special_user(uid):
        bot.send_message(m.chat.id, "🌟 Special user - unlimited credits")
    elif check_and_give_daily_credits(uid):
        credits = get_credits(uid)
        bot.send_message(m.chat.id, f"✅ 10 credits added! Total: {credits}")
    else:
        last_date = get_last_credit_date(uid)
        bot.send_message(m.chat.id, f"❌ Already claimed today. Last: {last_date}")

# Buy Credits
@bot.message_handler(func=lambda c: c.text == "💳 Buy Credits")
@handle_errors
def buy_credits_btn(m):
    uid = m.from_user.id
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("💎 100 Credits - ₹200", callback_data="buy_100"))
    kb.add(types.InlineKeyboardButton("💎 200 Credits - ₹300", callback_data="buy_200"))
    kb.add(types.InlineKeyboardButton("💎 500 Credits - ₹500", callback_data="buy_500"))
    kb.add(types.InlineKeyboardButton("🔄 Custom Amount", callback_data="buy_custom"))
    buy_text = f"""💳 <b>Credit Packs</b>
━━━━━━━━━━━━━━━━━━
💎 100 Credits - ₹200
💎 200 Credits - ₹300
💎 500 Credits - ₹500
━━━━━━━━━━━━━━━━━━
📥 Payment: DM @Maarjauky
💳 Your Credits: {get_credits(uid)}"""
    bot.send_message(m.chat.id, buy_text, reply_markup=kb, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
@handle_errors
def handle_buy_callback(call):
    uid = call.from_user.id
    if call.data == "buy_100":
        amount = "100 Credits for ₹200"
    elif call.data == "buy_200":
        amount = "200 Credits for ₹300"
    elif call.data == "buy_500":
        amount = "500 Credits for ₹500"
    elif call.data == "buy_custom":
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "DM @Maarjauky for custom amounts")
        return
    payment_text = f"""💳 <b>Payment Instructions</b>
━━━━━━━━━━━━━━━━━━
Selected: {amount}
📥 Payment Method: DM @Maarjauky
Send screenshot with your ID: {uid}"""
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, payment_text, parse_mode="HTML")

# My History
@bot.message_handler(func=lambda c: c.text == "📜 My History")
@handle_errors
def my_history_btn(m):
    uid = m.from_user.id
    cur = db.get_cursor()
    cur.execute("SELECT query, api_type, ts FROM history WHERE user_id=? ORDER BY id DESC", (uid,))
    rows = cur.fetchall()
    if not rows:
        bot.send_message(m.chat.id, "❌ No history found")
        return
    out = "📜 Your History:\n\n"
    for q, t, ts in rows[:20]:
        out += f"[{ts}] ({t}) {q}\n"
    send_long(m.chat.id, out)

# Telegram ID Info
@bot.message_handler(func=lambda c: c.text == "👤 Telegram ID Info")
@handle_errors
def ask_tgid(m):
    bot.send_message(m.chat.id, "📩 Send Telegram User ID:")
    bot.register_next_step_handler(m, handle_tgid)

@handle_errors
def handle_tgid(m):
    if not m.text:
        bot.send_message(m.chat.id, "⚠️ Please send a numeric ID")
        return
    q = m.text.strip()
    if not re.fullmatch(r"\d+", q):
        bot.send_message(m.chat.id, "⚠️ Invalid ID")
        return
    if not ensure_and_charge(m.from_user.id, m.chat.id):
        return
    progress = bot.send_message(m.chat.id, "🔍 Searching...")
    data = make_request(f"https://tg-info-neon.vercel.app/user-details?user={q}")
    bot.delete_message(m.chat.id, progress.message_id)
    if not data or not data.get("success"):
        refund_credit(m.from_user.id)
        bot.send_message(m.chat.id, "❌ No data found")
        return
    d = data.get("data", {})
    first_name = d.get('first_name', 'N/A')
    last_name = d.get('last_name', '')
    full_name = f"{first_name} {last_name}".strip() if last_name else first_name
    is_bot = d.get('is_bot', False)
    bot_emoji = "🤖" if is_bot else "👤"
    out = f"""{bot_emoji} <b>Telegram Info</b>
━━━━━━━━━━━━━━━━━━
🆔 User ID: <code>{d.get('id', 'N/A')}</code>
👤 Name: {full_name}
🤖 Is Bot: {is_bot}
💬 Total Messages: {d.get('total_msg_count', '0')}
👥 Total Groups: {d.get('total_groups', '0')}
━━━━━━━━━━━━━━━━━━"""
    bot.send_message(m.chat.id, out, parse_mode="HTML")
    add_history(m.from_user.id, q, "TG_INFO")

# India Number Info
@bot.message_handler(func=lambda message: message.text == "🇮🇳 India Number Info")
@handle_errors
def ask_india_number(message):
    bot.send_message(message.chat.id, "📱 Send 10-digit Indian number:")
    bot.register_next_step_handler(message, handle_india_number_response)

@handle_errors
def handle_india_number_response(message):
    if not message.text:
        bot.send_message(message.chat.id, "⚠️ Please send a number")
        return
    num = message.text.strip()
    if not re.fullmatch(r"\d{10}", num):
        bot.send_message(message.chat.id, "⚠️ Invalid 10-digit number")
        return
    if not ensure_and_charge(message.from_user.id, message.chat.id):
        return
    progress = bot.send_message(message.chat.id, "🔍 Searching...")
    try:
        r = requests.get(f"https://demon.taitanx.workers.dev/?mobile={num}", timeout=30)
        bot.delete_message(message.chat.id, progress.message_id)
        if r.status_code != 200:
            refund_credit(message.from_user.id)
            bot.send_message(message.chat.id, "❌ API error")
            return
        data = r.json()
        data_list = data.get("data", [])
        if not data_list:
            refund_credit(message.from_user.id)
            bot.send_message(message.chat.id, "📭 No data found")
            return
        header = f"""📱 <b>Number Lookup</b>
🔍 Number: {num}
📊 Records: {len(data_list)}
━━━━━━━━━━━━━━━━━━"""
        bot.send_message(message.chat.id, header, parse_mode="HTML")
        for i, rec in enumerate(data_list[:5], 1):
            name = clean(rec.get("name", "N/A"))
            mobile = clean(rec.get("mobile", "N/A"))
            circle = clean(rec.get("circle", "N/A"))
            out = f"""📋 Record #{i}
👤 Name: {name}
📱 Mobile: {mobile}
🌐 Circle: {circle}
━━━━━━━━━━━━━━━━━━"""
            bot.send_message(message.chat.id, out, parse_mode="HTML")
        add_history(message.from_user.id, num, "IND_NUMBER")
    except Exception as e:
        refund_credit(message.from_user.id)
        bot.send_message(message.chat.id, "❌ Error occurred")

# Admin Panel
@bot.message_handler(func=lambda c: c.text == "⚙️ Admin Panel")
@handle_errors
def admin_panel(m):
    if not is_admin(m.from_user.id):
        return
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("💳 Add Credits", "💸 Remove Credits")
    kb.row("👥 All Users", "📋 User History")
    kb.row("📢 Broadcast", "🌟 Special Users")
    kb.row("🚫 Block User", "✅ Unblock User")
    kb.row("🔙 Back to Main Menu")
    bot.send_message(m.chat.id, "⚙️ Admin Panel", reply_markup=kb)

@bot.message_handler(func=lambda c: c.text == "🔙 Back to Main Menu")
@handle_errors
def back_to_main(m):
    cmd_start(m)

# Web Server for Render
app = Flask('app')
@app.route('/')
def home():
    return "Bot is running!"
def run():
    app.run(host='0.0.0.0', port=8080)
def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

# Start Bot
if __name__ == "__main__":
    keep_alive()
    logger.info("Starting bot...")
    bot.polling(none_stop=True)

