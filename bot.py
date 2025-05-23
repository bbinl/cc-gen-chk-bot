import telebot
import asyncio
import aiohttp
import re

# BOT TOKEN - Keep it safe
BOT_TOKEN = "here"  # Replace with your actual bot token
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

# Async CC Checker
async def check_cc_async(card_details):
    url = "https://drlabapis.onrender.com/api/ccchecker"
    params = {"card": card_details}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=10) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    return {"error": f"API error: {response.status}"}
    except Exception as e:
        return {"error": str(e)}

# Format response
def format_cc_response(data, bin_number, bin_info):
    if isinstance(data, dict) and "error" in data:
        return f"❌ ERROR: {data['error']}"
    if not data:
        return "❌ NO CARDS GENERATED."

    formatted = f"ᵝᵒᵏ → <code>{bin_number[:6]}</code>\n"
    formatted += f"ᴀᵍᴏᴜɴᴛ → <code>{len(data)}</code>\n\n"
    for card in data:
        formatted += f"<code>{card.upper()}</code>\n"
    formatted += f"\nᵀᴿᵒ: {bin_info.get('card_type', 'NOT FOUND')} - {bin_info.get('network', 'NOT FOUND')} ({bin_info.get('tier', 'NOT FOUND')})\n"
    formatted += f"ᴀɪᵛᵛᴇʀ: {bin_info.get('bank', 'NOT FOUND')}\n"
    formatted += f"ᵟᵒɴᴠᵒʀᴅʏ: {bin_info.get('country', 'NOT FOUND')} {bin_info.get('flag', '🏳️')}"
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

# /chk Command
@bot.message_handler(func=lambda msg: msg.text.startswith(('/chk', '.chk')))
def chk_single_card(message):
    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.send_message(message.chat.id, "❌ Provide a card to check.\nExample: <code>/chk 5154620000000000|12|2025|123</code>")
            return

        card = parts[1]
        result = asyncio.run(check_cc_async(card))

        if "error" in result:
            bot.send_message(message.chat.id, f"❌ Error: {result['error']}")
        else:
            status = "✅ LIVE" if result.get("status") == "live" else "❌ DEAD"
            bot.send_message(message.chat.id, f"{status} → <code>{card}</code>")

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Unexpected Error: {e}")

# /mas.chk Command
@bot.message_handler(func=lambda msg: msg.text.startswith(('/mas.chk', '.mas.chk')))
def chk_multiple_cards(message):
    try:
        lines = message.text.split('\n')[1:]  # Skip the command line
        if not lines:
            bot.send_message(message.chat.id, "❌ Please input cards below the command.")
            return

        results = []
        for card in lines:
            res = asyncio.run(check_cc_async(card.strip()))
            if "error" in res:
                results.append(f"❌ ERROR → <code>{card.strip()}</code>")
            else:
                status = "✅ LIVE" if res.get("status") == "live" else "❌ DEAD"
                results.append(f"{status} → <code>{card.strip()}</code>")

        bot.send_message(message.chat.id, "\n".join(results))

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
