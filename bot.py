import telebot
import requests
import re

BOT_TOKEN = "7526852134:AAGx1RKchBl5GAGVWih7a0E7PmXEo2D0HO8"
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# Country flag mapping
COUNTRY_FLAGS = {
    "FRANCE": "🇫🇷", "UNITED STATES": "🇺🇸", "BRAZIL": "🇧🇷", "NAMIBIA": "🇳🇦",
    "INDIA": "🇮🇳", "GERMANY": "🇩🇪", "THAILAND": "🇹🇭", "MEXICO": "🇲🇽", "RUSSIA": "🇷🇺",
}

# BIN extractor
def extract_bin(text):
    match = re.match(r'(\d{6,16})', text)
    return match.group(1).ljust(16, 'x') if match and len(match.group(1)) == 6 else match.group(1) if match else None

# BIN Info
def get_bin_info(bin_number):
    try:
        url = f"https://drlabapis.onrender.com/api/bin?bin={bin_number[:6]}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            country = data.get('country', 'NOT FOUND').upper()
            return {
                "bank": data.get('issuer', 'NOT FOUND').upper(),
                "card_type": data.get('type', 'NOT FOUND').upper(),
                "network": data.get('scheme', 'NOT FOUND').upper(),
                "tier": data.get('tier', 'NOT FOUND').upper(),
                "country": country,
                "flag": COUNTRY_FLAGS.get(country, "🏳️")
            }
        return {"error": "BIN API error"}
    except Exception as e:
        return {"error": str(e)}

# CC Generator
def generate_cards(bin_number):
    try:
        url = f"https://drlabapis.onrender.com/api/ccgenerator?bin={bin_number}&count=10"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.text.strip().split("\n")
        return {"error": "GEN API error"}
    except Exception as e:
        return {"error": str(e)}

# Format CC Output
def format_cc(data, bin_number, bin_info):
    if isinstance(data, dict) and "error" in data:
        return f"❌ ERROR: {data['error']}"
    formatted = f"𝗕𝗜𝗡 ⇾ <code>{bin_number[:6]}</code>\n"
    formatted += f"𝗔𝗺𝗼𝘂𝗻𝘁 ⇾ <code>{len(data)}</code>\n\n"
    for card in data:
        formatted += f"<code>{card}</code>\n"
    formatted += f"\n𝗜𝗻𝗳𝗼: {bin_info.get('card_type')} - {bin_info.get('network')} ({bin_info.get('tier')})\n"
    formatted += f"𝐈𝐬𝐬𝐮𝐞𝐫: {bin_info.get('bank')}\n"
    formatted += f"𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country')} {bin_info.get('flag')}"
    return formatted

# /gen command
@bot.message_handler(commands=['gen'])
def handle_gen(message):
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "❌ Please provide a BIN. Example: /gen 457173")
        return

    bin_input = extract_bin(args[1])
    if not bin_input:
        bot.reply_to(message, "❌ Invalid BIN format.")
        return

    bin_info = get_bin_info(bin_input)
    cc_data = generate_cards(bin_input)
    reply = format_cc(cc_data, bin_input, bin_info)
    bot.send_message(message.chat.id, reply)

# /bin command
@bot.message_handler(commands=['bin'])
def handle_bin(message):
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "❌ Please provide a BIN. Example: /bin 457173")
        return

    bin_input = extract_bin(args[1])
    if not bin_input:
        bot.reply_to(message, "❌ Invalid BIN format.")
        return

    info = get_bin_info(bin_input)
    if "error" in info:
        bot.reply_to(message, f"❌ {info['error']}")
        return

    reply = (
        f"𝗕𝗜𝗡 ⇾ <code>{bin_input[:6]}</code>\n\n"
        f"𝗜𝗻𝗳𝗼: {info.get('card_type')} - {info.get('network')} ({info.get('tier')})\n"
        f"𝐈𝐬𝐬𝐮𝐞𝐫: {info.get('bank')}\n"
        f"𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {info.get('country')} {info.get('flag')}"
    )
    bot.send_message(message.chat.id, reply)

# /start command
@bot.message_handler(commands=['start'])
def handle_start(message):
    bot.reply_to(message, "👋 Welcome!\nUse:\n<code>/gen 457173</code> - To generate CCs\n<code>/bin 457173</code> - To check BIN info")
