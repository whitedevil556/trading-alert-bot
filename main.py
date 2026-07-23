# 🟢 सर्व आवश्यक लायब्ररीज
import telebot
import logzero
from SmartApi import SmartConnect
from apscheduler.schedulers.background import BackgroundScheduler
from supabase import create_client, Client
import pandas as pd
import datetime
import pyotp
import time
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

# ==========================================
# ⚙️ १. सर्व क्रेडेन्शियल्स
# ==========================================
TELEGRAM_TOKEN = "8769731052:AAEekGCG7hpi8L9lpotPjWKSHliydXfEDhk"
ADMIN_CHAT_ID = "1311752899"
ADMIN_USERNAME = "@mmhcr"

ANGEL_API_KEY = "eyUtPguP"
ANGEL_CLIENT_ID = "M692092"
ANGEL_PASSWORD = "4248"
ANGEL_TOTP_KEY = "KU4BY7F74REXTA7T2BKFINN55E"

# 🟢 Supabase Configs
SUPABASE_URL = "https://nithcddmdlzudauvcoxy.supabase.co"
SUPABASE_KEY = "sb_publishable_KuHxRULppKuRsJgvbRssBA_mwoFxqtd"

bot = telebot.TeleBot(TELEGRAM_TOKEN)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==========================================
# 📂 २. युजर डेटा मॅनेजमेंट (Supabase Database)
# ==========================================
def load_subscribers():
    try:
        response = supabase.table("subscribers").select("*").execute()
        subs = {}
        for row in response.data:
            subs[str(row['chat_id'])] = {
                "name": row['name'],
                "phone": row['phone'],
                "date": row['date']
            }
        return subs
    except Exception as e:
        print(f"❌ Database Read Error: {e}")
        return {}

def save_subscriber(chat_id, name, phone):
    try:
        today_str = str(datetime.date.today())
        data = {
            "chat_id": str(chat_id),
            "name": name,
            "phone": phone,
            "date": today_str
        }
        supabase.table("subscribers").upsert(data).execute()
        all_subs = load_subscribers()
        return len(all_subs)
    except Exception as e:
        print(f"❌ Database Save Error: {e}")
        return 0

# ==========================================
# 📈 ३. अँगल वन स्कॅनर इंजिन
# ==========================================
def get_angel_scan_results():
    obj = SmartConnect(api_key=ANGEL_API_KEY)
    try:
        totp = pyotp.TOTP(ANGEL_TOTP_KEY).now() if ANGEL_TOTP_KEY else ""
        login_data = obj.generateSession(ANGEL_CLIENT_ID, ANGEL_PASSWORD, totp)
        if not (login_data and login_data.get('status')):
            return None, None
    except Exception:
        return None, None

    NIFTY_STOCKS_ANGEL = {
        'RELIANCE': '2885', 'HDFCBANK': '1333', 'ICICIBANK': '4963', 'INFY': '1594', 'TCS': '11536',
        'ITC': '1660', 'LT': '11483', 'AXISBANK': '5900', 'SBIN': '3045', 'BHARTIARTL': '10604',
        'KOTAKBANK': '1922', 'TATAMOTORS': '3456', 'M&M': '2031', 'NTPC': '11630', 'TITAN': '3506',
        'HCLTECH': '7229', 'SUNPHARMA': '3351', 'MARUTI': '10999', 'ULTRACEMCO': '11532', 'ASIANPAINT': '236'
    }

    today_str = datetime.date.today().strftime('%Y-%m-%d')
    from_date_time = f"{today_str} 09:15"
    to_date_time = f"{today_str} 09:20"

    bullish_stocks = []
    bearish_stocks = []

    for symbol, token in NIFTY_STOCKS_ANGEL.items():
        try:
            historicParam = {
                "exchange": "NSE",
                "symboltoken": token,
                "interval": "FIVE_MINUTE",
                "fromdate": from_date_time,
                "todate": to_date_time
            }
            resp = obj.getCandleData(historicParam)
            if not resp or 'data' not in resp or not resp['data']:
                continue
                
            candle = resp['data'][0]
            open_p, high_p, low_p = float(candle[1]), float(candle[2]), float(candle[3])

            if open_p == low_p:
                bullish_stocks.append({'symbol': symbol, 'open': open_p, 'high': high_p, 'low': low_p})
            elif open_p == high_p:
                bearish_stocks.append({'symbol': symbol, 'open': open_p, 'high': high_p, 'low': low_p})
        except Exception:
            continue

    return bullish_stocks, bearish_stocks

def send_scan_report(chat_id):
    bullish, bearish = get_angel_scan_results()
    
    if bullish is None:
        bot.send_message(chat_id, "❌ अँगल वन सर्व्हरशी कनेक्ट होऊ शकलो नाही.")
        return

    if bullish:
        msg_bullish = f"🟢 **BULLISH STOCKS (Open = Low)** 🟢\n*Total: {len(bullish)} Stocks*\n\n"
        for item in bullish:
            msg_bullish += f"🚀 **{item['symbol']}** (O/L: ₹{item['open']:.2f} | H: ₹{item['high']:.2f})\n"
        bot.send_message(chat_id, msg_bullish, parse_mode="Markdown")
    else:
        bot.send_message(chat_id, "🟢 **BULLISH:** आज एकही परफेक्ट O=L स्टॉक सापडला नाही.", parse_mode="Markdown")

    if bearish:
        msg_bearish = f"🔴 **BEARISH STOCKS (Open = High)** 🔴\n*Total: {len(bearish)} Stocks*\n\n"
        for item in bearish:
            msg_bearish += f"🩸 **{item['symbol']}** (O/H: ₹{item['open']:.2f} | L: ₹{item['low']:.2f})\n"
        bot.send_message(chat_id, msg_bearish, parse_mode="Markdown")
    else:
        bot.send_message(chat_id, "🔴 **BEARISH:** आज एकही परफेक्ट O=H स्टॉक सापडला नाही.", parse_mode="Markdown")

# ==========================================
# ⏰ ४. ऑटो-अलर्ट शेड्यूलर (सकाळी ९:१६)
# ==========================================
def daily_auto_scan():
    print("⏰ [Auto Scheduler] सकाळी ९:१६ वाजले आहेत - ऑटो-स्कॅन सुरू होत आहे...")
    subs = load_subscribers()
    if not subs:
        return

    bullish, bearish = get_angel_scan_results()
    if bullish is None:
        return

    msg_bullish = f"⏰ **सकाळचा ऑटो-अलर्ट 📊**\n\n🟢 **BULLISH (Open = Low) - {len(bullish)} Stocks:**\n"
    if bullish:
        for item in bullish:
            msg_bullish += f"• **{item['symbol']}** (₹{item['open']:.2f})\n"
    else:
        msg_bullish += "एकही स्टॉक सापडला नाही.\n"

    msg_bearish = f"\n🔴 **BEARISH (Open = High) - {len(bearish)} Stocks:**\n"
    if bearish:
        for item in bearish:
            msg_bearish += f"• **{item['symbol']}** (₹{item['open']:.2f})\n"
    else:
        msg_bearish += "एकही स्टॉक सापडला नाही.\n"

    full_report = msg_bullish + msg_bearish

    for chat_id in subs.keys():
        try:
            bot.send_message(chat_id, full_report, parse_mode="Markdown")
            time.sleep(0.5)
        except Exception:
            continue

scheduler = BackgroundScheduler(timezone="Asia/Kolkata")
scheduler.add_job(daily_auto_scan, 'cron', day_of_week='mon-fri', hour=9, minute=16)
scheduler.start()

# ==========================================
# 🤖 ५. टेलिग्राम कमांड्स
# ==========================================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_text = (
        "👋 *स्वागत आहे!* 🚀\n\n"
        "मी तुमचा वैयक्तिक **Trading Alert Bot** आहे.\n"
        "खालील पर्यायांपैकी एक निवडा:"
    )
    markup = InlineKeyboardMarkup()
    markup.row_width = 2
    btn1 = InlineKeyboardButton("📊 आत्ता स्कॅन करा", callback_data="scan_now")
    btn2 = InlineKeyboardButton("⏰ डेली ऑटो-अलर्ट", callback_data="subscribe")
    btn3 = InlineKeyboardButton("📈 स्ट्रॅटेजी माहिती", callback_data="strategy")
    btn4 = InlineKeyboardButton("📞 सपोर्ट / ॲडमिन", callback_data="support")
    
    markup.add(btn1, btn2, btn3, btn4)
    bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(commands=['users'])
def show_users(message):
    if str(message.chat.id) == str(ADMIN_CHAT_ID):
        subs = load_subscribers()
        if not subs:
            bot.send_message(message.chat.id, "ℹ️ सध्या एकही सबस्क्रायबर नाही.")
            return

        text = f"📊 **एकूण सबस्क्रायबर्स यादी ({len(subs)} Users):**\n\n"
        for i, (cid, data) in enumerate(subs.items(), 1):
            text += f"{i}. **{data['name']}** - `{data['phone']}` ({data['date']})\n"

        bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(commands=['broadcast'])
def broadcast_message(message):
    if str(message.chat.id) == str(ADMIN_CHAT_ID):
        msg_text = message.text.replace('/broadcast', '').strip()
        if not msg_text:
            bot.send_message(ADMIN_CHAT_ID, "⚠️ मेसेज टाईप करा. उदा: `/broadcast आज मार्केट सुट्टीमुळे बंद आहे.`", parse_mode="Markdown")
            return

        subs = load_subscribers()
        sent_count = 0
        for chat_id in subs.keys():
            try:
                bot.send_message(chat_id, f"📢 **अ‍ॅडमिन अपडेट:**\n\n{msg_text}", parse_mode="Markdown")
                sent_count += 1
                time.sleep(0.3)
            except Exception:
                continue

        bot.send_message(ADMIN_CHAT_ID, f"✅ **ब्रॉडकास्ट पूर्ण!** {sent_count} युजर्सना मेसेज पाठवला आहे.", parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    chat_id = call.message.chat.id
    
    if call.data == "scan_now":
        bot.send_message(chat_id, "⏳ *स्कॅन सुरू आहे, कृपया ३०-४० सेकंद थांबा...*", parse_mode="Markdown")
        send_scan_report(chat_id)
        
    elif call.data == "subscribe":
        markup = ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
        btn = KeyboardButton("📱 मोबाईल नंबर शेअर करा", request_contact=True)
        markup.add(btn)
        
        bot.send_message(
            chat_id, 
            "⏰ **डेली ऑटो-अलर्ट सुरू करण्यासाठी खालील बटनावर क्लिक करून तुमचा मोबाईल नंबर शेअर करा:**", 
            parse_mode="Markdown", 
            reply_markup=markup
        )
        
    elif call.data == "strategy":
        text = (
            "📚 *Open = Low / Open = High स्ट्रॅटेजी नियम:*\n\n"
            "🟢 **BULLISH (O=L):** Open आणि Low समान असल्यास Buy करा.\n"
            "🔴 **BEARISH (O=H):** Open आणि High समान असल्यास Sell करा."
        )
        bot.send_message(chat_id, text, parse_mode="Markdown")
        
    elif call.data == "support":
        text = f"📞 सहकार्यासाठी संपर्क करा: {ADMIN_USERNAME}"
        bot.send_message(chat_id, text, parse_mode="Markdown")

@bot.message_handler(content_types=['contact'])
def handle_contact(message):
    chat_id = message.chat.id
    phone = message.contact.phone_number
    name = message.contact.first_name

    total_users = save_subscriber(chat_id, name, phone)

    remove_kb = ReplyKeyboardRemove()
    bot.send_message(
        chat_id, 
        f"✅ **धन्यवाद {name}!**\nतुमचा नंबर (`{phone}`) यशस्वीपणे रजिस्टर झाला आहे. तुम्हाला रोज सकाळी ९:१६ वाजता ऑटो-अलर्ट मिळतील.", 
        parse_mode="Markdown", 
        reply_markup=remove_kb
    )

    admin_msg = (
        f"🎉 **नवीन सबस्क्रायबर अ‍ॅड झाला!**\n\n"
        f"• **नाव:** {name}\n"
        f"• **मोबाईल:** `{phone}`\n"
        f"• **Chat ID:** `{chat_id}`\n\n"
        f"📈 **एकूण सबस्क्रायबर्स:** {total_users}"
    )
    bot.send_message(ADMIN_CHAT_ID, admin_msg, parse_mode="Markdown")

# ==========================================
# 🚀 ६. बॉट सुरू करणे
# ==========================================
print("🤖 'Trading Alert Bot' क्लाउडवर चालू झाला आहे!")
bot.infinity_polling()
#///////////////////////////////////////////////////////////////////////////////////////////////////////
import threading
from flask import Flask

# 🌐 Render Free Web Service साठी वेब सर्व्हर
app = Flask(__name__)


@app.route("/")
def home():
  return "Trading Bot is Live 24/7!"


def run_flask():
  app.run(host="0.0.0.0", port=10000)


# ==========================================
# 🚀 बॉट आणि वेब सर्व्हर चालू करणे
# ==========================================
if __name__ == "__main__":
  # वेब सर्व्हर स्टार्ट करा
  t = threading.Thread(target=run_flask)
  t.start()

  print("🤖 'Trading Alert Bot' क्लाउडवर चालू झाला आहे!")
  bot.infinity_polling()
