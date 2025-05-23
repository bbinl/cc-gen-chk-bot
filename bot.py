import telebot
import json
import os
from collections import defaultdict

# টেলিগ্রাম বট টোকেন
BOT_TOKEN = "7526852134:AAGx1RKchBl5GAGVWih7a0E7PmXEo2D0HO8"
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# JSON ফাইল যেখানে চেক করা কার্ড ও স্ট্যাটাস রাখা হবে
STATUS_FILE = "card_status.json"
card_status_cache = {}
generated_cards = defaultdict(list)

# স্ট্যাটাস JSON লোড/সেভ ফাংশন
def load_card_status():
    if os.path.exists(STATUS_FILE):
        with open(STATUS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_card_status():
    with open(STATUS_FILE, "w") as f:
        json.dump(card_status_cache, f, indent=2)

# বট চালু হলে পুরানো স্ট্যাটাস লোড
card_status_cache = load_card_status()

# কার্ড চেকার ফাংশন (ডেমো লজিক)
def simulate_card_check(card):
    if card in card_status_cache:
        return card_status_cache[card]
    if card[-1] in "13579":
        status = "Live"
    elif card[-1] in "02468":
        status = "Dead"
    else:
        status = "Unknown"
    card_status_cache[card] = status
    save_card_status()
    return status

# /gen কমান্ড
@bot.message_handler(func=lambda msg: msg.text.startswith(('/gen', '.gen')))
def handle_gen(msg):
    bin_prefix = "515462"
    cards = [f"{bin_prefix}{i:010d}|{(i%12)+1:02d}|202{7 + (i % 4)}|{100 + (i % 900)}" for i in range(10)]
    generated_cards[msg.message_id] = cards
    card_list = "\n".join(f"<code>{card}</code>" for card in cards)
    bot.send_message(msg.chat.id, f"✅ Generated Cards:\n{card_list}")

# /chk কমান্ড
@bot.message_handler(func=lambda msg: msg.text.startswith(('/chk', '.chk')))
def handle_chk(msg):
    parts = msg.text.split()
    if len(parts) < 2:
        bot.send_message(msg.chat.id, "❌ উদাহরণ: /chk 5154620000000001|01|2029|123")
        return
    card = parts[1].strip()
    status = simulate_card_check(card)
    bot.send_message(msg.chat.id, f"🧾 <code>{card}</code>\nStatus: <b>{status}</b>")

# /mas.chk কমান্ড
@bot.message_handler(commands=['mas.chk'])
def handle_mas_chk(msg):
    if not msg.reply_to_message or msg.reply_to_message.message_id not in generated_cards:
        bot.send_message(msg.chat.id, "❌ Reply করতে হবে জেনারেট করা কার্ড লিস্টে।")
        return
    cards = generated_cards[msg.reply_to_message.message_id]
    result_lines = [f"<code>{c}</code> ➜ <b>{simulate_card_check(c)}</b>" for c in cards]
    bot.send_message(msg.chat.id, "📋 Bulk Check Results:\n" + "\n".join(result_lines))

# /start কমান্ড
@bot.message_handler(commands=['start'])
def start_cmd(msg):
    bot.send_message(
        msg.chat.id,
        "👋 স্বাগতম! আপনি ব্যবহার করতে পারেন:\n"
        "/gen বা .gen – কার্ড তৈরি করতে\n"
        "/chk [কার্ড] – একটি কার্ড চেক করতে\n"
        "/mas.chk – বাল্ক চেক (reply করে)"
    )

# বট চালু
if __name__ == '__main__':
    print("✅ Bot is running...")
    bot.infinity_polling()
