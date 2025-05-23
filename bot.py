import os
import re
import asyncio
import aiohttp
import time
import random
import string
import telebot

BOT_TOKEN = "7526852134:AAGx1RKchBl5GAGVWih7a0E7PmXEo2D0HO8"  # 🔐 Replace this with your actual bot token
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# BIN Country flags
COUNTRY_FLAGS = {
    "FRANCE": "🇫🇷", "UNITED STATES": "🇺🇸", "BRAZIL": "🇧🇷", "NAMIBIA": "🇳🇦",
    "INDIA": "🇮🇳", "GERMANY": "🇩🇪", "THAILAND": "🇹🇭", "MEXICO": "🇲🇽", "RUSSIA": "🇷🇺"
}

# Util: BIN Extract
def extract_bin(bin_input):
    match = re.match(r'(\d{6,16})', bin_input)
    return match.group(1).ljust(16, 'x') if match and len(match.group(1)) == 6 else match.group(1) if match else None

# Async: BIN Lookup
async def lookup_bin(bin_number):
    url = f"https://drlabapis.onrender.com/api/bin?bin={bin_number[:6]}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as res:
            if res.status == 200:
                data = await res.json()
                country = data.get("country", "NOT FOUND").upper()
                return {
                    "bank": data.get("issuer", "NOT FOUND").upper(),
                    "card_type": data.get("type", "NOT FOUND").upper(),
                    "network": data.get("scheme", "NOT FOUND").upper(),
                    "tier": data.get("tier", "NOT FOUND").upper(),
                    "country": country,
                    "flag": COUNTRY_FLAGS.get(country, "🏳️")
                }
            return {"error": f"API error: {res.status}"}

# Async: Generate CC
async def generate_cc(bin_number):
    url = f"https://drlabapis.onrender.com/api/ccgenerator?bin={bin_number}&count=10"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as res:
            if res.status == 200:
                return (await res.text()).strip().splitlines()
            return {"error": f"API error: {res.status}"}

# Util: Format
def format_response(cards, bin_number, bin_info):
    if isinstance(cards, dict) and "error" in cards:
        return f"❌ ERROR: {cards['error']}"
    if not cards:
        return "❌ NO CARDS GENERATED."
    text = f"𝗕𝗜𝗡 ⇾ <code>{bin_number[:6]}</code>\n𝗔𝗺𝗼𝘂𝗻𝘁 ⇾ <code>{len(cards)}</code>\n\n"
    text += "\n".join([f"<code>{card}</code>" for card in cards])
    text += f"\n\n𝗜𝗻𝗳𝗼: {bin_info.get('card_type')} - {bin_info.get('network')} ({bin_info.get('tier')})"
    text += f"\n𝐈𝐬𝐬𝐮𝐞𝐫: {bin_info.get('bank')}\n𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country')} {bin_info.get('flag')}"
    return text

# /gen command
@bot.message_handler(func=lambda msg: msg.text.startswith(('/gen', '.gen')))
def handle_gen(message):
    try:
        args = message.text.split()
        bin_input = args[1] if len(args) > 1 else "515462"
        bin_number = extract_bin(bin_input)
        if not bin_number:
            bot.send_message(message.chat.id, "❌ Invalid BIN format.")
            return

        cards = asyncio.run(generate_cc(bin_number))
        info = asyncio.run(lookup_bin(bin_number))
        response = format_response(cards, bin_number, info)
        bot.send_message(message.chat.id, response)
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error: {e}")

# /start command
@bot.message_handler(commands=["start"])
def handle_start(message):
    bot.send_message(message.chat.id, "👋 Welcome! Use <code>/gen [BIN]</code> to generate cards.\nExample: <code>/gen 515462</code>")

# Run bot
if __name__ == "__main__":
    print("✅ Bot is running with polling...")
    bot.delete_webhook()
    bot.infinity_polling(timeout=60, long_polling_timeout=60)
