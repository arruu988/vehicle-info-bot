import os
import time
import logging
import requests
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

BOT_TOKEN = os.getenv("8595327549:AAG6164KjUp5Rof0UVuYUj04IQvnetkOFLM")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(name)

def get_vehicle_info(vehicle_no, retries=10):
    url = f"https://vehicleinfotrial.hackathonjce001.workers.dev/?VIN={vehicle_no}"
    headers = {"User-Agent": "Mozilla/5.0"}
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            return response.json()
        except Exception:
            time.sleep(2)
    return None

def format_vehicle_info(data):
    if not data:
        return "❌ Vehicle details nahi mil sake. Number check karke fir try karo."

    text = "🚗 Vehicle Information 🚗\n\n"
    emojis = {
        "owner_name": "👤", "vehicle_type": "🚙", "model": "🏷️", "fuel_type": "⛽",
        "insurance_company": "🛡️", "total_pending_challans": "🚨", "present_address": "🏠"
    }
    for key, value in data.items():
        emoji = emojis.get(key, "•")
        name = key.replace("_", " ").title()
        text += f"{emoji} {name}: {value}\n"

    text += "\n🤖 Powered by @maarjauky"
    return text

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Namaste! Mujhe ek vehicle number do, main details dunga. 🚙")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    vehicle_no = update.message.text.strip()
    if len(vehicle_no) < 3:
        await update.message.reply_text("❌ Valid number daal bhai.")
        return

    await update.message.chat.send_action(ChatAction.TYPING)
    msg = await update.message.reply_text("🔄 Searching...")
    data = get_vehicle_info(vehicle_no)

    if data:
        await update.message.reply_text(format_vehicle_info(data))
    else:
        await update.message.reply_text("😔 Kuch nahi mila, thoda baad me try kar.")

    await msg.delete()

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Error: %s", context.error)

def main():
    if not BOT_TOKEN:
        raise RuntimeError("❌ BOT_TOKEN Render me environment variable me set karna hai.")

    bot = Application.builder().token(BOT_TOKEN).build()
    bot.add_handler(CommandHandler("start", start))
    bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    bot.add_error_handler(error_handler)
    
    print("✅ Bot is running...")
    bot.run_polling()

if name == "main":

    main()
