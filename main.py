import os
import telebot
import time
from flask import Flask
import sys

# ========== CONFIG ==========
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8133993773:AAHUPt2Irj1LXC7QjV-tl00t-uo0fGbjyoc")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "8472134640"))

# Create bot instance
bot = telebot.TeleBot(BOT_TOKEN)

# ========== BOT COMMANDS ==========
@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    
    # Check if admin
    is_admin_user = user_id == ADMIN_ID
    
    # Welcome message
    welcome_text = f"""
🤖 <b>InfoBot by @Maarjauky</b>
━━━━━━━━━━━━━━━━━━

👤 <b>Your ID:</b> <code>{user_id}</code>
{"🌟 <b>Status:</b> Admin" if is_admin_user else "👤 <b>Status:</b> User"}

📞 <b>Contact Admin:</b> @Maarjauky
💳 <b>Buy Credits:</b> DM @Maarjauky

<b>Available Services:</b>
• 🌐 IP Information
• 🏦 IFSC Code Info  
• 📮 Pincode Info
• 📞 Contact Admin
• 💳 Buy Credits

━━━━━━━━━━━━━━━━━━
⚠️ <i>More services coming soon!</i>
"""
    
    # Create reply keyboard
    from telebot import types
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    # Add buttons
    markup.add("🌐 IP Info", "🏦 IFSC Code")
    markup.add("📮 Pincode Info", "📞 Contact Admin")
    markup.add("💳 Buy Credits", "🆔 My ID")
    
    if is_admin_user:
        markup.add("⚙️ Admin Panel")
    
    bot.send_message(message.chat.id, welcome_text, reply_markup=markup, parse_mode="HTML")

@bot.message_handler(func=lambda message: message.text == "🆔 My ID")
def my_id_command(message):
    bot.send_message(message.chat.id, f"🆔 <b>Your Telegram ID:</b> <code>{message.from_user.id}</code>", parse_mode="HTML")

@bot.message_handler(func=lambda message: message.text == "📞 Contact Admin")
def contact_admin_command(message):
    from telebot import types
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📞 Contact @Maarjauky", url="https://t.me/Maarjauky"))
    bot.send_message(message.chat.id, "Click below to contact admin:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "💳 Buy Credits")
def buy_credits_command(message):
    from telebot import types
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("💎 100 Credits - ₹200", callback_data="buy_100"))
    markup.add(types.InlineKeyboardButton("💎 200 Credits - ₹300", callback_data="buy_200"))
    markup.add(types.InlineKeyboardButton("💎 500 Credits - ₹500", callback_data="buy_500"))
    markup.add(types.InlineKeyboardButton("🔄 Custom Amount", callback_data="buy_custom"))
    
    text = """💳 <b>Credit Packages</b>
━━━━━━━━━━━━━━━━━━
💎 <b>100 Credits</b> - ₹200
💎 <b>200 Credits</b> - ₹300  
💎 <b>500 Credits</b> - ₹500
━━━━━━━━━━━━━━━━━━
📥 <b>Payment:</b> DM @Maarjauky
📸 Send payment screenshot"""
    
    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
def buy_callback(call):
    user_id = call.from_user.id
    
    if call.data == "buy_100":
        package = "100 Credits - ₹200"
    elif call.data == "buy_200":
        package = "200 Credits - ₹300"
    elif call.data == "buy_500":
        package = "500 Credits - ₹500"
    else:
        package = "Custom Amount"
    
    text = f"""💳 <b>Payment Instructions</b>
━━━━━━━━━━━━━━━━━━
📦 <b>Package:</b> {package}
👤 <b>Your ID:</b> <code>{user_id}</code>

📥 <b>Steps:</b>
1. Send payment to @Maarjauky
2. Take screenshot
3. Send to @Maarjauky
4. Credits added within 24h

💬 <b>Contact:</b> @Maarjauky"""
    
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, text, parse_mode="HTML")

# ========== WORKING APIs ==========
import requests

@bot.message_handler(func=lambda message: message.text == "🌐 IP Info")
def ip_info_command(message):
    msg = bot.send_message(message.chat.id, "🌐 Send IP address (e.g., 8.8.8.8):")
    bot.register_next_step_handler(msg, process_ip_info)

def process_ip_info(message):
    import re
    
    ip = message.text.strip()
    if not re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', ip):
        bot.send_message(message.chat.id, "❌ Invalid IP format")
        return
    
    try:
        response = requests.get(f"http://ip-api.com/json/{ip}", timeout=10)
        if response.status_code == 200:
            data = response.json()
            
            if data.get('status') == 'success':
                info = f"""🌐 <b>IP Information</b>
━━━━━━━━━━━━━━━━━━
🖥️ <b>IP:</b> <code>{ip}</code>
🌍 <b>Country:</b> {data.get('country', 'N/A')}
🏙️ <b>City:</b> {data.get('city', 'N/A')}
🏛️ <b>Region:</b> {data.get('regionName', 'N/A')}
📡 <b>ISP:</b> {data.get('isp', 'N/A')}
📍 <b>Location:</b> {data.get('lat', 'N/A')}, {data.get('lon', 'N/A')}"""
                
                bot.send_message(message.chat.id, info, parse_mode="HTML")
            else:
                bot.send_message(message.chat.id, "❌ IP not found")
        else:
            bot.send_message(message.chat.id, "❌ API Error")
    except:
        bot.send_message(message.chat.id, "❌ Error fetching data")

@bot.message_handler(func=lambda message: message.text == "🏦 IFSC Code")
def ifsc_command(message):
    msg = bot.send_message(message.chat.id, "🏦 Send IFSC Code (e.g., SBIN0005943):")
    bot.register_next_step_handler(msg, process_ifsc)

def process_ifsc(message):
    ifsc = message.text.strip().upper()
    
    try:
        response = requests.get(f"https://ifsc.razorpay.com/{ifsc}", timeout=10)
        if response.status_code == 200:
            data = response.json()
            
            info = f"""🏦 <b>Bank Information</b>
━━━━━━━━━━━━━━━━━━
🏛️ <b>Bank:</b> {data.get('BANK', 'N/A')}
🔢 <b>IFSC:</b> {data.get('IFSC', 'N/A')}
🏢 <b>Branch:</b> {data.get('BRANCH', 'N/A')}
📍 <b>Address:</b> {data.get('ADDRESS', 'N/A')}
🏙️ <b>City:</b> {data.get('CITY', 'N/A')}"""
            
            bot.send_message(message.chat.id, info, parse_mode="HTML")
        else:
            bot.send_message(message.chat.id, "❌ IFSC not found")
    except:
        bot.send_message(message.chat.id, "❌ Error fetching data")

@bot.message_handler(func=lambda message: message.text == "📮 Pincode Info")
def pincode_command(message):
    msg = bot.send_message(message.chat.id, "📮 Send 6-digit Pincode:")
    bot.register_next_step_handler(msg, process_pincode)

def process_pincode(message):
    pincode = message.text.strip()
    
    try:
        response = requests.get(f"https://api.postalpincode.in/pincode/{pincode}", timeout=10)
        if response.status_code == 200:
            data = response.json()
            
            if data[0]['Status'] == 'Success':
                post_office = data[0]['PostOffice'][0] if data[0]['PostOffice'] else {}
                
                info = f"""📮 <b>Pincode Information</b>
━━━━━━━━━━━━━━━━━━
🔢 <b>Pincode:</b> {pincode}
🏛️ <b>District:</b> {post_office.get('District', 'N/A')}
🏛️ <b>State:</b> {post_office.get('State', 'N/A')}
🏢 <b>Post Office:</b> {post_office.get('Name', 'N/A')}"""
                
                bot.send_message(message.chat.id, info, parse_mode="HTML")
            else:
                bot.send_message(message.chat.id, "❌ Pincode not found")
        else:
            bot.send_message(message.chat.id, "❌ API Error")
    except:
        bot.send_message(message.chat.id, "❌ Error fetching data")

# ========== ADMIN PANEL ==========
@bot.message_handler(func=lambda message: message.text == "⚙️ Admin Panel")
def admin_panel_command(message):
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ Access Denied")
        return
    
    from telebot import types
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("📊 Bot Stats", "👥 Users List")
    markup.add("📢 Broadcast", "🔙 Main Menu")
    
    bot.send_message(message.chat.id, "⚙️ <b>Admin Panel</b>\nSelect option:", reply_markup=markup, parse_mode="HTML")

@bot.message_handler(func=lambda message: message.text == "🔙 Main Menu")
def main_menu_command(message):
    start_command(message)

@bot.message_handler(func=lambda message: message.text == "📊 Bot Stats")
def bot_stats_command(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    stats = f"""📊 <b>Bot Statistics</b>
━━━━━━━━━━━━━━━━━━
🤖 <b>Bot:</b> InfoBot
👤 <b>Admin:</b> @Maarjauky
🆔 <b>Admin ID:</b> {ADMIN_ID}
🔗 <b>Contact:</b> @Maarjauky"""
    
    bot.send_message(message.chat.id, stats, parse_mode="HTML")

@bot.message_handler(func=lambda message: message.text == "👥 Users List")
def users_list_command(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    # Simple users list (in production use database)
    bot.send_message(message.chat.id, "👥 Users list feature coming soon!")

@bot.message_handler(func=lambda message: message.text == "📢 Broadcast")
def broadcast_command(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    msg = bot.send_message(message.chat.id, "📢 Send broadcast message:")
    bot.register_next_step_handler(msg, process_broadcast)

def process_broadcast(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    # Simple broadcast (in production send to all users)
    bot.send_message(message.chat.id, f"✅ Broadcast sent!\nMessage: {message.text}")

# ========== FALLBACK ==========
@bot.message_handler(func=lambda message: True)
def fallback_command(message):
    bot.send_message(message.chat.id, "❌ Unknown command. Use /start to see menu")

# ========== FLASK WEB SERVER ==========
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Telegram Bot is running - @Maarjauky"

@app.route('/health')
def health():
    return "OK", 200

@app.route('/ping')
def ping():
    return "pong", 200

def run_web_server():
    port = int(os.environ.get('PORT', 8080))
    # Use different port to avoid conflict
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# ========== BOT RUNNER ==========
def run_bot_single_instance():
    print("🤖 Starting Telegram Bot...")
    print(f"👤 Admin: {ADMIN_ID}")
    print(f"🔗 Contact: @Maarjauky")
    print("⏳ Bot is running...")
    
    try:
        # Remove any existing webhook
        bot.remove_webhook()
        time.sleep(1)
        
        # Start polling with single instance
        bot.polling(
            none_stop=True,
            interval=3,
            timeout=30,
            allowed_updates=None,
            skip_pending=False
        )
    except Exception as e:
        print(f"❌ Bot error: {e}")
        time.sleep(5)
        # Restart bot
        run_bot_single_instance()

# ========== MAIN ==========
if __name__ == "__main__":
    # IMPORTANT: Run only ONE instance
    import threading
    
    # Start Flask web server in background thread
    web_thread = threading.Thread(target=run_web_server, daemon=True)
    web_thread.start()
    
    # Start bot (main thread)
    run_bot_single_instance()


