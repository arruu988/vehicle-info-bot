import requests
import time
import logging
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = "8595327549:AAG6164KjUp5Rof0UVuYUj04IQvnetkOFLM"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_vehicle_info(vehicle_no, retries=3):
    url = f"https://vehicleinfotrial.hackathonjce001.workers.dev/?VIN={vehicle_no}"
    headers = {"User-Agent": "Mozilla/5.0"}
    for attempt in range(1, retries + 1):
        try:
            logger.info(f"Attempt {attempt}/{retries} for VIN: {vehicle_no}")
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data
        except Exception as e:
            logger.warning(f"Attempt {attempt} failed: {e}")
            time.sleep(1)
    return None

def format_vehicle_info(data):
    if not data:
        return "❌ Vehicle details nahi mil sake. Vehicle number check karo."
    text = "🚗 VEHICLE INFORMATION 🚗\n\n"
    field_emojis = {
        'owner_name': '👤','vehicle_type': '🚙','registration_date': '📅','model': '🏷️','fuel_type': '⛽','insurance_company': '🛡️','insurance_valid_upto': '📄','pucc_number': '📋','pucc_valid_upto': '📅','fitness_upto': '💪','blacklist_status': '⚫','rc_status': '📄','present_address': '🏠','permanent_address': '🏠','chassis_number': '🔧','engine_number': '⚙️','mobile_number': '📱','noc_details': '📝','total_pending_challans': '🚨','maker_model': '🚗','manufacturing_year': '📅','vehicle_color': '🎨','registration_year': '📅','vehicle_category': '📋','body_type': '🚙','cylinder_capacity': '⚙️','seating_capacity': '💺','wheelbase': '📏','cubic_capacity': '📦','gross_vehicle_weight': '⚖️','unladen_weight': '⚖️','permit_type': '📄','permit_number': '📋','permit_issue_date': '📅','permit_valid_from': '📅','permit_valid_upto': '📅','national_permit_number': '📋','national_permit_issued_by': '🏛️','national_permit_valid_upto': '📅','non_use_status': '⏸️','non_use_from': '📅','non_use_to': '📅','insurance_policy_number': '📄','address_line': '🏠','city': '🏙️','district': '🗺️','state': '🏛️','pincode': '📮','country': '🌍','rate_limit': '📊','powered_by': '⚡'
    }
    for key, value in data.items():
        if key.lower() == 'powered by' or key.lower() == 'powered_by':
            text += f"⚡ Powered By: @maarjauky\n"
        elif key.lower() == 'rate limit' or key.lower() == 'rate_limit':
            continue
        else:
            emoji = field_emojis.get(key, '•')
            display_name = key.replace('_', ' ').title()
            text += f"{emoji} {display_name}: {value}\n"
    text += "\n🤖 Powered by @maarjauky"
    return text

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    welcome = f"""Namaste {user.first_name}! 👋
🤖 Vehicle Info Bot
Mujhe kisi bhi vehicle ka number/VIN do, main details dunga!
📌 Examples:
• ABC123
• MH12DE1433
• 1HGBH41JXMN109186
Apna vehicle number try karo! 🚙"""
    await update.message.reply_text(welcome)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    vehicle_no = update.message.text.strip()
    if len(vehicle_no) < 3:
        await update.message.reply_text("❌ Please enter valid vehicle number!")
        return
    await update.message.reply_chat_action("typing")
    msg = await update.message.reply_text("🔄 Searching in database...")
    data = get_vehicle_info(vehicle_no)
    if data:
        response_text = format_vehicle_info(data)
        await update.message.reply_text(response_text)
    else:
        await update.message.reply_text("😔 Sorry! Details nahi mil sake.\n\nKoshish karo:\n• Different number try karo\n• Thodi der baad try karo")
    await msg.delete()

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Error: {context.error}")

def main():
    print("🚀 Starting Vehicle Info Bot...")
    print("Free limit: 6 searches/day")
    print("Premium: Unlimited")
    print("Prices: 150/month, 1200/6months, 1350/year")
    print("Admin User IDs: 8472134840, 1199617785")
    print("Bot by amacrjauky")
    try:
        application = Application.builder().token(BOT_TOKEN).build()
        application.add_handler(CommandHandler("start", start))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        application.add_error_handler(error_handler)
        
        print("✅ Bot running! Press Ctrl+C to stop.")
        application.run_polling(drop_pending_updates=True)
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
