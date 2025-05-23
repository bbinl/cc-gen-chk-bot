import telebot
import asyncio
import aiohttp
import re

# BOT TOKEN - Replace with your real token
BOT_TOKEN = "7526852134:AAGx1RKchBl5GAGVWih7a0E7PmXEo2D0HO8"
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# Country flag mapping
COUNTRY_FLAGS = {
    "FRANCE": "🇫🇷", "UNITED STATES": "🇺🇸", "BRAZIL": "🇧🇷", "NAMIBIA": "🇳🇦",
    "INDIA": "🇮🇳", "GERMANY": "🇩🇪", "THAILAND": "🇹🇭", "MEXICO": "🇲🇽", "RUSSIA": "🇷🇺",
}

# Trained card statuses
TRAINED_CARDS = {
    "5154620016971366|05|2028|065": "✅ Live",
    "5195357304800426|10|2029|530": "✅ Live",
    "5195357304883083|05|2029|680": "✅ Live",
    "5154620016972380|01|2029|245": "❔ Unknown",
    "5154620016974766|05|2029|743": "❔ Unknown",
    "5154620016970277|09|2027|140": "❔ Unknown",
    "5195357304800574|09|2030|851": "❔ Unknown",
    "5195357304818212|05|2029|447": "❔ Unknown",
    "5195357304802125|12|2027|571": "❔ Unknown",
    "5195357304821885|01|2029|680": "❔ Unknown",
}

def check_card_status(card):
    return TRAINED_CARDS.get(card.strip(), "❌ Dead")

# BIN extractor
def extract_bin(bin_input):
    match = re.match(r'(\d{6,16})', bin_input)
    return match.group(1).ljust(16, 'x') if match and len(match.group(1)) == 6 else match.group(1) if match else None

# Async BIN info fetcher
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

# Async CC generator
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

# Format generator result
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

# /gen command
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

# /chk command
@bot.message_handler(func=lambda msg: msg.text.startswith(('/chk', '.chk')))
def check_command(message):
    try:
        parts = message.text.strip().split()
        if len(parts) < 2:
            bot.send_message(message.chat.id, "⚠️ Usage: /chk <code>4111111111111111|12|2025|123</code>", parse_mode="HTML")
            return
        card_input = parts[1]
        if '|' not in card_input or len(card_input.split('|')) not in [3, 4]:
            bot.send_message(message.chat.id, "⚠️ Invalid format. Try like: <code>/chk 4111111111111111|12|2025|123</code>", parse_mode="HTML")
            return
        result = check_card_status(card_input)
        bot.send_message(message.chat.id, f"𝗖𝗮𝗿𝗱: <code>{card_input}</code>\n𝗥𝗲𝘀𝘂𝗹𝘁: {result}", parse_mode="HTML")

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error while checking card: {e}")

# /start command
@bot.message_handler(commands=['start'])
def start_command(message):
    bot.send_message(
        message.chat.id,
        "👋 Welcome! Available commands:\n"
        "<code>/gen 515462</code> - Generate cards\n"
        "<code>/chk 5154620016971366|05|2028|065</code> - Check card status",
        parse_mode="HTML"
    )

# Run the bot
if __name__ == '__main__':
    print("✅ Bot is running...")
    bot.delete_webhook()
    bot.infinity_polling(timeout=60, long_polling_timeout=60)
