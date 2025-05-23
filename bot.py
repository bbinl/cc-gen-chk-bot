import telebot
import asyncio
import aiohttp
import re
import random
import json
import os
from telebot import TeleBot
from flask import Flask
from threading import Thread

# BOT TOKEN
BOT_TOKEN = "8176347490:AAG-F8xFHoo83x4DixxBs282GgbhODTdObY"
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

# Save status cache
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
async def generate_cc_async(bin_number):
    url = f"https://drlabapis.onrender.com/api/ccgenerator?bin={bin_number}&count=10"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as response:
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

    formatted = f"𝗕𝗜𝗡 ⇾ <code>{bin_number[:6]}</code>\n"
    formatted += f"𝗔𝗺𝗼𝘂𝗻𝘁 ⇾ <code>{len(data)}</code>\n\n"
    for card in data:
        formatted += f"<code>{card.upper()}</code>\n"
    formatted += f"\n𝗜𝗻𝗳𝗼: {bin_info.get('card_type', 'NOT FOUND')} - {bin_info.get('network', 'NOT FOUND')} ({bin_info.get('tier', 'NOT FOUND')})\n"
    formatted += f"𝐈𝐬𝐬𝐮𝐞𝐫: {bin_info.get('bank', 'NOT FOUND')}\n"
    formatted += f"𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'NOT FOUND')} {bin_info.get('flag', '🏳️')}"
    return formatted

# Command: /gen or .gen
@bot.message_handler(func=lambda msg: msg.text.startswith(('/gen', '.gen')))
def handle_gen(message):
    parts = message.text.split()
    bin_input = parts[1] if len(parts) > 1 else "515462"
    bin_number = extract_bin(bin_input)
    if not bin_number:
        bot.send_message(message.chat.id, "❌ Invalid BIN format.")
        return

    cc_data = asyncio.run(generate_cc_async(bin_number))
    bin_info = asyncio.run(lookup_bin(bin_number))
    result = format_cc_response(cc_data, bin_number, bin_info)
    bot.send_message(message.chat.id, result)

# Command: /chk or .chk
@bot.message_handler(func=lambda msg: msg.text.startswith(('/chk', '.chk')))
def handle_chk(message):
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "❌ Provide a card to check.")
        return

    card = parts[1].strip()
    status = check_card(card)
    bot.reply_to(message, f"<code>{card}</code>\n{status}")

# Command: /mas.chk
@bot.message_handler(func=lambda msg: msg.text.startswith(('/mas.chk',)) and msg.reply_to_message)
def handle_mass_chk(message):
    lines = message.reply_to_message.text.split('\n')
    cards = [line.strip() for line in lines if '|' in line]
    if not cards:
        bot.reply_to(message, "❌ No cards found in the replied message.")
        return

    reply = ""
    for card in cards:
        status = check_card(card)
        reply += f"{card}\n{status}\n\n"
    bot.reply_to(message, reply.strip())

# all commands show
@bot.message_handler(commands=['reveal'])
def show_help(message):
    help_text = (
        "🛠 Available Commands:\n\n"
        "/arise — Start the bot\n"
        "/gen or .gen — Generate random cards with BIN info\n"
        "/chk or .chk — Check a single card's status\n"
        "/mas.chk — Check all generated cards at once (reply to a list)\n"
        "/reveal — Show all the commands"
    )
    bot.reply_to(message, help_text)

# Start command
@bot.message_handler(commands=['start', 'arise'])
def start_command(message):
    welcome_text = (
        "👋 <b>Welcome!</b>\n\n"
        "Here are the available commands you can use:\n\n"
        "<code>/gen</code> or <code>.gen</code> — Generate random cards with BIN info\n"
        "<code>/chk</code> or <code>.chk</code> — Check a single card’s status\n"
        "<code>/mas.chk</code> — Check all generated cards at once (must reply to the generated list)\n"
        "<code>/reveal</code> — Show all the commands\n\n"
        "📢 Join our Telegram Channel for updates and tools:\n"
        "<a href='https://t.me/bro_bin_lagbe'>https://t.me/bro_bin_lagbe</a>"
    )
    bot.send_message(message.chat.id, welcome_text, parse_mode="HTML")

# Run bot
if __name__ == '__main__':
    print("Bot is running...")
    bot.infinity_polling()
