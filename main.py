import re
import sqlite3
import requests
import telebot
import time
import os
from telebot import types
from flask import Flask
from threading import Thread

# ========== CONFIGURATION ==========
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8133993773:AAHUPt2Irj1LXC7QjV-tl00t-uo0fGbjyoc")
bot = telebot.TeleBot(BOT_TOKEN)

ADMIN_ID = int(os.environ.get("ADMIN_ID", "8472134640"))
DB_FILE = "users.db"

# ========== DATABASE FUNCTIONS ==========
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY, credits INTEGER DEFAULT 5)''')
    c.execute('''CREATE TABLE IF NOT EXISTS history
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  user_id INTEGER, query TEXT, api_type TEXT, 
                  ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
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

def add_history(user_id, query, api_type):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO history (user_id, query, api_type) VALUES (?, ?, ?)",
              (user_id, query, api_type))
    conn.commit()
    conn.close()

# ========== CREDIT SYSTEM ==========
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

# ========== START COMMAND ==========
@bot.message_handler(commands=['start'])
def start_command(m):
    user_id = m.from_user.id
    init_user(user_id)
    
    credits = get_credits(user_id)
    
    # Create keyboard
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    # Row 1
    kb.add("👤 Telegram ID Info", "🇮🇳 India Number Info")
    # Row 2
    kb.add("📱 Pakistan Number Info", "📮 Pincode Info")
    # Row 3
    kb.add("🚘 Vehicle Info", "🆔 Aadhaar Info")
    # Row 4
    kb.add("🧪 ICMR Number Info", "🏦 IFSC Code Info")
    # Row 5
    kb.add("💸 UPI ID Info", "📋 Ration Card Info")
    # Row 6
    kb.add("🌐 IP Info", "🎮 Free Fire Info")
    # Row 7
    kb.add("👀 Free Fire Views", "💳 My Credits")
    # Row 8
    kb.add("💳 Buy Credits", "📞 Contact Admin")
    
    # Admin panel for admin only
    if is_admin(user_id):
        kb.add("⚙️ Admin Panel")
    
    # Welcome message
    welcome_text = f"""
🤖 <b>InfoBot by @Maarjauky</b>
━━━━━━━━━━━━━━━━━━

💳 <b>Your Credits:</b> {credits}
🎁 <b>Daily Credits:</b> Get 10 free credits daily

📞 <b>Contact Admin:</b> @Maarjauky
💳 <b>Buy Credits:</b> DM @Maarjauky

<b>Available Services:</b>
• 👤 Telegram ID Info
• 🇮🇳 India Number Info
• 📱 Pakistan Number Info
• 📮 Pincode Info
• 🚘 Vehicle Info
• 🆔 Aadhaar Info
• 🧪 ICMR Number Info
• 🏦 IFSC Code Info
• 💸 UPI ID Info
• 📋 Ration Card Info
• 🌐 IP Info
• 🎮 Free Fire Info
• 👀 Free Fire Views

━━━━━━━━━━━━━━━━━━
⚠️ Each search costs 1 credit
✅ Choose an option below:
"""
    
    bot.send_message(m.chat.id, welcome_text, reply_markup=kb, parse_mode="HTML")

# ========== BASIC HANDLERS ==========
@bot.message_handler(func=lambda m: m.text == "🆔 My ID")
def my_id_handler(m):
    bot.send_message(m.chat.id, f"🆔 Your Telegram ID: <code>{m.from_user.id}</code>", parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text == "💳 My Credits")
def my_credits_handler(m):
    credits = get_credits(m.from_user.id)
    if is_special_user(m.from_user.id):
        bot.send_message(m.chat.id, f"💳 Your Credits: <b>{credits}</b> (Special User 🌟)", parse_mode="HTML")
    else:
        bot.send_message(m.chat.id, f"💳 Your Credits: <b>{credits}</b>", parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text == "📞 Contact Admin")
def contact_admin_handler(m):
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("📞 Contact @Maarjauky", url="https://t.me/Maarjauky"))
    bot.send_message(m.chat.id, "Click below to contact admin:", reply_markup=kb)

# ========== BUY CREDITS ==========
@bot.message_handler(func=lambda m: m.text == "💳 Buy Credits")
def buy_credits_handler(m):
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("💎 100 Credits - ₹200", callback_data="buy_100"))
    kb.add(types.InboardButton("💎 200 Credits - ₹300", callback_data="buy_200"))
    kb.add(types.InlineKeyboardButton("💎 500 Credits - ₹500", callback_data="buy_500"))
    kb.add(types.InlineKeyboardButton("🔄 Custom Amount", callback_data="buy_custom"))
    
    credits = get_credits(m.from_user.id)
    
    text = f"""
💳 <b>Credit Packages</b>
━━━━━━━━━━━━━━━━━━
💎 <b>100 Credits</b> - ₹200
💎 <b>200 Credits</b> - ₹300  
💎 <b>500 Credits</b> - ₹500
━━━━━━━━━━━━━━━━━━
📥 <b>Payment Method:</b> DM @Maarjauky
💳 <b>Your Current Credits:</b> {credits}

⚠️ Send payment screenshot to @Maarjauky
"""
    
    bot.send_message(m.chat.id, text, reply_markup=kb, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
def buy_callback_handler(call):
    user_id = call.from_user.id
    
    if call.data == "buy_100":
        package = "100 Credits - ₹200"
    elif call.data == "buy_200":
        package = "200 Credits - ₹300"
    elif call.data == "buy_500":
        package = "500 Credits - ₹500"
    elif call.data == "buy_custom":
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "For custom amounts, please DM @Maarjauky directly.")
        return
    
    payment_text = f"""
💳 <b>Payment Instructions</b>
━━━━━━━━━━━━━━━━━━
📦 <b>Package:</b> {package}
👤 <b>Your ID:</b> <code>{user_id}</code>

📥 <b>Steps:</b>
1. Send ₹ payment to @Maarjauky
2. Take screenshot of payment
3. Send screenshot to @Maarjauky with your ID
4. Credits will be added within 24 hours

💬 <b>Contact:</b> @Maarjauky
"""
    
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, payment_text, parse_mode="HTML")

# ========== WORKING APIs ==========
# 1. IP INFO (WORKING)
@bot.message_handler(func=lambda m: m.text == "🌐 IP Info")
def ip_info_handler(m):
    msg = bot.send_message(m.chat.id, "🌐 Send IP address (e.g., 8.8.8.8):")
    bot.register_next_step_handler(msg, process_ip_info)

def process_ip_info(m):
    if not m.text or not re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', m.text):
        bot.send_message(m.chat.id, "❌ Invalid IP address format")
        return
    
    if not ensure_and_charge(m.from_user.id, m.chat.id):
        return
    
    ip_address = m.text.strip()
    
    try:
        # Working IP API
        url = f"http://ip-api.com/json/{ip_address}"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('status') == 'success':
                info_text = f"""
🌐 <b>IP Information</b>
━━━━━━━━━━━━━━━━━━
🖥️ <b>IP:</b> <code>{ip_address}</code>
🌍 <b>Country:</b> {data.get('country', 'N/A')}
🏙️ <b>City:</b> {data.get('city', 'N/A')}
🏛️ <b>Region:</b> {data.get('regionName', 'N/A')}
📮 <b>ZIP:</b> {data.get('zip', 'N/A')}
📍 <b>Coordinates:</b> {data.get('lat', 'N/A')}, {data.get('lon', 'N/A')}
🕐 <b>Timezone:</b> {data.get('timezone', 'N/A')}
📡 <b>ISP:</b> {data.get('isp', 'N/A')}
🏢 <b>Organization:</b> {data.get('org', 'N/A')}
"""
                bot.send_message(m.chat.id, info_text, parse_mode="HTML")
                add_history(m.from_user.id, ip_address, "IP_INFO")
            else:
                bot.send_message(m.chat.id, "❌ Unable to fetch IP information")
        else:
            bot.send_message(m.chat.id, "❌ API Error")
    except Exception as e:
        bot.send_message(m.chat.id, "❌ Error fetching data")

# 2. IFSC CODE INFO (WORKING)
@bot.message_handler(func=lambda m: m.text == "🏦 IFSC Code Info")
def ifsc_handler(m):
    msg = bot.send_message(m.chat.id, "🏦 Send IFSC Code (e.g., SBIN0005943):")
    bot.register_next_step_handler(msg, process_ifsc)

def process_ifsc(m):
    ifsc = m.text.strip().upper()
    
    if not re.match(r'^[A-Z]{4}0[A-Z0-9]{6}$', ifsc):
        bot.send_message(m.chat.id, "❌ Invalid IFSC format")
        return
    
    if not ensure_and_charge(m.from_user.id, m.chat.id):
        return
    
    try:
        # Working IFSC API
        url = f"https://ifsc.razorpay.com/{ifsc}"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            info_text = f"""
🏦 <b>Bank Information</b>
━━━━━━━━━━━━━━━━━━
🏛️ <b>Bank:</b> {data.get('BANK', 'N/A')}
🔢 <b>IFSC:</b> {data.get('IFSC', 'N/A')}
🏢 <b>Branch:</b> {data.get('BRANCH', 'N/A')}
📍 <b>Address:</b> {data.get('ADDRESS', 'N/A')}
🏙️ <b>City:</b> {data.get('CITY', 'N/A')}
🏛️ <b>State:</b> {data.get('STATE', 'N/A')}
📞 <b>Contact:</b> {data.get('CONTACT', 'N/A')}
"""
            bot.send_message(m.chat.id, info_text, parse_mode="HTML")
            add_history(m.from_user.id, ifsc, "IFSC_INFO")
        else:
            bot.send_message(m.chat.id, "❌ IFSC not found")
    except:
        bot.send_message(m.chat.id, "❌ Error fetching data")

# 3. PINCODE INFO (WORKING)
@bot.message_handler(func=lambda m: m.text == "📮 Pincode Info")
def pincode_handler(m):
    msg = bot.send_message(m.chat.id, "📮 Send 6-digit Pincode:")
    bot.register_next_step_handler(msg, process_pincode)

def process_pincode(m):
    pincode = m.text.strip()
    
    if not re.match(r'^\d{6}$', pincode):
        bot.send_message(m.chat.id, "❌ Invalid pincode")
        return
    
    if not ensure_and_charge(m.from_user.id, m.chat.id):
        return
    
    try:
        # Working Pincode API
        url = f"https://api.postalpincode.in/pincode/{pincode}"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            if data[0]['Status'] == 'Success':
                post_offices = data[0]['PostOffice']
                
                info_text = f"""
📮 <b>Pincode Information</b>
━━━━━━━━━━━━━━━━━━
🔢 <b>Pincode:</b> {pincode}
🏛️ <b>District:</b> {post_offices[0]['District']}
🏛️ <b>State:</b> {post_offices[0]['State']}
🏢 <b>Post Offices:</b> {len(post_offices)}

<b>First 3 Post Offices:</b>
"""
                for i, office in enumerate(post_offices[:3], 1):
                    info_text += f"\n{i}. {office['Name']} ({office['BranchType']})"
                
                bot.send_message(m.chat.id, info_text, parse_mode="HTML")
                add_history(m.from_user.id, pincode, "PINCODE_INFO")
            else:
                bot.send_message(m.chat.id, "❌ Pincode not found")
        else:
            bot.send_message(m.chat.id, "❌ API Error")
    except:
        bot.send_message(m.chat.id, "❌ Error fetching data")

# ========== ADMIN PANEL ==========
@bot.message_handler(func=lambda m: m.text == "⚙️ Admin Panel")
def admin_panel_handler(m):
    if not is_admin(m.from_user.id):
        bot.send_message(m.chat.id, "❌ Access denied")
        return
    
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("💳 Add Credits", "👥 All Users")
    kb.add("📢 Broadcast", "🔙 Main Menu")
    
    bot.send_message(m.chat.id, "⚙️ <b>Admin Panel</b>\nSelect an option:", reply_markup=kb, parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text == "💳 Add Credits")
def admin_add_credits(m):
    if not is_admin(m.from_user.id):
        return
    
    msg = bot.send_message(m.chat.id, "Send: user_id amount")
    bot.register_next_step_handler(msg, process_add_credits)

def process_add_credits(m):
    if not is_admin(m.from_user.id):
        return
    
    try:
        parts = m.text.split()
        if len(parts) != 2:
            bot.send_message(m.chat.id, "❌ Format: user_id amount")
            return
        
        user_id = int(parts[0])
        amount = int(parts[1])
        
        init_user(user_id)
        current = get_credits(user_id)
        set_credits(user_id, current + amount)
        
        bot.send_message(m.chat.id, f"✅ Added {amount} credits to user {user_id}")
        
        # Notify user
        try:
            bot.send_message(user_id, f"🎉 {amount} credits added by admin!")
        except:
            pass
    except:
        bot.send_message(m.chat.id, "❌ Invalid input")

@bot.message_handler(func=lambda m:
