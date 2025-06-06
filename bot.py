import telebot
import asyncio
import aiohttp
import re
import random
import json
import os
import requests
import html
import threading
from telebot import TeleBot
from flask import Flask
from threading import Thread
from flag_data import COUNTRY_FLAGS

# BOT TOKEN
BOT_TOKEN = "8176347490:AAGuw1IelrRZgSjFgoM6pu9pMj22k4ZmIGk"
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

# === Persistent Storage ===
CACHE_FILE = "card_status_cache.json"
CARDS_FILE = "generated_cards.json"

# Safe load for card_status_cache
if os.path.exists(CACHE_FILE):
    try:
        with open(CACHE_FILE, 'r') as f:
            card_status_cache = json.load(f)
    except json.JSONDecodeError:
        card_status_cache = {}
else:
    card_status_cache = {}

# Safe load for generated_cards
if os.path.exists(CARDS_FILE):
    try:
        with open(CARDS_FILE, 'r') as f:
            generated_cards = set(json.load(f))
    except json.JSONDecodeError:
        generated_cards = set()
else:
    generated_cards = set()

if os.path.exists(CARDS_FILE):
    with open(CARDS_FILE, 'r') as f:
        generated_cards = set(json.load(f))
else:
    generated_cards = set()

def save_cache():
    with open(CACHE_FILE, 'w') as f:
        json.dump(card_status_cache, f)

def save_generated_cards():
    with open(CARDS_FILE, 'w') as f:
        json.dump(list(generated_cards), f)

# BIN extractor
def extract_bin(bin_input):
    match = re.match(r'(\d{6,16})', bin_input)
    return match.group(1).ljust(16, 'x') if match and len(match.group(1)) == 6 else match.group(1) if match else None

# Async fetch BIN info
async def lookup_bin(bin_number):
    url_primary = f"https://lookup.binlist.net/{bin_number[:6]}"
    url_fallback = f"https://drlabapis.onrender.com/api/bin?bin={bin_number[:6]}"
    headers = {"Accept-Version": "3"}

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url_primary, headers=headers, timeout=10) as response:
                if response.status == 200:
                    bin_data = await response.json()
                else:
                    raise Exception("Primary API failed")
        except Exception:
            try:
                async with session.get(url_fallback, timeout=10) as fallback_resp:
                    if fallback_resp.status == 200:
                        bin_data = (await fallback_resp.json()).get("data", {})
                    else:
                        return {"error": f"Fallback API error: {fallback_resp.status}"}
            except Exception as e:
                return {"error": str(e)}

    country_info = bin_data.get('country', {})
    bank_info = bin_data.get('bank', {})
    number_info = bin_data.get('number', {})

    return {
        "bank": bank_info.get('name', 'NOT FOUND').upper(),
        "card_type": bin_data.get('type', 'NOT FOUND').upper(),
        "network": bin_data.get('scheme', 'NOT FOUND').upper(),
        "tier": bin_data.get('brand', 'NOT FOUND').upper(),
        "country": country_info.get('name', 'NOT FOUND').upper(),
        "flag": country_info.get('emoji', '🏳️'),
        "currency": country_info.get('currency', 'NOT FOUND'),
        "country_code": country_info.get('alpha2', 'N/A'),
        "prepaid": bin_data.get('prepaid', False),
        "luhn": number_info.get('luhn', False),
        "length": number_info.get('length', 'N/A'),
    }

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


# Function to check a single card via xchecker.cc
def check_card(card):
    try:
        parts = card.strip().split('|')
        if len(parts) != 4:
            return "❌ Invalid card format. Use cc|mm|yy|cvv"

        cc, mm, yy, cvv = parts
        if len(yy) == 4:
            yy = yy[-2:]

        url = f"https://xchecker.cc/api.php?cc={cc}|{mm}|{yy}|{cvv}"
        response = requests.get(url, timeout=10)
        data = response.json()

        if "error" in data:
            return f"❌ {data['error']}"
        else:
            status = data.get("status", "Unknown")
            details = data.get("details", "")

            # ✅ Filter out donation lines
            filtered_lines = []
            for line in details.strip().splitlines():
                if "donation" not in line.lower() and "bc1q" not in line.lower():
                    filtered_lines.append(line)
            cleaned_details = "\n".join(filtered_lines)

            return f"✅ Status: <b>{status}</b>\nℹ️ {html.escape(cleaned_details)}"
    except Exception as e:
        return f"⚠️ Error checking card: {str(e)}"

# Format generated output
def format_cc_response(data, bin_number, bin_info):
    if isinstance(data, dict) and "error" in data:
        return f"❌ ERROR: {data['error']}"
    if not data:
        return "❌ NO CARDS GENERATED."

    formatted = f"𝗕𝗜𝗡 ⇒ <code>{bin_number[:6]}</code>\n"
    formatted += f"𝗔𝗺𝗼𝘂𝗻𝘁 ⇒ <code>{len(data)}</code>\n\n"

    for card in data:
        formatted += f"<code>{card.upper()}</code>\n"

    formatted += "\n"
    formatted += f"𝗧𝘆𝗽𝗲: {bin_info.get('card_type', 'NOT FOUND')} ({bin_info.get('network', 'NOT FOUND')})\n"
    formatted += f"𝗕𝗿𝗮𝗻𝗱: {bin_info.get('tier', 'NOT FOUND')}\n"
    formatted += f"𝐈𝐬𝐬𝐮𝐞𝐫: {bin_info.get('bank', 'NOT FOUND')}\n"
    formatted += f"𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'NOT FOUND')} {bin_info.get('flag', '🏳️')}\n"
    formatted += f"𝗖𝘂𝗿𝗿𝗲𝗻𝗰𝘆: {bin_info.get('currency', 'NOT FOUND')} | 𝗖𝗼𝗱𝗲: {bin_info.get('country_code', 'N/A')}\n"
    formatted += f"𝗣𝗿𝗲𝗽𝗮𝗶𝗱: {'YES' if bin_info.get('prepaid') else 'NO'} | 𝗟𝘂𝗵𝗻 𝗩𝗮𝗹𝗶𝗱: {'YES' if bin_info.get('luhn') else 'NO'}"
    return formatted

MAX_GEN_LIMIT = 20  # একবারে সর্বোচ্চ যতগুলো কার্ড জেনারেট করা যাবে

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

    count = 3  # default
    for i in range(2, len(parts)):
        if parts[i].lower() in [".cnt", "/cnt"] and i + 1 < len(parts):
            if parts[i+1].isdigit():
                count = int(parts[i+1])
            break

    if count > MAX_GEN_LIMIT:
        bot.reply_to(message, f"❌ You can generate a maximum of {MAX_GEN_LIMIT} cards at once.")
        return

    bin_number = extract_bin(bin_input)
    if not bin_number:
        bot.send_message(message.chat.id, "❌ Invalid BIN format.")
        return

    cc_data = asyncio.run(generate_cc_async(bin_input, month, year, cvv, count))
    bin_info = asyncio.run(lookup_bin(bin_number))
    result = format_cc_response(cc_data, bin_input, bin_info)
    user = message.from_user
    username = f"@{user.username}" if user.username else user.first_name
    result += f"\n\n👤 Gen by: {username}"
    bot.send_message(message.chat.id, result)


# /chk or .chk command
@bot.message_handler(func=lambda msg: msg.text.startswith(('/chk', '.chk')))
def handle_chk(message):
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "❌ Provide a card to check.")
        return

    card = parts[1].strip()
    user = message.from_user
    username = f"@{user.username}" if user.username else user.first_name

    # ⏳ Send temporary "checking" message
    sent_msg = bot.reply_to(message, f"🔄 Checking <code>{card}</code>...", parse_mode="HTML")

    # ✅ Run the actual check (can be slow)
    status = check_card(card)

    # ✏️ Edit the previous message with final result
    try:
        bot.edit_message_text(
            chat_id=sent_msg.chat.id,
            message_id=sent_msg.message_id,
            text=f"<code>{card}</code>\n{status}\n\n👤 Checked by: {username}",
            parse_mode="HTML"
        )
    except Exception as e:
        bot.reply_to(message, f"⚠️ Failed to edit message: {str(e)}")


# /mas or .mas command
@bot.message_handler(func=lambda msg: msg.text.startswith(('/mas', '.mas')))
def handle_mass_chk(message):
    if not message.reply_to_message:
        bot.reply_to(message, "❌ Please reply to a message containing cards.")
        return

    lines = message.reply_to_message.text.strip().split('\n')
    cards = [line.strip() for line in lines if '|' in line and line.count('|') == 3]

    if not cards:
        bot.reply_to(message, "❌ No valid cards found in the replied message.")
        return

    # ✅ Limit to 10 cards max
    if len(cards) > 10:
        bot.reply_to(message, f"⚠️ Limit exceeded: You can check a maximum of 10 cards at once. You provided {len(cards)}.")
        return

    user = message.from_user
    username = f"@{user.username}" if user.username else user.first_name

    # ⏳ Send temporary checking message
    sent_msg = bot.reply_to(message, f"🔄 Checking {len(cards)} cards...", parse_mode="HTML")

    # ✅ Prepare results
    results = []
    for card in cards:
        status = check_card(card)
        results.append(f"<code>{card}</code>\n{status}")

    reply_text = "\n\n".join(results) + f"\n\n👤 Checked by: {username}"

    if len(reply_text) > 4000:
        reply_text = reply_text[:3900] + "\n\n⚠️ Output trimmed..."

    # ✏️ Edit the previous message with final results
    try:
        bot.edit_message_text(
            chat_id=sent_msg.chat.id,
            message_id=sent_msg.message_id,
            text=reply_text.strip(),
            parse_mode="HTML"
        )
    except Exception as e:
        bot.reply_to(message, f"⚠️ Failed to edit message: {str(e)}")



# /bin or .bin command
@bot.message_handler(func=lambda m: m.text.startswith(('/bin', '.bin')))
def handle_bin_command(message):
    parts = message.text.strip().split()
    if len(parts) < 2:
        bot.reply_to(message, "❗ একটি BIN দিন যেমন: `/bin 426633`", parse_mode="Markdown")
        return

    bin_number = parts[1]

    try:
        # Async BIN info fetch
        bin_info = asyncio.run(lookup_bin(bin_number))

        if "error" in bin_info:
            bot.reply_to(message, f"❌ ত্রুটি: {bin_info['error']}")
            return

        # Output formatting
        formatted = f"𝗕𝗜𝗡: `{bin_number}`\n"
        formatted += f"𝗧𝘆𝗽𝗲: {bin_info.get('card_type', 'NOT FOUND')} ({bin_info.get('network', 'NOT FOUND')})\n"
        formatted += f"𝗕𝗿𝗮𝗻𝗱: {bin_info.get('tier', 'NOT FOUND')}\n"
        formatted += f"𝐈𝐬𝐬𝐮𝐞𝐫: {bin_info.get('bank', 'NOT FOUND')}\n"
        formatted += f"𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'NOT FOUND')} {bin_info.get('flag', '🏳️')}\n"
        formatted += f"𝗖𝘂𝗿𝗿𝗲𝗻𝗰𝘆: {bin_info.get('currency', 'NOT FOUND')} | 𝗖𝗼𝗱𝗲: {bin_info.get('country_code', 'N/A')}\n"
        formatted += f"𝗣𝗿𝗲𝗽𝗮𝗶𝗱: {'YES' if bin_info.get('prepaid') else 'NO'} | 𝗟𝘂𝗵𝗻 𝗩𝗮𝗹𝗶𝗱: {'YES' if bin_info.get('luhn') else 'NO'}"

        bot.reply_to(message, formatted, parse_mode="Markdown")
    
    except Exception as e:
        bot.reply_to(message, f"❌ Internal error: {str(e)}")

# reveal command
@bot.message_handler(commands=['reveal'])
def show_help(message):
    user = message.from_user
    username = f"@{user.username}" if user.username else user.first_name
    help_text = (
        "🛠 Available Commands:\n\n"
        "/arise — Start the bot\n"
        "/gen or .gen — Generate random cards with BIN info\n"
        "/chk or .chk — Check a single card's status\n"
        "/mas — Check all generated cards at once (reply to a list)\n"
        "/reveal — Show all the commands\n\n"
        "<code>/gen &lt;bin&gt; .cnt &lt;amount&gt;</code> — Control quantity\n"
       f"\n👤 Revealed by: {username}"
    )
    bot.reply_to(message, help_text)

# start/arise command
@bot.message_handler(commands=['start', 'arise'])
def start_command(message):
    user = message.from_user
    username = f"@{user.username}" if user.username else user.first_name
    welcome_text = (
        f"👋 <b>Welcome {username}!</b>\n\n"
        "You Arisied This Bot Here are the available commands you can use:\n\n"
        "<code>/gen</code> or <code>.gen</code> — Generate cards with optional date/CVV and amount\n"
        "<code>/chk</code> or <code>.chk</code> — Check a single card’s status\n"
        "<code>/mas</code> — Mass check cards by replying to card list\n"
        "<code>/reveal</code> — Show all the commands\n\n"
        "<code>/gen &lt;bin&gt; .cnt &lt;amount&gt;</code> — Control quantity\n\n"
        "📢 Join our Telegram Channel:"
        "<a href='https://t.me/bro_bin_lagbe'>https://t.me/bro_bin_lagbe</a>"
    )
    bot.send_message(message.chat.id, welcome_text, parse_mode="HTML")

# Run the bot
if __name__ == '__main__':
    print("Bot is running...")
    bot.infinity_polling()
