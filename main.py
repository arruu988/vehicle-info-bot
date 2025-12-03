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

# ========== BOT INITIALIZATION ==========
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8133993773:AAHUPt2Irj1LXC7QjV-tl00t-uo0fGbjyoc")
bot = telebot.TeleBot(BOT_TOKEN)

# ========== CONFIG ==========
ADMIN_ID = int(os.environ.get("ADMIN_ID", "8472134640"))
DB_FILE = "users.db"

# ========== CHANNEL CONFIG ==========
CHANNEL_USERNAME = ""
CHANNEL_LINK = ""
CHANNEL_ID = ""

# ========== LOGGING SETUP ==========
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ========== DATABASE SETUP ==========
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

# ========== SPECIAL USERS ==========
SPECIAL_USERS = [
    {"id": 8472134640, "name": "Admin"},
]

# ========== UTILITY FUNCTIONS ==========
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
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
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

# ========== CHANNEL FUNCTIONS ==========
def check_channel_membership(user_id):
    try:
        if not CHANNEL_ID:
            return True
        chat_member = bot.get_chat_member(CHANNEL_ID, user_id)
        return chat_member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logger.error(f"Error checking channel membership for {user_id}: {e}")
        return False

def send_channel_join_message(chat_id):
    if not CHANNEL_LINK:
        return
    keyboard = types.InlineKeyboardMarkup()
    join_button = types.InlineKeyboardButton("📢 Join Our Channel", url=CHANNEL_LINK)
    check_button = types.InlineKeyboardButton("✅ I've Joined", callback_data="check_join")
    keyboard.add(join_button)
    keyboard.add(check_button)
    
    message_text = """🔒 <b>Channel Membership Required</b>

▀▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▀

┊  JOIN OUR CHANNEL  ┊

▄▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▄

👇 Click the button below to join our channel, then click "I've Joined" to verify."""
    
    bot.send_message(chat_id, message_text, reply_markup=keyboard, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data == "check_join")
@handle_errors
def check_join_callback(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    
    if check_channel_membership(user_id):
        bot.answer_callback_query(call.id, "✅ Verification successful! Welcome to InfoBot!")
        bot.delete_message(chat_id, call.message.message_id)
        cmd_start(call.message)
    else:
        bot.answer_callback_query(call.id, "❌ You haven't joined the channel yet. Please join and try again.")

# ========== ENSURE AND CHARGE FUNCTION ==========
@handle_errors
def ensure_and_charge(uid: int, chat_id: int) -> bool:
    if CHANNEL_ID:
        if not is_admin(uid) and not is_special_user(uid) and not check_channel_membership(uid):
            send_channel_join_message(chat_id)
            return False
        
    if is_user_blocked(uid):
        bot.send_message(chat_id, "⚠️ <b>Your account has been blocked.</b>\n\nContact @Maarjauky for more information.")
        return False
        
    init_user(uid)
    
    if is_special_user(uid):
        return True
        
    credits = get_credits(uid)
    if credits <= 0:
        kb = types.InlineKeyboardMarkup(row_width=1)
        btn1 = types.InlineKeyboardButton("💳 Buy Credits", callback_data="buy_credits")
        kb.add(btn1)
        
        message_text = "❌ <b>No credits left.</b>\n\nYou can purchase more credits from @Maarjauky"
        
        bot.send_message(chat_id, message_text, reply_markup=kb)
        return False
    set_credits(uid, credits - 1)
    return True

# ========== START COMMAND ==========
@bot.message_handler(commands=["start"])
@handle_errors
def cmd_start(m):
    try:
        uid = m.from_user.id
        chat_id = m.chat.id
        
        logger.info(f"Start command received from user {uid}")
        
        if is_user_blocked(uid):
            bot.send_message(chat_id, "⚠️ <b>Your account has been blocked.</b>\n\nContact @Maarjauky for more information.")
            return

        init_user(uid)

        if is_special_user(uid):
            set_credits(uid, 999)
            logger.info(f"Set unlimited credits for special user {uid}")

        if not is_special_user(uid):
            if check_and_give_daily_credits(uid):
                logger.info(f"Daily credits given to user {uid}")

        credits = get_credits(uid)

        kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        
        kb.add(
            types.KeyboardButton("👤 Telegram ID Info"),
            types.KeyboardButton("🇮🇳 India Number Info")
        )
        kb.add(
            types.KeyboardButton("📱 Pakistan Number Info"), 
            types.KeyboardButton("📮 Pincode Info")
        )
        kb.add(
            types.KeyboardButton("🚘 Vehicle Info"),
            types.KeyboardButton("🆔 Aadhaar Info")
        )
        kb.add(
            types.KeyboardButton("🧪 ICMR Number Info"),
            types.KeyboardButton("🏦 IFSC Code Info")
        )
        kb.add(
            types.KeyboardButton("💸 UPI ID Info"),
            types.KeyboardButton("📋 Ration Card Info")
        )
        kb.add(
            types.KeyboardButton("🌐 IP Info"),
            types.KeyboardButton("🎮 Free Fire Info")
        )
        kb.add(
            types.KeyboardButton("👀 Free Fire Views"),
            types.KeyboardButton("💳 My Credits")
        )
        kb.add(
            types.KeyboardButton("💳 Buy Credits"),
            types.KeyboardButton("🎁 Get Daily Credits"),
            types.KeyboardButton("📜 My History")
        )
        kb.add(
            types.KeyboardButton("📞 Contact Admin"),
            types.KeyboardButton("🆔 My ID")
        )
        
        if is_admin(uid):
            kb.add(types.KeyboardButton("⚙️ Admin Panel"))
                
        start_text = f"""
━━━━━━━━━━━━━━━━━━
🤖 <b>InfoBot</b>
<i>Your Digital Info Assistant 🚀</i>
━━━━━━━━━━━━━━━━━━

🔍 <b>Available Services:</b>
• 👤 Telegram ID Info
• 🇮🇳 India Number Info  
• 📱 Pakistan Number Info
• 📮 Pincode Details
• 🚘 Vehicle Info
• 🆔 Aadhaar Info
• 🧪 ICMR Number Info
• 🏦 IFSC Code Info
• 💸 UPI ID Info
• 📋 Ration Card Info
• 🌐 IP Info
• 🎮 Free Fire Info
• 👀 Free Fire Views

💳 <b>Your Credits:</b> <code>{credits}</code>
🎁 <b>Daily Credits:</b> Get 10 free credits every day!

📞 <b>Contact Admin:</b> @Maarjauky
💳 <b>Buy Credits:</b> DM @Maarjauky

⚠️ Each search costs <b>1 credit</b>.
Credits are refunded if no results found.

✅ <b>Choose an option below to begin!</b>

━━━━━━━━━━━━━━━━━━
© 2025 <b>InfoBot</b> | All Rights Reserved
━━━━━━━━━━━━━━━━━━
"""
        bot.send_message(
            chat_id, 
            start_text, 
            reply_markup=kb, 
            disable_web_page_preview=True, 
            parse_mode="HTML"
        )
        logger.info(f"Start message sent successfully to user {uid}")
        
    except Exception as e:
        logger.error(f"Critical error in start command: {e}", exc_info=True)
        bot.send_message(m.chat.id, "🚀 Welcome to InfoBot! Please use the menu buttons to get started.")

# ========== IP INFO ==========
@bot.message_handler(func=lambda c: c.text == "🌐 IP Info")
@handle_errors
def ask_ip_address(m):
    bot.send_message(m.chat.id, "🌐 Send IP address to get information (e.g., 8.8.8.8):")
    bot.register_next_step_handler(m, handle_ip_info)

@handle_errors
def handle_ip_info(m):
    user_id = m.from_user.id
    chat_id = m.chat.id
    
    try:
        if not m.text or not m.text.strip():
            return bot.send_message(chat_id, "⚠️ Please send a valid IP address.")
        
        ip = m.text.strip()
        
        if not re.fullmatch(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', ip):
            return bot.send_message(chat_id, "❌ Invalid IP address format. Please use format like 8.8.8.8")
        
        octets = ip.split('.')
        for octet in octets:
            try:
                octet_num = int(octet)
                if not 0 <= octet_num <= 255:
                    return bot.send_message(chat_id, "❌ Invalid IP address. Octets must be between 0-255.")
            except ValueError:
                return bot.send_message(chat_id, "❌ Invalid IP address.")
        
        if not ensure_and_charge(user_id, chat_id):
            return
        
        progress_msg = bot.send_message(chat_id, "🔍 Searching IP information...")
        
        try:
            url = f"http://ip-api.com/json/{ip}?fields=status,message,country,countryCode,region,regionName,city,zip,lat,lon,timezone,isp,org,as,query"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('status') == 'success':
                    ip_data = {
                        'ip': data.get('query', ip),
                        'country': data.get('country'),
                        'countryCode': data.get('countryCode'),
                        'region': data.get('regionName'),
                        'city': data.get('city'),
                        'zip': data.get('zip'),
                        'lat': data.get('lat'),
                        'lon': data.get('lon'),
                        'timezone': data.get('timezone'),
                        'isp': data.get('isp'),
                        'org': data.get('org'),
                        'as': data.get('as'),
                    }
                else:
                    refund_credit(user_id)
                    bot.delete_message(chat_id, progress_msg.message_id)
                    return bot.send_message(chat_id, f"❌ {data.get('message', 'IP not found')}")
            else:
                refund_credit(user_id)
                bot.delete_message(chat_id, progress_msg.message_id)
                return bot.send_message(chat_id, "❌ Failed to fetch IP information.")
                
        except Exception as e:
            refund_credit(user_id)
            bot.delete_message(chat_id, progress_msg.message_id)
            return bot.send_message(chat_id, "❌ Error fetching IP information.")
        
        bot.delete_message(chat_id, progress_msg.message_id)
        
        ip_addr = clean(ip_data.get('ip')) or ip
        country = clean(ip_data.get('country')) or 'Unknown'
        country_code = clean(ip_data.get('countryCode')) or 'N/A'
        region = clean(ip_data.get('region')) or 'Unknown'
        city = clean(ip_data.get('city')) or 'Unknown'
        zip_code = clean(ip_data.get('zip')) or 'Unknown'
        lat = clean(ip_data.get('lat')) or 'Unknown'
        lon = clean(ip_data.get('lon')) or 'Unknown'
        timezone = clean(ip_data.get('timezone')) or 'Unknown'
        isp = clean(ip_data.get('isp')) or 'Unknown'
        org = clean(ip_data.get('org')) or 'Unknown'
        as_number = clean(ip_data.get('as')) or 'Unknown'
        
        coordinates = f"{lat}, {lon}" if lat != 'Unknown' and lon != 'Unknown' else 'Unknown'
        
        response = f"""
🌐 <b>IP Address Information</b>
━━━━━━━━━━━━━━━━━━━━━━
🖥️ <b>IP Address:</b> <code>{ip_addr}</code>
🌍 <b>Country:</b> {country} ({country_code})
🏙️ <b>Region:</b> {region}
🏠 <b>City:</b> {city}
📮 <b>ZIP Code:</b> {zip_code}
📍 <b>Coordinates:</b> {coordinates}
🕐 <b>Timezone:</b> {timezone}
📡 <b>ISP:</b> {isp}
🏢 <b>Organization:</b> {org}
🔢 <b>AS Number:</b> {as_number}
━━━━━━━━━━━━━━━━━━━━━━
✅ <i>Information retrieved successfully</i>
"""
        bot.send_message(chat_id, response, parse_mode="HTML")
        add_history(user_id, ip, "IP_INFO")
        
    except Exception as e:
        refund_credit(user_id)
        logger.error(f"Error in handle_ip_info: {e}")
        bot.send_message(chat_id, "❌ An unexpected error occurred. Please try again later.")

# ========== ADMIN PANEL ==========
@bot.message_handler(func=lambda c: c.text == "⚙️ Admin Panel")
@handle_errors
def admin_panel(m):
    if not is_admin(m.from_user.id):
        return
    
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("💳 Add Credits", "💸 Remove Credits")
    kb.row("👥 All Users", "📋 User History")
    kb.row("📢 Broadcast", "🌟 Special Users")
    kb.row("🚫 Block User", "✅ Unblock User", "📋 Blocked Users")
    kb.row("🔙 Back to Main Menu")
    
    bot.send_message(m.chat.id, "⚙️ <b>Admin Panel</b>\n\nChoose an option:", reply_markup=kb, parse_mode="HTML")

@bot.message_handler(func=lambda c: c.text == "💳 Add Credits")
@handle_errors
def add_credits_btn(m):
    if not is_admin(m.from_user.id):
        return
    
    msg = bot.send_message(m.chat.id, "💳 Send user ID and credits to add (format: user_id credits):")
    bot.register_next_step_handler(m, process_add_credits)

@handle_errors
def process_add_credits(m):
    try:
        if not is_admin(m.from_user.id):
            return
        
        parts = m.text.strip().split()
        if len(parts) != 2:
            return bot.send_message(m.chat.id, "❌ Invalid format. Please use: user_id credits")
        
        try:
            uid = int(parts[0])
            credits = int(parts[1])
        except ValueError:
            return bot.send_message(m.chat.id, "❌ Invalid user ID or credits value.")
        
        if credits <= 0:
            return bot.send_message(m.chat.id, "❌ Credits must be a positive number.")
        
        init_user(uid)
        current_credits = get_credits(uid)
        new_credits = change_credits(uid, credits)
        
        bot.send_message(m.chat.id, f"✅ Successfully added {credits} credits to user {uid}.\nPrevious balance: {current_credits}\nNew balance: {new_credits}")
        
        try:
            bot.send_message(uid, f"🎉 {credits} credits have been added to your account!\nYour current balance: {new_credits}")
        except Exception as e:
            logger.error(f"Could not notify user {uid}: {e}")
    except Exception as e:
        logger.error(f"Error in process_add_credits: {e}")
        bot.send_message(m.chat.id, f"⚠️ Error: <code>{str(e)}</code>", parse_mode="HTML")

@bot.message_handler(func=lambda c: c.text == "💸 Remove Credits")
@handle_errors
def remove_credits_btn(m):
    if not is_admin(m.from_user.id):
        return
    
    msg = bot.send_message(m.chat.id, "💸 Send user ID and credits to remove (format: user_id credits):")
    bot.register_next_step_handler(m, process_remove_credits)

@handle_errors
def process_remove_credits(m):
    try:
        if not is_admin(m.from_user.id):
            return
        
        parts = m.text.strip().split()
        if len(parts) != 2:
            return bot.send_message(m.chat.id, "❌ Invalid format. Please use: user_id credits")
        
        try:
            uid = int(parts[0])
            credits = int(parts[1])
        except ValueError:
            return bot.send_message(m.chat.id, "❌ Invalid user ID or credits value.")
        
        if credits <= 0:
            return bot.send_message(m.chat.id, "❌ Credits must be a positive number.")
        
        init_user(uid)
        current_credits = get_credits(uid)
        new_credits = change_credits(uid, -credits)
        
        bot.send_message(m.chat.id, f"✅ Successfully removed {credits} credits from user {uid}.\nPrevious balance: {current_credits}\nNew balance: {new_credits}")
        
        try:
            bot.send_message(uid, f"❌ {credits} credits have been removed from your account.\nYour current balance: {new_credits}")
        except Exception as e:
            logger.error(f"Could not notify user {uid}: {e}")
    except Exception as e:
        logger.error(f"Error in process_remove_credits: {e}")
        bot.send_message(m.chat.id, f"⚠️ Error: <code>{str(e)}</code>", parse_mode="HTML")

@bot.message_handler(func=lambda c: c.text == "👥 All Users")
@handle_errors
def all_users_btn(m):
    if not is_admin(m.from_user.id):
        return
    
    cur = db.get_cursor()
    cur.execute("SELECT user_id FROM users ORDER BY user_id")
    users = [row[0] for row in cur.fetchall()]
    
    if not users:
        return bot.send_message(m.chat.id, "❌ No users found.")
    
    total_users = len(users)
    special_count = len(SPECIAL_USERS)
    normal_count = total_users - special_count
    
    out = f"""
👥 <b>All Users</b>
━━━━━━━━━━━━━━━━━━
📊 <b>Total Users:</b> {total_users}
🌟 <b>Special Users:</b> {special_count}
👤 <b>Normal Users:</b> {normal_count}

📋 <b>User List:</b>
"""
    
    for i, uid in enumerate(users[:50], 1):
        special = " 🌟" if is_special_user(uid) else ""
        credits = get_credits(uid)
        out += f"\n{i}. <code>{uid}</code> - {credits} credits{special}"
    
    if len(users) > 50:
        out += f"\n\n... and {len(users) - 50} more users."
    
    send_long(m.chat.id, out)

@bot.message_handler(func=lambda c: c.text == "📋 User History")
@handle_errors
def user_history_btn(m):
    if not is_admin(m.from_user.id):
        return
    
    msg = bot.send_message(m.chat.id, "📋 Send user ID to view history:")
    bot.register_next_step_handler(m, process_user_history)

@handle_errors
def process_user_history(m):
    try:
        if not is_admin(m.from_user.id):
            return
        
        try:
            uid = int(m.text.strip())
        except ValueError:
            return bot.send_message(m.chat.id, "❌ Invalid user ID.")
        
        cur = db.get_cursor()
        cur.execute("SELECT query, api_type, ts FROM history WHERE user_id=? ORDER BY id DESC LIMIT 50", (uid,))
        rows = cur.fetchall()
        
        if not rows:
            return bot.send_message(m.chat.id, f"❌ No history found for user {uid}.")
        
        out = f"""
📋 <b>User History for {uid}</b>
━━━━━━━━━━━━━━━━━━
"""
        
        for q, t, ts in rows:
            out += f"\n[{ts}] ({t}) {q}"
        
        send_long(m.chat.id, out)
    except Exception as e:
        logger.error(f"Error in process_user_history: {e}")
        bot.send_message(m.chat.id, f"⚠️ Error: <code>{str(e)}</code>", parse_mode="HTML")

@bot.message_handler(func=lambda c: c.text == "📢 Broadcast")
@handle_errors
def broadcast_btn(m):
    if not is_admin(m.from_user.id):
        return
    
    msg = bot.send_message(m.chat.id, "📢 Send the message to broadcast to all users:")
    bot.register_next_step_handler(m, process_broadcast)

@handle_errors
def process_broadcast(m):
    try:
        if not is_admin(m.from_user.id):
            return
        
        broadcast_message = m.text.strip()
        if not broadcast_message:
            return bot.send_message(m.chat.id, "❌ Message cannot be empty.")
        
        cur = db.get_cursor()
        cur.execute("SELECT user_id FROM users")
        users = [row[0] for row in cur.fetchall()]
        
        if not users:
            return bot.send_message(m.chat.id, "❌ No users found.")
        
        success_count = 0
        failed_count = 0
        
        progress_msg = bot.send_message(m.chat.id, f"📢 Broadcasting message to {len(users)} users...")
        
        for uid in users:
            try:
                if is_user_blocked(uid):
                    failed_count += 1
                    continue
                
                bot.send_message(uid, f"📢 <b>Broadcast Message</b>\n\n{broadcast_message}\n\n<i>Contact: @Maarjauky</i>", parse_mode="HTML")
                success_count += 1
                time.sleep(0.1)
            except Exception as e:
                logger.error(f"Failed to send broadcast to {uid}: {e}")
                failed_count += 1
        
        try:
            bot.delete_message(m.chat.id, progress_msg.message_id)
        except:
            pass
        
        result_msg = f"""
✅ <b>Broadcast Completed</b>
━━━━━━━━━━━━━━━━━━
📊 <b>Total Users:</b> {len(users)}
✅ <b>Successful:</b> {success_count}
❌ <b>Failed:</b> {failed_count}
"""
        bot.send_message(m.chat.id, result_msg, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error in process_broadcast: {e}")
        bot.send_message(m.chat.id, f"⚠️ Error: <code>{str(e)}</code>", parse_mode="HTML")

@bot.message_handler(func=lambda c: c.text == "🌟 Special Users")
@handle_errors
def special_users_btn(m):
    if not is_admin(m.from_user.id):
        return
    
    kb = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton("➕ Add Special User", callback_data="add_special")
    btn2 = types.InlineKeyboardButton("➖ Remove Special User", callback_data="remove_special")
    kb.add(btn1, btn2)
    
    out = "🌟 <b>Special Users</b>\n━━━━━━━━━━━━━━━━━━\n"
    for user in SPECIAL_USERS:
        out += f"🆔 <code>{user['id']}</code> - {user['name']}\n"
    
    bot.send_message(m.chat.id, out, reply_markup=kb, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data in ["add_special", "remove_special"])
@handle_errors
def handle_special_user_callback(call):
    if not is_admin(call.from_user.id):
        return
    
    if call.data == "add_special":
        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id, "➕ Send user ID and name to add as special user (format: user_id name):")
        bot.register_next_step_handler(msg, process_add_special_user)
    elif call.data == "remove_special":
        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id, "➖ Send user ID to remove from special users:")
        bot.register_next_step_handler(msg, process_remove_special_user)

@handle_errors
def process_add_special_user(m):
    try:
        if not is_admin(m.from_user.id):
            return
        
        parts = m.text.strip().split(maxsplit=1)
        if len(parts) < 2:
            return bot.send_message(m.chat.id, "❌ Invalid format. Please use: user_id name")
        
        try:
            uid = int(parts[0])
            name = parts[1]
        except ValueError:
            return bot.send_message(m.chat.id, "❌ Invalid user ID.")
        
        if is_special_user(uid):
            return bot.send_message(m.chat.id, "❌ User is already a special user.")
        
        SPECIAL_USERS.append({"id": uid, "name": name})
        init_user(uid)
        set_credits(uid, 999)
        
        bot.send_message(m.chat.id, f"✅ Successfully added {name} (ID: {uid}) as a special user.")
        
        try:
            bot.send_message(uid, f"🌟 You have been added as a special user with unlimited credits!")
        except Exception as e:
            logger.error(f"Could not notify user {uid}: {e}")
    except Exception as e:
        logger.error(f"Error in process_add_special_user: {e}")
        bot.send_message(m.chat.id, f"⚠️ Error: <code>{str(e)}</code>", parse_mode="HTML")

@handle_errors
def process_remove_special_user(m):
    try:
        if not is_admin(m.from_user.id):
            return
        
        try:
            uid = int(m.text.strip())
        except ValueError:
            return bot.send_message(m.chat.id, "❌ Invalid user ID.")
        
        for i, user in enumerate(SPECIAL_USERS):
            if user["id"] == uid:
                SPECIAL_USERS.pop(i)
                init_user(uid)
                set_credits(uid, 5)
                
                bot.send_message(m.chat.id, f"✅ Successfully removed user {uid} from special users.")
                
                try:
                    bot.send_message(uid, "❌ You have been removed from special users. Your credits have been reset to normal.")
                except Exception as e:
                    logger.error(f"Could not notify user {uid}: {e}")
                return
        
        bot.send_message(m.chat.id, "❌ User not found in special users list.")
    except Exception as e:
        logger.error(f"Error in process_remove_special_user: {e}")
        bot.send_message(m.chat.id, f"⚠️ Error: <code>{str(e)}</code>", parse_mode="HTML")

@bot.message_handler(func=lambda c: c.text=="🚫 Block User")
@handle_errors
def block_user_btn(m):
    if not is_admin(m.from_user.id): 
        return
    bot.send_message(m.chat.id,"🚫 Send user ID to block:")
    bot.register_next_step_handler(m,process_block_user)

@handle_errors
def process_block_user(m):
    try:
        uid=int(m.text.strip())
        
        cur = db.get_cursor()
        cur.execute("SELECT user_id FROM users WHERE user_id=?", (uid,))
        if not cur.fetchone():
            return bot.send_message(m.chat.id, "❌ User not found in database.")
        
        if is_user_blocked(uid):
            return bot.send_message(m.chat.id, "❌ User is already blocked.")
        
        msg = bot.send_message(m.chat.id, "🚫 Please provide a reason for blocking (optional):")
        bot.register_next_step_handler(msg, lambda msg: process_block_reason(msg, uid))
    except Exception as e:
        logger.error(f"Error in process_block_user: {e}")
        bot.send_message(m.chat.id, "❌ Invalid user ID.")

@handle_errors
def process_block_reason(m, uid):
   

