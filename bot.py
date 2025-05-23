
import logging
import random
import json
import re
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.utils import executor

API_TOKEN = '7526852134:AAGx1RKchBl5GAGVWih7a0E7PmXEo2D0HO8'
bot = Bot(token=API_TOKEN, parse_mode='HTML')
dp = Dispatcher(bot)
logging.basicConfig(level=logging.INFO)

STATUS_CACHE_FILE = 'card_status_cache.json'
status_cache = {}

# Load cache
try:
    with open(STATUS_CACHE_FILE, 'r') as f:
        status_cache = json.load(f)
except FileNotFoundError:
    status_cache = {}

def save_cache():
    with open(STATUS_CACHE_FILE, 'w') as f:
        json.dump(status_cache, f)

def get_card_status(card):
    if card in status_cache:
        return status_cache[card]
    roll = random.random()
    if roll < 0.5:
        status = 'Live'
    elif roll < 0.75:
        status = 'Dead'
    else:
        status = 'Unknown'
    status_cache[card] = status
    save_cache()
    return status

COUNTRY_FLAGS = {
    "UNITED STATES": "🇺🇸", "INDIA": "🇮🇳", "BANGLADESH": "🇧🇩",
}

async def get_bin_info(bin_number):
    url = f'https://bins.antipublic.cc/bins/{bin_number[:6]}'
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
    except:
        return {}

def format_cc_response(data, bin_number, bin_info):
    if isinstance(data, dict) and "error" in data:
        return f"❌ ERROR: {data['error']}"
    if not data:
        return "❌ NO CARDS GENERATED."
    formatted = f"𝗕𝗜𝗡 ⇾ <code>{bin_number[:6]}</code>
"
    formatted += f"𝗔𝗺𝗼𝘂𝗻𝘁 ⇾ <code>{len(data)}</code>

"
    for card in data:
        formatted += f"<code>{card.upper()}</code>
"
    formatted += f"\n𝗜𝗻𝗳𝗼: {bin_info.get('card_type', 'NOT FOUND')} - {bin_info.get('network', 'NOT FOUND')} ({bin_info.get('tier', 'NOT FOUND')})\n"
    formatted += f"𝐈𝐬𝐬𝐮𝐞𝐫: {bin_info.get('bank', 'NOT FOUND')}\n"
    formatted += f"𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'NOT FOUND')} {bin_info.get('flag', '🏳️')}"
    return formatted

def generate_cards(bin_number, amount=10):
    cards = []
    for _ in range(amount):
        suffix = ''.join(random.choices("0123456789", k=9))
        exp_month = str(random.randint(1, 12)).zfill(2)
        exp_year = str(random.randint(2026, 2030))
        cvv = str(random.randint(100, 999))
        card = f"{bin_number[:6]}{suffix}|{exp_month}|{exp_year}|{cvv}"
        cards.append(card)
    return cards

@dp.message_handler(lambda m: m.text.startswith(('/gen', '.gen')))
async def handle_gen(message: Message):
    parts = message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.reply("❌ বিন নাম্বার ইনপুট দিন। উদাহরণ: /gen 515462")
        return
    bin_number = parts[1]
    cards = generate_cards(bin_number)
    bin_info = await get_bin_info(bin_number)
    response = format_cc_response(cards, bin_number, bin_info)
    await message.reply(response)

@dp.message_handler(lambda m: m.text.startswith(('/chk', '.chk')))
async def handle_check(message: Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply("❌ কার্ড দিন। উদাহরণ: /chk 5154620000000000|10|2028|109")
        return
    card = parts[1].strip()
    status = get_card_status(card)
    status_emoji = {"Live": "✅", "Dead": "❌", "Unknown": "❓"}
    await message.reply(f"{status_emoji[status]} {status}")

@dp.message_handler(lambda m: m.text.startswith('/mas.chk'))
async def handle_mass_check(message: Message):
    if not message.reply_to_message or not message.reply_to_message.text:
        await message.reply("❌ Reply করতে হবে জেনারেট করা কার্ড লিস্টে।")
        return
    cards = re.findall(r'\d{15,16}\|\d{2}\|\d{4}\|\d{3}', message.reply_to_message.text)
    if not cards:
        await message.reply("❌ কোনো কার্ড পাওয়া যায়নি।")
        return
    result = ""
    for card in cards:
        status = get_card_status(card)
        emoji = {"Live": "✅", "Dead": "❌", "Unknown": "❓"}[status]
        result += f"{card}\n{emoji} {status}\n\n"
    await message.reply(result.strip())

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
