import telebot
import asyncio
import aiohttp
import re
import random
import json
import os
from flask import Flask
from threading import Thread

# BOT TOKEN
BOT_TOKEN = "8176347490:AAFKOhXce4bjeJj_la5ueKrDdW9EOqZ0xik"
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# === FLASK SERVER FOR RENDER ===
app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# === START FLASK FIRST ===
keep_alive()

# Store card status persistently
CACHE_FILE = "card_status_cache.json"
if os.path.exists(CACHE_FILE):
    with open(CACHE_FILE, 'r') as f:
        card_status_cache = json.load(f)
else:
    card_status_cache = {}

def save_cache():
    with open(CACHE_FILE, 'w') as f:
        json.dump(card_status_cache, f)

# Country flags
COUNTRY_FLAGS = {
    "FRANCE": "🇫🇷", "UNITED STATES": "🇺🇸", "BRAZIL": "🇧🇷", "NAMIBIA": "🇳🇦",
    "INDIA": "🇮🇳", "GERMANY": "🇩🇪", "THAILAND": "🇹🇭", "MEXICO": "🇲🇽", "RUSSIA": "🇷🇺",
}

# BIN extractor
def extract_bin(bin_input):
    match = re.match(r'(\d{6,16})', bin_input)
    return match.group(1).ljust(16, 'x') if match and len(match.group(1)) == 6 else match.group(1) if match else None

# Async fetch BIN info
async def lookup_bin(bin_number):
    url = f"https://drlabapis.onrender.com/api/bin?bin={bin_number[:6]}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    bin_data = await response.json()
                    country_name = bin_data.get('country', 'NOT FOUND').upper()
                    return {
                        "bank": bin_data.get('issuer', 'NOT FOUND').upper(),
                        "card_type": bin_data.get('type', 'NOT FOUND').upper(),
                        "network": bin_data.get('scheme', 'NOT FOUND').upper(),
                        "tier": bin_data.get('tier', 'NOT FOUND').upper(),
                        "country": country_name,
                        "flag": COUNTRY_FLAGS.get(country_name, "🏳️")
                    }
                else:
                    return {"error": f"API error: {response.status}"}
    except Exception as e:
        return {"error": str(e)}

# Async generate cards
async def generate_cc_async(bin_number, month=None, year=None, cvv=None, count=10):
    full_bin = bin_number
    if month and year and cvv:
        full_bin += f"|{month}|{year}|{cvv}"

    base_url = f"https://drlabapis.onrender.com/api/ccgenerator?bin={full_bin}&count={count}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(base_url, timeout=10) as response:
                if response.status == 200:
                    raw_text = await response.text()
                    return raw_text.strip().split("\n")
                else:
                    return {"error": f"API error: {response.status}"}
    except Exception as e:
        return {"error": str(e)}

# Card checker simulator
def check_card(card):
    if card in card_status_cache:
        return card_status_cache[card]

    roll = random.random()
    if roll < 0.5:
        status = "✅ Live"
    elif roll < 0.75:
        status = "❓ Unknown"
    else:
        status = "❌ Dead"

    card_status_cache[card] = status
    save_cache()
    return status

# Format generated output
def format_cc_response(data, bin_number, bin_info):
    if isinstance(data, dict) and "error" in data:
        return f"❌ ERROR: {data['error']}"
    if not data:
        return "❌ NO CARDS GENERATED."

    formatted = f"𝐵𝐬𝐯 ⇒ <code>{bin_number[:6]}</code>\n"
    formatted += f"𝐦𝑎𝑌𝑒𝑟 ⇒ <code>{len(data)}</code>\n\n"
    for card in data:
        formatted += f"<code>{card.upper()}</code>\n"
    formatted += f"\nℷℳ𝑎: {bin_info.get('card_type', 'NOT FOUND')} - {bin_info.get('network', 'NOT FOUND')} ({bin_info.get('tier', 'NOT FOUND')})\n"
    formatted += f"𝐍𝑒𝑚𝑒𝑡: {bin_info.get('bank', 'NOT FOUND')}\n"
    formatted += f"𝐵𝐮𝑖𝑡𝑒: {bin_info.get('country', 'NOT FOUND')} {bin_info.get('flag', '🏳️')}"
    return formatted

# /gen or .gen command
@bot.message_handler(func=lambda msg: msg.text.startswith(('/gen', '.gen')))
def handle_gen(message):
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "❌ BIN input is required.")
        return

    bin_parts = parts[1].split('|')
    bin_input = bin_parts[0]
    month = bin_parts[1] if len(bin_parts) > 1 else None
    year = bin_parts[2] if len(bin_parts) > 2 else None
    cvv = bin_parts[3] if len(bin_parts) > 3 else None

    count = 10  # default
    for i in range(2, len(parts)):
        if parts[i].lower() in [".cnt", "/cnt"] and i + 1 < len(parts):
            if parts[i+1].isdigit():
                count = int(parts[i+1])
            break

    bin_number = extract_bin(bin_input)
    if not bin_number:
        bot.send_message(message.chat.id, "❌ Invalid BIN format.")
        return

    cc_data = asyncio.run(generate_cc_async(bin_input, month, year, cvv, count))
    bin_info = asyncio.run(lookup_bin(bin_number))
    result = format_cc_response(cc_data, bin_input, bin_info)
    bot.send_message(message.chat.id, result)

# Other commands stay the same...
# (Include /chk, /mas.chk, /reveal, /start)

# Run the bot
if __name__ == '__main__':
    print("Bot is running...")
    bot.infinity_polling()
