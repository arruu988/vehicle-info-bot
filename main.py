import re
import sqlite3
import requests
import telebot
import time
import os
from telebot import types
from flask import Flask
from threading import Thread

# Bot Token - Render के environment variable से लें
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8133993773:AAHUPt2Irj1LXC7QjV-tl00t-uo0fGbjyoc")
bot = telebot.TeleBot(BOT_TOKEN)

# Admin ID
ADMIN_ID = int(os.environ.get("ADMIN_ID", "8472134640"))
DB_FILE = "users.db"

# Database setup
def init_db():
    conn = sqlite3.connect(DB_FILE)
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
    conn.commit()
    conn.close()

init_db()

SPECIAL_USERS = [{"id": ADMIN_ID, "name": "Admin"}]

def is_admin(user_id):
    return user_id == ADMIN_ID

def is_special_user(user_id):
    return any(user["id"] == user_id for user in SPECIAL_USERS)

def get_connection():
    return sqlite3.connect(DB_FILE)

def init_user(user_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, credits) VALUES (?, 5)", (user_id,))
    conn.commit()
    conn.close()

def get_credits(user_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT credits FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def set_credits(user_id, credits):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE users SET credits=? WHERE user_id=?", (credits, user_id))
    conn.commit()
    conn.close()

def ensure_and_charge(user_id, chat_id):
    if is_special_user(user_id):
        init_user(user_id)
        set_credits(user_id, 999)
        return True
    
    init_user(user_id)
    credits = get_credits(user_id)
    
    if credits <= 0:
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("💳 Buy Credits", callback_data="buy_credits"))
        bot.send_message(chat_id, "❌ No credits left. DM @Maarjauky to buy", reply_markup=kb)
        return False
    
    set_credits(user_id, credits - 1)
    return True

# Start Command
@bot.message_handler(commands=['start'])
def start(m):
    user_id = m.from_user.id
    init_user(user_id)
    
    credits = get_credits(user_id)
    
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add("👤 Telegram ID Info", "🇮🇳 India Number Info")
    kb.add("📱 Pakistan Number Info", "📮 Pincode Info")
    kb.add("🚘 Vehicle Info", "🆔 Aadhaar Info")
    kb.add("🧪 ICMR Number Info", "🏦 IFSC Code Info")
    kb.add("💸 UPI ID Info", "📋 Ration Card Info")
    kb.add("🌐 IP Info", "🎮 Free Fire Info")
    kb.add("👀 Free Fire Views", "💳 My Credits")
    kb.add("💳 Buy Credits", "📞 Contact Admin")
    
    if is_admin(user_id):
        kb.add("⚙️ Admin Panel")
    
    text = f"""🤖 <b>InfoBot by @Maarjauky</b>

💳 Credits: {credits}
🎁 Daily 10 free credits

📞 Contact: @Maarjauky
💳 Buy Credits: DM @Maarjauky

Choose an option:"""
    
    bot.send_message(m.chat.id, text, reply_markup=kb, parse_mode="HTML")

# Basic handlers
@bot.message_handler(func=lambda m: m.text == "🆔 My ID")
def my_id(m):
    bot.send_message(m.chat.id, f"🆔 Your ID: <code>{m.from_user.id}</code>", parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text == "💳 My Credits")
def my_credits(m):
    credits = get_credits(m.from_user.id)
    bot.send_message(m.chat.id, f"💳 Credits: {credits}")

@bot.message_handler(func=lambda m: m.text == "📞 Contact Admin")
def contact_admin(m):
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("📞 Contact @Maarjauky", url="https://t.me/Maarjauky"))
    bot.send_message(m.chat.id, "Click to contact:", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "💳 Buy Credits")
def buy_credits_menu(m):
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("💎 100 Credits - ₹200", callback_data="buy_100"))
    kb.add(types.InlineKeyboardButton("💎 200 Credits - ₹300", callback_data="buy_200"))
    kb.add(types.InlineKeyboardButton("💎 500 Credits - ₹500", callback_data="buy_500"))
    kb.add(types.InlineKeyboardButton("🔄 Custom Amount", callback_data="buy_custom"))
    
    text = """💳 <b>Credit Packs</b>
━━━━━━━━━━━━━━
💎 100 Credits - ₹200
💎 200 Credits - ₹300
💎 500 Credits - ₹500
━━━━━━━━━━━━━━
📥 DM @Maarjauky to buy"""
    
    bot.send_message(m.chat.id, text, reply_markup=kb, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
def buy_callback(call):
    if call.data == "buy_100":
        amount = "100 Credits - ₹200"
    elif call.data == "buy_200":
        amount = "200 Credits - ₹300"
    elif call.data == "buy_500":
        amount = "500 Credits - ₹500"
    else:
        amount = "Custom Amount"
    
    text = f"""💳 <b>Payment Instructions</b>
━━━━━━━━━━━━━━
Package: {amount}
📥 Send payment to: @Maarjauky
📸 Send screenshot with your ID: {call.from_user.id}
✅ Credits added within 24 hours"""
    
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, text, parse_mode="HTML")

# Telegram ID Info
@bot.message_handler(func=lambda m: m.text == "👤 Telegram ID Info")
def ask_tg_id(m):
    msg = bot.send_message(m.chat.id, "📩 Send Telegram User ID:")
    bot.register_next_step_handler(msg, process_tg_id)

def process_tg_id(m):
    if not m.text or not m.text.isdigit():
        bot.send_message(m.chat.id, "❌ Invalid ID")
        return
    
    if not ensure_and_charge(m.from_user.id, m.chat.id):
        return
    
    user_id = m.text
    try:
        response = requests.get(f"https://tg-info-neon.vercel.app/user-details?user={user_id}", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                user_data = data["data"]
                text = f"""👤 <b>Telegram Info</b>
━━━━━━━━━━━━━━
🆔 ID: <code>{user_data.get('id', 'N/A')}</code>
👤 Name: {user_data.get('first_name', '')} {user_data.get('last_name', '')}
🤖 Bot: {user_data.get('is_bot', False)}
💬 Messages: {user_data.get('total_msg_count', 0)}"""
                bot.send_message(m.chat.id, text, parse_mode="HTML")
            else:
                bot.send_message(m.chat.id, "❌ User not found")
        else:
            bot.send_message(m.chat.id, "❌ API error")
    except:
        bot.send_message(m.chat.id, "❌ Error fetching data")

# India Number Info
@bot.message_handler(func=lambda m: m.text == "🇮🇳 India Number Info")
def ask_india_number(m):
    msg = bot.send_message(m.chat.id, "📱 Send 10-digit Indian number:")
    bot.register_next_step_handler(msg, process_india_number)

def process_india_number(m):
    if not m.text or not re.match(r'^\d{10}$', m.text):
        bot.send_message(m.chat.id, "❌ Invalid number")
        return
    
    if not ensure_and_charge(m.from_user.id, m.chat.id):
        return
    
    number = m.text
    try:
        response = requests.get(f"https://demon.taitanx.workers.dev/?mobile={number}", timeout=30)
        if response.status_code == 200:
            data = response.json()
            records = data.get("data", [])
            if records:
                text = f"""📱 <b>Number Lookup</b>
━━━━━━━━━━━━━━
🔍 Number: {number}
📊 Records: {len(records)}"""
                bot.send_message(m.chat.id, text, parse_mode="HTML")
                
                for i, rec in enumerate(records[:3], 1):
                    info = f"""📋 Record #{i}
👤 Name: {rec.get('name', 'N/A')}
📱 Mobile: {rec.get('mobile', 'N/A')}
📍 Address: {rec.get('address', 'N/A')[:50]}..."""
                    bot.send_message(m.chat.id, info)
            else:
                bot.send_message(m.chat.id, "📭 No records found")
        else:
            bot.send_message(m.chat.id, "❌ API error")
    except:
        bot.send_message(m.chat.id, "❌ Error fetching data")

# Admin Panel
@bot.message_handler(func=lambda m: m.text == "⚙️ Admin Panel")
def admin_panel(m):
    if not is_admin(m.from_user.id):
        return
    
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("💳 Add Credits", "👥 All Users")
    kb.add("📢 Broadcast", "🔙 Back")
    
    bot.send_message(m.chat.id, "⚙️ Admin Panel", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "💳 Add Credits")
def add_credits_start(m):
    if not is_admin(m.from_user.id):
        return
    msg = bot.send_message(m.chat.id, "Send: user_id credits")
    bot.register_next_step_handler(msg, add_credits_process)

def add_credits_process(m):
    if not is_admin(m.from_user.id):
        return
    
    try:
        parts = m.text.split()
        user_id = int(parts[0])
        credits = int(parts[1])
        
        init_user(user_id)
        current = get_credits(user_id)
        set_credits(user_id, current + credits)
        
        bot.send_message(m.chat.id, f"✅ Added {credits} credits to {user_id}")
        
        try:
            bot.send_message(user_id, f"🎉 {credits} credits added by admin!")
        except:
            pass
    except:
        bot.send_message(m.chat.id, "❌ Invalid format")

@bot.message_handler(func=lambda m: m.text == "👥 All Users")
def all_users(m):
    if not is_admin(m.from_user.id):
        return
    
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT user_id, credits FROM users")
    users = c.fetchall()
    conn.close()
    
    text = f"👥 Total Users: {len(users)}\n\n"
    for uid, credits in users[:20]:
        text += f"🆔 {uid}: {credits} credits\n"
    
    bot.send_message(m.chat.id, text)

@bot.message_handler(func=lambda m: m.text == "📢 Broadcast")
def broadcast_start(m):
    if not is_admin(m.from_user.id):
        return
    msg = bot.send_message(m.chat.id, "📢 Send broadcast message:")
    bot.register_next_step_handler(msg, broadcast_send)

def broadcast_send(m):
    if not is_admin(m.from_user.id):
        return
    
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT user_id FROM users")
    users = [row[0] for row in c.fetchall()]
    conn.close()
    
    sent = 0
    for uid in users:
        try:
            bot.send_message(uid, f"📢 <b>Broadcast</b>\n\n{m.text}\n\n<i>- Admin @Maarjauky</i>", parse_mode="HTML")
            sent += 1
            time.sleep(0.1)
        except:
            continue
    
    bot.send_message(m.chat.id, f"✅ Broadcast sent to {sent}/{len(users)} users")

@bot.message_handler(func=lambda m: m.text == "🔙 Back")
def back_to_main(m):
    start(m)

# Flask Web Server (Render के लिए जरूरी)
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Telegram Bot is running! - @Maarjauky"

@app.route('/health')
def health():
    return "OK", 200

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# Bot start function
def run_bot():
    print("🤖 Starting Telegram Bot...")
    while True:
        try:
            bot.polling(none_stop=True, timeout=60)
        except Exception as e:
            print(f"Bot error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    # Start web server in separate thread
    web_thread = Thread(target=run_web, daemon=True)
    web_thread.start()
    
    # Start bot
    run_bot()
