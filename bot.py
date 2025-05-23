import telebot
import asyncio
import aiohttp
import re

# BOT TOKEN - Keep it safe
BOT_TOKEN = "7526852134:AAGx1RKchBl5GAGVWih7a0E7PmXEo2D0HO8"  # Replace with your actual bot token
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# Country flag mapping
COUNTRY_FLAGS = {
    "FRANCE": "🇫🇷", "UNITED STATES": "🇺🇸", "BRAZIL": "🇧🇷", "NAMIBIA": "🇳🇦",
    "INDIA": "🇮🇳", "GERMANY": "🇩🇪", "THAILAND": "🇹🇭", "MEXICO": "🇲🇽", "RUSSIA": "🇷🇺",
}

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

# Luhn Algorithm Checker
def luhn_check(card_number):
    digits = [int(x) for x in card_number if x.isdigit()]
    checksum = 0
    double = False
    for d in reversed(digits):
        if double:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
        double = not double
    return checksum % 10 == 0

# Format response
def format_cc_response(data, bin_number, bin_info):
    if isinstance(data, dict) and "error" in data:
        return f"❌ ERROR: {data['error']}"
    if not data:
        return "❌ NO CARDS GENERATED."

    formatted = f"ᴽᵒᵋ → <code>{bin_number[:6]}</code>\n"
    formatted += f"ᴀᴏᴜɴᴟ → <code>{len(data)}</code>\n\n"
    for card in data:
        formatted += f"<code>{card.upper()}</code>\n"
    formatted += f"\nᵀᴿᴮ: {bin_info.get('card_type', 'NOT FOUND')} - {bin_info.get('network', 'NOT FOUND')} ({bin_info.get('tier', 'NOT FOUND')})\n"
    formatted += f"ᴀɪᴻᴻᴀᴟʀ: {bin_info.get('bank', 'NOT FOUND')}\n"
    formatted += f"ᵟᵒɴᴿʀᴅᵗ: {bin_info.get('country', 'NOT FOUND')} {bin_info.get('flag', '🏳️')}"
    return formatted

# /gen Command
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

# /chk Command (local validation)
@bot.message_handler(func=lambda msg: msg.text.startswith(('/chk', '.chk')))
def chk_single_card(message):
    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.send_message(message.chat.id, "❌ Provide a card to check.\nExample: <code>/chk 5154620000000000|12|2025|123</code>")
            return

        card_line = parts[1]
        card_number = card_line.split('|')[0]
        if not re.match(r'^\d{16}$', card_number):
            bot.send_message(message.chat.id, f"❌ Invalid card number format → <code>{card_line}</code>")
            return

        is_valid = luhn_check(card_number)
        status = "✅ VALID" if is_valid else "❌ INVALID"
        bot.send_message(message.chat.id, f"{status} → <code>{card_line}</code>")

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Unexpected Error: {e}")

# /mas.chk Command (multi-line local validation)
@bot.message_handler(func=lambda msg: msg.text.startswith(('/mas.chk', '.mas.chk')))
def chk_multiple_cards(message):
    try:
        lines = message.text.split('\n')[1:]  # Skip the command line
        if not lines:
            bot.send_message(message.chat.id, "❌ Please input cards below the command.")
            return

        results = []
        for card_line in lines:
            card_line = card_line.strip()
            if not card_line:
                continue
            card_number = card_line.split('|')[0]
            if not re.match(r'^\d{16}$', card_number):
                results.append(f"❌ INVALID FORMAT → <code>{card_line}</code>")
                continue

            is_valid = luhn_check(card_number)
            status = "✅ VALID" if is_valid else "❌ INVALID"
            results.append(f"{status} → <code>{card_line}</code>")

        bot.send_message(message.chat.id, "\n".join(results) if results else "❌ No valid card lines provided.")

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Unexpected Error: {e}")

# /start command
@bot.message_handler(commands=['start'])
def start_command(message):
    bot.send_message(message.chat.id, "👋 Welcome!\nUse <code>/gen [BIN]</code> to generate cards.\nUse <code>/chk [CARD]</code> to check a card.\nUse <code>/mas.chk</code> and then paste multiple cards below.")

# Entry point
if __name__ == '__main__':
    print("Bot is running...")
    bot.delete_webhook()
    bot.infinity_polling(timeout=60, long_polling_timeout=60)
