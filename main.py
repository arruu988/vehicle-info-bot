import requests
import time
import logging
import json
import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Bot Token
BOT_TOKEN = "8595327549:AAG6164KjUp5Rof0UVuYUj04IQvnetkOFLM"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# User database (in production use real database)
users_db = {
    # Admin (YOU) - unlimited access - DONO IDs DALDI
    8472134640: {"searches_today": 0, "total_searches": 0, "premium": True, "limit": 9999, "last_reset": datetime.date.today().isoformat()},
    1189817785: {"searches_today": 0, "total_searches": 0, "premium": True, "limit": 9999, "last_reset": datetime.date.today().isoformat()}
}

# Free user limits - UPDATED
FREE_DAILY_LIMIT = 6  # 3 se 6 kar diya
PREMIUM_DAILY_LIMIT = 9999

# New Prices - UPDATED
PRICE_1_MONTH = "₹50"
PRICE_6_MONTHS = "₹200" 
PRICE_1_YEAR = "₹350"

def save_user_data():
    # Yahan real database use karo
    pass

def get_user(user_id):
    today = datetime.date.today().isoformat()
    
    if user_id not in users_db:
        users_db[user_id] = {
            "searches_today": 0, 
            "total_searches": 0, 
            "premium": False, 
            "limit": FREE_DAILY_LIMIT,
            "last_reset": today
        }
    
    # Daily reset check
    if users_db[user_id]["last_reset"] != today:
        users_db[user_id]["searches_today"] = 0
        users_db[user_id]["last_reset"] = today
    
    return users_db[user_id]

def can_user_search(user_id):
    user = get_user(user_id)
    return user["searches_today"] < user["limit"]

def increment_search_count(user_id):
    user = get_user(user_id)
    user["searches_today"] += 1
    user["total_searches"] += 1
    return user["searches_today"]

def get_remaining_searches(user_id):
    user = get_user(user_id)
    return user["limit"] - user["searches_today"]

def make_user_premium(user_id):
    user = get_user(user_id)
    user["premium"] = True
    user["limit"] = PREMIUM_DAILY_LIMIT
    return True

def get_mobile_info(mobile_no, retries=5):
    url = f"https://bjkkhfd.jhgfffff/?number={mobile_no}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    for attempt in range(1, retries + 1):
        try:
            print(f"Trying... Attempt {attempt}/{retries}")
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data
        except Exception as e:
            print(f"Attempt {attempt} failed: {e}")
            time.sleep(2)
    
    return None

def format_mobile_info(data):
    if not data:
        return "❌ Koi details nahi mili. Mobile number check karo."
    
    text = "📱 **MOBILE NUMBER DETAILS** 📱\n\n"
    
    if data.get('status') == 'success':
        data1 = data.get('data1', {})
        
        text += "👤 **PERSONAL INFORMATION** 👤\n"
        text += f"• 📞 **Mobile Number**: {data1.get('mobile', 'N/A')}\n"
        text += f"• 🏷️ **Name**: {data1.get('name', 'N/A')}\n"
        text += f"• 👨‍👦 **Father's Name**: {data1.get('fname', 'N/A')}\n"
        text += f"• 📱 **Alternate Number**: {data1.get('alt', 'N/A')}\n"
        text += f"• 🆔 **ID**: {data1.get('id', 'N/A')}\n\n"
        
        text += "📍 **ADDRESS INFORMATION** 📍\n"
        address = data1.get('address', 'N/A')
        formatted_address = address.replace('!', '\n') if address else 'N/A'
        text += f"• 🏠 **Address**:\n{formatted_address}\n\n"
        
        text += "📡 **NETWORK INFORMATION** 📡\n"
        text += f"• 🌐 **Circle**: {data1.get('circle', 'N/A')}\n"
        text += f"• 📶 **Operator**: JIO\n"
        
        # SIRF TUMHARA USERNAME
        text += f"\n🤖 **Bot by @maarjauky**"
        
    else:
        text = "❌ Mobile number details nahi mil sake."
    
    return text

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = get_user(user.id)
    
    if user_data["premium"]:
        user_type = "🌟 **PREMIUM USER**"
        limit_info = f"Daily searches: {user_data['searches_today']}/UNLIMITED 🚀"
    else:
        user_type = "🔹 **FREE USER**"
        limit_info = f"Daily searches: {user_data['searches_today']}/{FREE_DAILY_LIMIT}"
    
    welcome = f"""
Namaste {user.first_name}! 👋

📱 **Mobile Info Bot**

{user_type}
{limit_info}

✨ **Features:**
• Mobile number tracking
• Real-time information
• Accurate results

💎 **Upgrade to Premium:**
• Unlimited searches 🚀
• Priority support
• Only {PRICE_1_MONTH}/month

Send any 10-digit number to start!

🤖 **Bot by @maarjauky**
    """
    await update.message.reply_text(welcome, parse_mode='Markdown')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    mobile_no = update.message.text.strip()
    
    # Check if user can search
    if not can_user_search(user.id):
        await update.message.reply_text(
            f"❌ **Daily Limit Reached!**\n\n"
            f"You've used all your {FREE_DAILY_LIMIT} free searches for today.\n"
            f"🔓 **Upgrade to Premium** for unlimited searches!\n\n"
            f"💎 **Premium Benefits:**\n"
            f"• Unlimited daily searches 🚀\n"
            f"• Priority support\n"
            f"• Only {PRICE_1_MONTH}/month\n\n"
            f"Use /premium command to upgrade!\n\n"
            f"🤖 **Bot by @maarjauky**"
        )
        return
    
    # Mobile number validation
    if len(mobile_no) < 10:
        await update.message.reply_text("❌ Please enter valid 10-digit mobile number!")
        return
    
    mobile_no = ''.join(filter(str.isdigit, mobile_no))
    if len(mobile_no) != 10:
        await update.message.reply_text("❌ Please enter exactly 10-digit mobile number!")
        return
    
    await update.message.reply_chat_action("typing")
    
    # Show search count
    searches_done = increment_search_count(user.id)
    remaining = get_remaining_searches(user.id)
    
    processing_msg = await update.message.reply_text(
        f"🔍 Searching... ({searches_done}/{get_user(user.id)['limit']} today)"
    )
    
    # Get mobile info
    data = get_mobile_info(mobile_no)
    
    if data and data.get('status') == 'success':
        formatted_info = format_mobile_info(data)
        # Add remaining searches info
        if not get_user(user.id)["premium"]:
            formatted_info += f"\n\n🔍 **Remaining searches today**: {remaining}"
        await update.message.reply_text(formatted_info, parse_mode='Markdown')
    else:
        error_msg = f"❌ Sorry! Details nahi mil sake."
        if not get_user(user.id)["premium"]:
            error_msg += f"\n\n🔍 **Remaining searches today**: {remaining}"
        error_msg += f"\n\n🤖 **Bot by @maarjauky**"
        await update.message.reply_text(error_msg)
    
    await processing_msg.delete()

async def premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    premium_text = f"""
💎 **PREMIUM UPGRADE** 💎

Hey {user.first_name}! 

🚀 **Get UNLIMITED Access:**
• Unlimited daily searches 🚀
• No restrictions  
• Priority support
• Faster results

💰 **Affordable Pricing:**
• {PRICE_1_MONTH} - 1 Month
• {PRICE_6_MONTHS} - 6 Months (BEST VALUE 💫)  
• {PRICE_1_YEAR} - 1 Year

📞 **Contact @maarjauky to upgrade!**

Send your:
• Name
• Telegram username  
• Preferred plan

We'll activate premium within minutes! ⚡

🎁 **Free users get {FREE_DAILY_LIMIT} searches/day**

🤖 **Bot by @maarjauky**
    """
    await update.message.reply_text(premium_text, parse_mode='Markdown')

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = get_user(user.id)
    
    if user_data["premium"]:
        limit_info = "UNLIMITED 🚀"
    else:
        limit_info = f"{user_data['searches_today']}/{FREE_DAILY_LIMIT}"
    
    stats_text = f"""
📊 **YOUR STATS** 📊

👤 User: {user.first_name}
🎯 Status: {'🌟 PREMIUM' if user_data['premium'] else '🔹 FREE'}
🔍 Searches Today: {limit_info}
📈 Total Searches: {user_data['total_searches']}

💎 **Upgrade for unlimited searches!**
Use /premium to learn more.

🤖 **Bot by @maarjauky**
    """
    await update.message.reply_text(stats_text, parse_mode='Markdown')

# ADMIN COMMANDS
async def admin_add_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # Check if admin (you) - DONO IDs CHECK KARO
    if user.id not in [8472134640, 1189817785]:  # DONO IDs DALDI
        await update.message.reply_text("❌ Admin access required!")
        return
    
    if context.args:
        target_username = context.args[0]
        # Yahan user ko premium banao
        await update.message.reply_text(f"✅ {target_username} ko premium kar diya! 🚀\n\n🤖 Bot by @maarjauky")
    else:
        await update.message.reply_text("Usage: /addpremium username\n\n🤖 Bot by @maarjauky")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Error: {context.error}")

def main():
    print("🤖 Starting Premium Mobile Info Bot...")
    print(f"🔹 Free limit: {FREE_DAILY_LIMIT} searches/day")
    print(f"💎 Premium: Unlimited")
    print(f"💰 Prices: {PRICE_1_MONTH}/month, {PRICE_6_MONTHS}/6months, {PRICE_1_YEAR}/year")
    print(f"👑 Admin User IDs: 8472134640, 1189817785")
    print(f"🤖 Bot by @maarjauky")
    
    try:
        app = Application.builder().token(BOT_TOKEN).build()
        
        # Handlers
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("premium", premium_command))
        app.add_handler(CommandHandler("stats", stats_command))
        app.add_handler(CommandHandler("addpremium", admin_add_premium))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        app.add_error_handler(error_handler)
        
        print("✅ Bot running! Premium system ready!")
        app.run_polling()
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
