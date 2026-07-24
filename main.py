# 🟢 सर्व आवश्यक लायब्ररीज
import os
import time
import datetime
import threading
from flask import Flask
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from SmartApi import SmartConnect
from apscheduler.schedulers.background import BackgroundScheduler
from supabase import create_client, Client
import pyotp

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

# 🟢 Global Alert Switch (Default: True)
AUTO_ALERTS_ENABLED = True

bot = telebot.TeleBot(TELEGRAM_TOKEN)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# 🌐 IST टाइमझोन हेल्पर्स
IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))

def get_ist_now():
    return datetime.datetime.now(IST)

# ==========================================
# ⏰ मार्केट टाइमिंग चेकर
# ==========================================
def is_market_ready_for_scan():
    """मध्यरात्री १२ ते सकाळी ९:१६ दरम्यान मॅन्युअल स्कॅन रोखण्यासाठी चेकर"""
    now_ist = get_ist_now()
    
    if now_ist.weekday() in [5, 6]:
        return False, "🏖️ **आज शनिवार/रविवार असल्यामुळे मार्केट बंद आहे.**\n\nसोमवारी सकाळी ९:१६ नंतर पुन्हा स्कॅन करा!"
    
    time_str = now_ist.strftime("%H:%M")
    
    if time_str < "09:16":
        return False, "⏰ **आजचे मार्केट अजून सुरू झालेले नाही!**\n\nमार्केट सकाळी ९:१५ ला सुरू होते.\n\nकृपया **सकाळी ९:१६ नंतर** पुन्हा स्कॅन बटणावर क्लिक करा! 📈"
        
    return True, ""

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
        today_str = get_ist_now().strftime('%Y-%m-%d')
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
# 🟢 O=L / O=H कॅशे मेमरी (Memory Cache)
# ==========================================
CACHED_OL_RESULTS = {
    "date": None,
    "interval": None,
    "bullish": None,
    "bearish": None
}

# ==========================================
# 📈 ३. स्कॅнер इंजिन - १ (Open = Low / Open = High)
# ==========================================
def get_angel_scan_results(interval="FIVE_MINUTE", from_time="09:15", to_time="09:20", force_refresh=False):
    global CACHED_OL_RESULTS
    
    today_str = get_ist_now().strftime('%Y-%m-%d')
    
    if not force_refresh and CACHED_OL_RESULTS["date"] == today_str and CACHED_OL_RESULTS["interval"] == "FIVE_MINUTE":
        if CACHED_OL_RESULTS["bullish"] is not None:
            print("⚡ [Cache Used] सेव्ह केलेला ५-मिनिटांचा डेटा वापरत आहे...")
            return CACHED_OL_RESULTS["bullish"], CACHED_OL_RESULTS["bearish"]

    print("🌐 [API Live Fetch] सर्व्हरवरून नवीन डेटा आणत आहे...")
    obj = SmartConnect(api_key=ANGEL_API_KEY)
    try:
        totp = pyotp.TOTP(ANGEL_TOTP_KEY).now() if ANGEL_TOTP_KEY else ""
        login_data = obj.generateSession(ANGEL_CLIENT_ID, ANGEL_PASSWORD, totp)
        if not (login_data and login_data.get('status')):
            return None, None
    except Exception:
        return None, None

    NIFTY_STOCKS_ANGEL = {
        'HDFCBANK': '1333', 'ICICIBANK': '4963', 'AXISBANK': '5900', 'SBIN': '3045', 
        'KOTAKBANK': '1922', 'INDUSINDBK': '5258', 'AUBANK': '21238', 'BANDHANBNK': '2263', 
        'FEDERALBNK': '1023', 'IDFCFIRSTB': '11184', 'PNB': '10666', 'BOB': '4668',
        'RELIANCE': '2885', 'INFY': '1594', 'TCS': '11536', 'ITC': '1660', 'LT': '11483', 
        'BHARTIARTL': '10604', 'TATAMOTORS': '3456', 'M&M': '2031', 'NTPC': '11630', 
        'TITAN': '3506', 'HCLTECH': '7229', 'SUNPHARMA': '3351', 'MARUTI': '10999', 
        'ULTRACEMCO': '11532', 'ASIANPAINT': '236', 'BAJFINANCE': '317', 'BAJAJFINSV': '16675', 
        'HINDUNILVR': '1394', 'WIPRO': '3787', 'TATASTEEL': '3499', 'POWERGRID': '14977', 
        'BAJAJ-AUTO': '16669', 'TECHM': '13538', 'HINDALCO': '1363', 'GRASIM': '1232', 
        'ONGC': '2475', 'ADANIENT': '25', 'ADANIPORTS': '15083', 'COALINDIA': '20374', 
        'BPCL': '526', 'BRITANNIA': '547', 'DRREDDY': '881', 'EICHERMOT': '910', 
        'DIVISLAB': '10940', 'APOLLOHOSP': '157', 'HEROMOTOCO': '1348', 'CIPLA': '694', 
        'HDFCLIFE': '467', 'SBILIFE': '21808', 'TATACONSUM': '3432', 'JSWSTEEL': '11723'
    }

    from_date_time = f"{today_str} {from_time}"
    to_date_time = f"{today_str} {to_time}"

    bullish_stocks = []
    bearish_stocks = []

    for symbol, token in NIFTY_STOCKS_ANGEL.items():
        try:
            time.sleep(0.4)
            historicParam = {
                "exchange": "NSE",
                "symboltoken": token,
                "interval": interval,
                "fromdate": from_date_time,
                "todate": to_date_time
            }
            resp = obj.getCandleData(historicParam)
            if not resp or 'data' not in resp or not resp['data']:
                continue
                
            candle = resp['data'][0]
            open_p = round(float(candle[1]), 2)
            high_p = round(float(candle[2]), 2)
            low_p = round(float(candle[3]), 2)

            if open_p == low_p:
                bullish_stocks.append({'symbol': symbol, 'open': open_p, 'high': high_p, 'low': low_p})
            elif open_p == high_p:
                bearish_stocks.append({'symbol': symbol, 'open': open_p, 'high': high_p, 'low': low_p})
        except Exception:
            continue

    if interval == "FIVE_MINUTE":
        CACHED_OL_RESULTS["date"] = today_str
        CACHED_OL_RESULTS["interval"] = "FIVE_MINUTE"
        CACHED_OL_RESULTS["bullish"] = bullish_stocks
        CACHED_OL_RESULTS["bearish"] = bearish_stocks

    return bullish_stocks, bearish_stocks

# 🟢 रिपोर्टींग फंक्शन
def send_scan_report(chat_id, force_refresh=False):
    now_ist = get_ist_now()
    now_time = now_ist.strftime("%H:%M")

    if now_time < "09:21":
        bullish, bearish = get_angel_scan_results(interval="ONE_MINUTE", from_time="09:15", to_time="09:16", force_refresh=force_refresh)
        time_title = "१-मिनिट कॅन्डल"
    else:
        bullish, bearish = get_angel_scan_results(interval="FIVE_MINUTE", from_time="09:15", to_time="09:20", force_refresh=force_refresh)
        time_title = "५-मिनिट कॅन्डल"
    
    if bullish is None:
        bot.send_message(chat_id, "❌ मार्केट सर्व्हरशी संपर्क होऊ शकला नाही. कृपया थोड्या वेळाने प्रयत्न करा.")
        return

    refresh_markup = InlineKeyboardMarkup()
    btn_ref = InlineKeyboardButton("🔄 ताजे रिफ्रेश स्कॅन करा", callback_data="force_scan_now")
    refresh_markup.add(btn_ref)

    if bullish:
        msg_bullish = f"🟢 **BULLISH STOCKS (Open = Low)** 🟢\n🕒 {time_title} | *Total: {len(bullish)} Stocks*\n\n"
        for item in bullish:
            msg_bullish += f"🚀 **{item['symbol']}** (O/L: ₹{item['open']:.2f} | H: ₹{item['high']:.2f})\n"
        bot.send_message(chat_id, msg_bullish, parse_mode="Markdown", reply_markup=refresh_markup)
    else:
        bot.send_message(chat_id, f"🟢 **BULLISH:** आज एकही परफेक्ट O=L स्टॉक सापडला नाही ({time_title}).", parse_mode="Markdown", reply_markup=refresh_markup)

    if bearish:
        msg_bearish = f"🔴 **BEARISH STOCKS (Open = High)** 🔴\n🕒 {time_title} | *Total: {len(bearish)} Stocks*\n\n"
        for item in bearish:
            msg_bearish += f"🩸 **{item['symbol']}** (O/H: ₹{item['open']:.2f} | L: ₹{item['low']:.2f})\n"
        bot.send_message(chat_id, msg_bearish, parse_mode="Markdown", reply_markup=refresh_markup)
    else:
        bot.send_message(chat_id, f"🔴 **BEARISH:** आज एकही परफेक्ट O=H स्टॉक सापडला नाही ({time_title}).", parse_mode="Markdown", reply_markup=refresh_markup)

# ==========================================
# 🧠 ७. स्कॅनर इंजिन - २ (Setup 2 - 50% Body Rule)
# ==========================================
def scan_setup_2():
    obj = SmartConnect(api_key=ANGEL_API_KEY)
    try:
        totp = pyotp.TOTP(ANGEL_TOTP_KEY).now() if ANGEL_TOTP_KEY else ""
        login_data = obj.generateSession(ANGEL_CLIENT_ID, ANGEL_PASSWORD, totp)
        if not (login_data and login_data.get('status')):
            return "❌ सर्व्हर कनेक्टिव्हिटी एरर"
    except Exception:
        return "❌ सर्व्हर कनेक्टिव्हिटी एरर"

    WATCHLIST = {
        'NIFTY 50': '26000', 
        'BANKNIFTY': '26009',
        'HDFCBANK': '1333', 'ICICIBANK': '4963', 'AXISBANK': '5900', 'SBIN': '3045', 
        'KOTAKBANK': '1922', 'INDUSINDBK': '5258', 'AUBANK': '21238', 'BANDHANBNK': '2263', 
        'FEDERALBNK': '1023', 'IDFCFIRSTB': '11184', 'PNB': '10666', 'BOB': '4668',
        'RELIANCE': '2885', 'INFY': '1594', 'TCS': '11536', 'ITC': '1660', 'LT': '11483', 
        'BHARTIARTL': '10604', 'TATAMOTORS': '3456', 'M&M': '2031', 'NTPC': '11630', 
        'TITAN': '3506', 'HCLTECH': '7229', 'SUNPHARMA': '3351', 'MARUTI': '10999', 
        'ULTRACEMCO': '11532', 'ASIANPAINT': '236', 'BAJFINANCE': '317', 'BAJAJFINSV': '16675', 
        'HINDUNILVR': '1394', 'WIPRO': '3787', 'TATASTEEL': '3499', 'POWERGRID': '14977', 
        'BAJAJ-AUTO': '16669', 'TECHM': '13538', 'HINDALCO': '1363', 'GRASIM': '1232', 
        'ONGC': '2475', 'ADANIENT': '25', 'ADANIPORTS': '15083', 'COALINDIA': '20374', 
        'BPCL': '526', 'BRITANNIA': '547', 'DRREDDY': '881', 'EICHERMOT': '910', 
        'DIVISLAB': '10940', 'APOLLOHOSP': '157', 'HEROMOTOCO': '1348', 'CIPLA': '694', 
        'HDFCLIFE': '467', 'SBILIFE': '21808', 'TATACONSUM': '3432', 'JSWSTEEL': '11723'
    }

    now_ist = get_ist_now()
    today_str = now_ist.strftime('%Y-%m-%d')
    now_time = now_ist.strftime('%H:%M')
    
    from_date_time = f"{today_str} 09:15"
    to_date_time = f"{today_str} {now_time}"

    report_text = f"🔥 **Setup 2 (50% Rule) - Live Radar** 🔥\n🕒 Timeframe: 5 Min\n\n"
    found_setups = 0

    for symbol, token in WATCHLIST.items():
        try:
            time.sleep(0.4)

            historicParam = {
                "exchange": "NSE",
                "symboltoken": token,
                "interval": "FIVE_MINUTE",
                "fromdate": from_date_time,
                "todate": to_date_time
            }
            resp = obj.getCandleData(historicParam)
            if not resp or 'data' not in resp or len(resp['data']) < 2:
                continue
            
            data = resp['data']
            
            f_candle = data[0]
            f_open, f_high, f_low, f_close = round(float(f_candle[1]), 2), round(float(f_candle[2]), 2), round(float(f_candle[3]), 2), round(float(f_candle[4]), 2)
            
            f_range = f_high - f_low
            if f_range <= 0:
                continue

            f_mid = f_low + (f_range * 0.50)
            
            is_bullish_first = f_close >= f_open
            is_bearish_first = f_close < f_open
            
            setup_active = True
            daily_signal_fired = False
            inside_count = 0
            trigger_high = f_high
            trigger_low = f_low
            
            stock_status = ""

            for i in range(1, len(data)):
                c_candle = data[i]
                c_time = c_candle[0].split("T")[1][:5]
                c_open, c_high, c_low, c_close = round(float(c_candle[1]), 2), round(float(c_candle[2]), 2), round(float(c_candle[3]), 2), round(float(c_candle[4]), 2)
                
                # १. जर आधीच READY अलर्ट बनला असेल, तर हाय किंवा लो ब्रेक तपासणे
                if setup_active and inside_count >= 1:
                    if is_bullish_first and c_high > trigger_high:
                        stock_status = f"🚀 **BUY Triggered** @ {c_time} (> ₹{trigger_high:.2f})"
                        daily_signal_fired = True
                        break
                    elif is_bearish_first and c_low < trigger_low:
                        stock_status = f"🩸 **SELL Triggered** @ {c_time} (< ₹{trigger_low:.2f})"
                        daily_signal_fired = True
                        break

                if not setup_active:
                    continue

                # २. ५०% झोनमधील इनसाईड कॅन्डल तपासणे
                body_max = max(c_open, c_close)
                body_min = min(c_open, c_close)
                
                body_in_upper_half = (body_min >= f_mid)
                body_in_lower_half = (body_max <= f_mid)
                
                is_inside_valid = (is_bullish_first and body_in_upper_half) or (is_bearish_first and body_in_lower_half)
                
                if is_inside_valid:
                    inside_count += 1
                    trigger_high = max(trigger_high, c_high)
                    trigger_low = min(trigger_low, c_low)
                    stock_status = f"⚠️ **READY** @ {c_time} (Watch H: ₹{trigger_high:.2f} / L: ₹{trigger_low:.2f})"
                else:
                    if inside_count >= 1 and not daily_signal_fired:
                        stock_status = f"❌ **Setup Cancelled** @ {c_time} (50% Zone Break)"
                    setup_active = False

            if stock_status != "":
                report_text += f"🔸 **{symbol}:** {stock_status}\n"
                found_setups += 1
            
        except Exception:
            continue
            
    if found_setups == 0:
        report_text += "⚪ सध्या कोणत्याही स्टॉकमध्ये 'Setup 2' बनलेला नाही."
        
    return report_text

# ==========================================
# ⏰ ४. ऑटो-अलर्ट शेड्यूलर (सकाळी ९:१६ आणि ९:२१)
# ==========================================
def send_auto_scan_job(title_prefix, interval_type, from_t, to_t):
    global AUTO_ALERTS_ENABLED
    
    if not AUTO_ALERTS_ENABLED:
        bot.send_message(ADMIN_CHAT_ID, f"⏸️ **[Auto Scan Skipped]** ऑटो-अलर्ट्स अ‍ॅडमिनने बंद ठेवले आहेत.")
        return

    subs = load_subscribers()
    if not subs:
        return

    bullish, bearish = get_angel_scan_results(interval=interval_type, from_time=from_t, to_time=to_t)
    if bullish is None:
        bot.send_message(ADMIN_CHAT_ID, f"❌ **[{title_prefix} Error]** मार्केट डेटा फेच करू शकलो नाही.")
        return

    msg_bullish = f"⏰ **{title_prefix} 📊**\n\n🟢 **BULLISH (Open = Low) - {len(bullish)} Stocks:**\n"
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

    sent_count = 0
    for chat_id in subs.keys():
        try:
            bot.send_message(chat_id, full_report, parse_mode="Markdown")
            sent_count += 1
            time.sleep(0.3)
        except Exception:
            continue

    bot.send_message(ADMIN_CHAT_ID, f"✅ **[{title_prefix} Complete]** {sent_count} सबस्क्रायबर्सना अलर्ट पाठवला!")

def scan_916_early():
    send_auto_scan_job("⚡ फास्ट ऑटो-अलर्ट (१-मिनिट O=L)", "ONE_MINUTE", "09:15", "09:16")

def scan_921_confirmed():
    send_auto_scan_job("📊 ५-मिनिट ऑटो-अलर्ट (५-मिनिट O=L)", "FIVE_MINUTE", "09:15", "09:20")

# 🟢 Scheduler Setup
scheduler = BackgroundScheduler(timezone="Asia/Kolkata")
scheduler.add_job(scan_916_early, 'cron', day_of_week='mon-fri', hour=9, minute=16, second=15)
scheduler.add_job(scan_921_confirmed, 'cron', day_of_week='mon-fri', hour=9, minute=21, second=15)
scheduler.start()

# ==========================================
# 🤖 ५. टेलिग्राम कमांड्स व अ‍ॅडमिन कस्टमायझेशन
# ==========================================
def get_main_keyboard():
    markup = InlineKeyboardMarkup()
    markup.row_width = 2
    btn1 = InlineKeyboardButton("📊 आत्ता स्कॅन करा (O=L)", callback_data="scan_now")
    btn5 = InlineKeyboardButton("🔥 Setup 2 (50% Rule)", callback_data="setup_2")
    btn2 = InlineKeyboardButton("⏰ डेली ऑटो-अलर्ट", callback_data="subscribe")
    btn3 = InlineKeyboardButton("📈 स्ट्रॅटेजी माहिती", callback_data="strategy")
    btn4 = InlineKeyboardButton("📞 सपोर्ट / ॲडमिन", callback_data="support")
    
    markup.add(btn1, btn5)
    markup.add(btn2, btn3)
    markup.add(btn4)
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_text = (
        "👋 *स्वागत आहे!* 🚀\n\n"
        "मी तुमचा वैयक्तिक **Trading Alert Bot** आहे.\n"
        "खालील पर्यायांपैकी एक निवडा:"
    )
    bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown", reply_markup=get_main_keyboard())

@bot.message_handler(commands=['alerts_off'])
def disable_alerts(message):
    global AUTO_ALERTS_ENABLED
    if str(message.chat.id) == str(ADMIN_CHAT_ID):
        AUTO_ALERTS_ENABLED = False
        bot.send_message(ADMIN_CHAT_ID, "🔴 **ऑटो-अलर्ट्स यशस्वीपणे बंद (DISABLED) केले आहेत!**")

@bot.message_handler(commands=['alerts_on'])
def enable_alerts(message):
    global AUTO_ALERTS_ENABLED
    if str(message.chat.id) == str(ADMIN_CHAT_ID):
        AUTO_ALERTS_ENABLED = True
        bot.send_message(ADMIN_CHAT_ID, "🟢 **ऑटो-अलर्ट्स यशस्वीपणे सुरू (ENABLED) केले आहेत!**")

@bot.message_handler(commands=['users'])
def show_users(message):
    if str(message.chat.id) == str(ADMIN_CHAT_ID):
        subs = load_subscribers()
        if not subs:
            bot.send_message(message.chat.id, "ℹ️ सध्या एकही सबस्क्रायबर नाही.")
            return

        status_str = "🟢 चालू (ACTIVE)" if AUTO_ALERTS_ENABLED else "🔴 बंद (DISABLED)"
        text = f"📊 **एकूण सबस्क्रायबर्स यादी ({len(subs)} Users):**\n"
        text += f"🔔 **ऑटो-अलर्ट स्टेटस:** {status_str}\n\n"
        for i, (cid, data) in enumerate(subs.items(), 1):
            text += f"{i}. **{data['name']}** - `{data['phone']}` ({data['date']})\n"

        bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(commands=['broadcast'])
def broadcast_message(message):
    if str(message.chat.id) == str(ADMIN_CHAT_ID):
        msg_text = message.text.replace('/broadcast', '').strip()
        if not msg_text:
            bot.send_message(ADMIN_CHAT_ID, "⚠️ मेसेज टाईप करा. उदा: `/broadcast आज मार्केट बंद आहे.`", parse_mode="Markdown")
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

        bot.send_message(ADMIN_CHAT_ID, f"✅ **ब्रॉडकास्ट पूर्ण!** {sent_count} युजर्सना मेसेज पाठवला.", parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    chat_id = call.message.chat.id
    
    if call.data == "scan_now":
        is_ready, alert_msg = is_market_ready_for_scan()
        if not is_ready:
            bot.send_message(chat_id, alert_msg, parse_mode="Markdown")
            return
            
        bot.send_message(chat_id, "⏳ *O=L/O=H स्कॅन सुरू आहे, कृपया थांबा...*", parse_mode="Markdown")
        send_scan_report(chat_id)
        
    elif call.data == "force_scan_now":
        is_ready, alert_msg = is_market_ready_for_scan()
        if not is_ready:
            bot.send_message(chat_id, alert_msg, parse_mode="Markdown")
            return

        bot.send_message(chat_id, "🔄 *ताजा (Fresh Live) डेटा मागवत आहे... कृपया ३० सेकंद थांबा...*", parse_mode="Markdown")
        send_scan_report(chat_id, force_refresh=True)

    elif call.data == "setup_2":
        is_ready, alert_msg = is_market_ready_for_scan()
        if not is_ready:
            bot.send_message(chat_id, alert_msg, parse_mode="Markdown")
            return

        bot.send_message(chat_id, "🔍 *Setup 2 स्कॅन करत आहे (Nifty, BankNifty & Stocks)... कृपया १५-२० सेकंद थांबा...*", parse_mode="Markdown")
        setup2_result = scan_setup_2()
        bot.send_message(chat_id, setup2_result, parse_mode="Markdown")
        
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
            "📚 *आपल्या स्ट्रॅटेजीज:*\n\n"
            "🟢 **O=L / O=H:** Open आणि Low समान असल्यास Buy, High समान असल्यास Sell.\n\n"
            "🔥 **Setup 2 (Pro):** पहिल्या ५-मिनिट कॅन्डलच्या ५०% झोनमध्ये दुसरी कॅन्डल क्लोज झाली की **'READY'** अलर्ट मिळतो. आणि त्याचा हाय/लो ब्रेक झाला की **'BUY/SELL'** सिग्नल!"
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
        f"✅ **धन्यवाद {name}!**\nतुमचा नंबर (`{phone}`) यशस्वीपणे रजिस्टर झाला आहे. तुम्हाला रोज सकाळी ९:१६ आणि ९:२१ वाजता ऑटो-अलर्ट मिळतील.", 
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

@bot.message_handler(func=lambda message: True)
def handle_all_other_messages(message):
    chat_id = message.chat.id
    first_name = message.from_user.first_name if message.from_user.first_name else "मित्र"

    text = (
        f"नमस्कार **{first_name}**! 🙏\n\n"
        "मी तुमचा **Trading Alert Bot** आहे. मदत हवी असल्यास खालील बटणांवर क्लिक करा:"
    )

    bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=get_main_keyboard())

# ==========================================
# 🚀 ६. Flask Web Server & Bot Start
# ==========================================
app = Flask(__name__)

@app.route("/")
def home():
    return "Trading Bot is Live & Active 24/7!"

def run_bot():
    print("🤖 टेलिग्राम बॉट सुरू होत आहे...")
    try:
        bot.infinity_polling(timeout=10, long_polling_timeout=5)
    except Exception as e:
        print("Bot Polling Error:", e)

if __name__ == "__main__":
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()

    port = int(os.environ.get("PORT", 10000))
    print(f"🌐 Flask वेब सर्व्हर पोर्ट {port} वर सुरू होत आहे...")
    app.run(host="0.0.0.0", port=port)
