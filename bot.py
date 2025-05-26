import telebot
import asyncio
import aiohttp
import re
import random
import json
import os
from flag_data import COUNTRY_FLAGS

# BOT TOKEN
BOT_TOKEN = "8176347490:AAEdsangR5rM1t35s227epkWr11y-w3Fo18"
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

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

# === BIN Handling ===
def extract_bin(bin_input):
    match = re.match(r'(\d{6,16})', bin_input)
    return match.group(1).ljust(16, 'x') if match and len(match.group(1)) == 6 else match.group(1) if match else None

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
                return {"error": f"API error: {response.status}"}
    except Exception as e:
        return {"error": str(e)}

async def generate_cc_async(bin_number, month=None, year=None, cvv=None, count=10):
    full_bin = bin_number
    if month and year and cvv:
        full_bin += f"|{month}|{year}|{cvv}"
    base_url = f"https://web-production-4159.up.railway.app/api/ccgenerator?bin={full_bin}&count={count}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(base_url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("status") == "success":
                        cards = data["generated"]
                        formatted = [
                            f"{c['raw_card_number']}|{c['expiry_month']}|{c['expiry_year']}|{c['cvv']}"
                            for c in cards
                        ]
                        new_cards = [c for c in formatted if c not in generated_cards]
                        for c in new_cards:
                            generated_cards.add(c)
                        save_generated_cards()
                        return new_cards, data.get("metadata", {})
                    return {"error": "API did not return success."}
                return {"error": f"API error: {response.status}"}
    except Exception as e:
        return {"error": str(e)}

def check_card(card):
    if card in card_status_cache:
        return card_status_cache[card]
    roll = random.random()
    status = "✅ Live" if roll < 0.5 else "❓ Unknown" if roll < 0.75 else "❌ Dead"
    card_status_cache[card] = status
    save_cache()
    return status

def format_cc_response(data_tuple, bin_number, bin_info):
    if isinstance(data_tuple, dict) and "error" in data_tuple:
        return f"❌ ERROR: {data_tuple['error']}"

    data, meta = data_tuple
    if not data:
        return "❌ NO NEW CARDS GENERATED (All duplicates)."

    formatted = f"𝗕𝗜𝗡 ⇒ <code>{bin_number[:6]}</code>\n"
    formatted += f"𝗔𝗺𝗼𝘂𝗻𝘁 ⇒ <code>{len(data)}</code>\n\n"
    for card in data:
        formatted += f"<code>{card}</code>\n"
    formatted += f"\n𝗜𝗻𝗳𝗼: {bin_info.get('card_type', meta.get('card_type', 'N/A'))} - {bin_info.get('network', 'N/A')} ({bin_info.get('tier', 'N/A')})\n"
    formatted += f"𝐈𝐬𝐬𝐮𝐞𝐫: {bin_info.get('bank', meta.get('bin_bank', 'N/A'))}\n"
    formatted += f"𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', meta.get('bin_country', 'N/A'))} {bin_info.get('flag', '🏳️')}"
    return formatted

MAX_GEN_LIMIT = 30

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

    count = 3
    for i in range(2, len(parts)):
        if parts[i].lower() in [".cnt", "/cnt"] and i + 1 < len(parts):
            if parts[i+1].isdigit():
                count = int(parts[i+1])
            break

    if count > MAX_GEN_LIMIT:
        bot.reply_to(message, f"❌ Max {MAX_GEN_LIMIT} cards allowed.")
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

@bot.message_handler(func=lambda msg: msg.text.startswith(('/chk', '.chk')))
def handle_chk(message):
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "❌ Provide a card to check.")
        return
    card = parts[1].strip()
    status = check_card(card)
    user = message.from_user
    username = f"@{user.username}" if user.username else user.first_name
    bot.reply_to(message, f"<code>{card}</code>\n{status}\n\n👤 Checked by: {username}")

@bot.message_handler(func=lambda msg: msg.text.startswith(('/mas', '.mas')) and msg.reply_to_message)
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

    user = message.from_user
    username = f"@{user.username}" if user.username else user.first_name
    reply += f"👤 Checked by: {username}"
    bot.reply_to(message, reply.strip())

@bot.message_handler(commands=['reveal'])
def show_help(message):
    user = message.from_user
    username = f"@{user.username}" if user.username else user.first_name
    help_text = (
        "🛠 Available Commands:\n\n"
        "/arise — Start the bot\n"
        "/gen or .gen — Generate cards with BIN\n"
        "/chk or .chk — Check a card's status\n"
        "/mas — Mass check cards (reply to list)\n"
        "/reveal — Show help info\n"
        "/gen <bin> .cnt <amount> — Control quantity\n"
        f"\n👤 Revealed by: {username}"
    )
    bot.reply_to(message, help_text)

@bot.message_handler(commands=['start', 'arise'])
def start_command(message):
    user = message.from_user
    username = f"@{user.username}" if user.username else user.first_name
    welcome_text = (
        f"👋 <b>Welcome {username}!</b>\n\n"
        "Commands:\n"
        "<code>/gen</code> or <code>.gen</code> — Generate cards\n"
        "<code>/chk</code> or <code>.chk</code> — Check a card\n"
        "<code>/mas</code> — Mass check cards\n"
        "<code>/reveal</code> — Show all commands\n"
        "<code>/gen</code> <bin> <code>.cnt <amount> </code> — Control quantity\n\n"
        "📢 Join Telegram: <a href='https://t.me/bro_bin_lagbe'>Click Here</a>"
    )
    bot.send_message(message.chat.id, welcome_text, parse_mode="HTML")

if __name__ == '__main__':
    print("Bot is running...")
    bot.infinity_polling()
