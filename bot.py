import telebot
import asyncio
import aiohttp
import re
import random

BOT_TOKEN = "7526852134:AAGx1RKchBl5GAGVWih7a0E7PmXEo2D0HO8"
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

COUNTRY_FLAGS = {
    "FRANCE": "🇫🇷", "UNITED STATES": "🇺🇸", "BRAZIL": "🇧🇷", "NAMIBIA": "🇳🇦",
    "INDIA": "🇮🇳", "GERMANY": "🇩🇪", "THAILAND": "🇹🇭", "MEXICO": "🇲🇽", "RUSSIA": "🇷🇺",
}

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
    except Exception as e:
        return {"error": str(e)}

async def generate_cc_async(bin_number):
    url = f"https://drlabapis.onrender.com/api/ccgenerator?bin={bin_number}&count=10"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    raw_text = await response.text()
                    return raw_text.strip().split("\n")
    except Exception as e:
        return {"error": str(e)}

def simulate_card_check(card):
    outcome = random.choices(["Live", "Dead", "Unknown"], weights=[5, 3, 2])[0]
    return f"<code>{card}</code> → <b>{outcome}</b>"

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

@bot.message_handler(commands=['start'])
def start_command(message):
    bot.send_message(message.chat.id, "👋 Welcome! Use <code>/gen [BIN]</code> to generate cards.\nExample: <code>/gen 515462</code>")

@bot.message_handler(func=lambda msg: msg.text.startswith(('/gen', '.gen')))
def gen_command(message):
    try:
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

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Unexpected Error: {e}")

@bot.message_handler(commands=['mas.chk'])
def check_generated_cards(message):
    if not message.reply_to_message or not message.reply_to_message.text:
        bot.send_message(message.chat.id, "⚠️ Please reply to a card list.")
        return

    lines = message.reply_to_message.text.splitlines()
    cards = [line.strip().strip("<code>").strip("</code>") for line in lines if re.match(r'^\d{16}\|\d{2}\|\d{4}\|\d{3}$', line.strip())]
    if not cards:
        bot.send_message(message.chat.id, "⚠️ No valid card format found.")
        return

    results = "\n".join([simulate_card_check(card) for card in cards])
    bot.send_message(message.chat.id, f"🔍 <b>Card Check Results:</b>\n\n{results}")

if __name__ == '__main__':
    print("Bot is running...")
    bot.delete_webhook()
    bot.infinity_polling(timeout=60, long_polling_timeout=60)
