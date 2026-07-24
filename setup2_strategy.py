# ==========================================
# 🔥 setup2_strategy.py (Setup 2 Modular Logic)
# ==========================================
import time
import datetime
from SmartApi import SmartConnect
import pyotp

# 🌐 IST टाइमझोन हेल्पर्स
IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))

def get_ist_now():
    return datetime.datetime.now(IST)

# 🔁 API डेटा री-ट्राय व AB1021 हँडलर
def fetch_candle_data_with_retry(obj, historicParam, retries=3):
    for attempt in range(retries):
        try:
            resp = obj.getCandleData(historicParam)
            if resp and isinstance(resp, dict):
                if resp.get('status') is True and 'data' in resp and resp['data']:
                    return resp['data']
                elif resp.get('errorcode') == 'AB1021' or 'Too many requests' in str(resp.get('message')):
                    time.sleep(1.0)
                    continue
        except Exception:
            pass
        time.sleep(0.35)
    return None

# 🔥 Setup 2 मुख्य स्कॅनर फंक्शन
def scan_setup_2_logic(api_key, client_id, password, totp_key):
    """
    Setup 2 (Inside Candle Breakout) चा लाइव्ह रिपोर्ट जनरेट करणारे फंक्शन
    """
    now_ist = get_ist_now()
    today_str = now_ist.strftime('%Y-%m-%d')
    now_time = now_ist.strftime('%H:%M')

    obj = SmartConnect(api_key=api_key)
    try:
        totp = pyotp.TOTP(totp_key).now() if totp_key else ""
        login_data = obj.generateSession(client_id, password, totp)
        if not (login_data and login_data.get('status')):
            return "❌ सर्व्हर कनेक्टिव्हिटी एरर"
    except Exception:
        return "❌ सर्व्हर कनेक्टिव्हिटी एरर"

    WATCHLIST = {
        'NIFTY 50': '26000', 'BANKNIFTY': '26009',
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
    
    from_date_time = f"{today_str} 09:15"
    to_date_time = f"{today_str} {now_time}"

    buy_list, sell_list, ready_list, cancelled_list = [], [], [], []

    for symbol, token in WATCHLIST.items():
        try:
            time.sleep(0.35)
            historicParam = {
                "exchange": "NSE",
                "symboltoken": token,
                "interval": "FIVE_MINUTE",
                "fromdate": from_date_time,
                "todate": to_date_time
            }
            
            data = fetch_candle_data_with_retry(obj, historicParam, retries=3)
            if not data or len(data) < 2:
                continue
            
            f_candle = data[0]
            f_open, f_high, f_low, f_close = round(float(f_candle[1]), 2), round(float(f_candle[2]), 2), round(float(f_candle[3]), 2), round(float(f_candle[4]), 2)
            
            tol = max(0.10, f_open * 0.0005)
            is_bullish_first = (abs(f_open - f_low) <= tol)
            is_bearish_first = (abs(f_open - f_high) <= tol)
            
            if not (is_bullish_first or is_bearish_first):
                continue

            f_range = f_high - f_low
            if f_range <= 0:
                continue

            f_mid = f_low + (f_range * 0.50)
            
            setup_active = True
            daily_signal_fired = False
            inside_count = 0
            trigger_high = f_high
            trigger_low = f_low
            current_status = ""  # Safe initialization to avoid UnboundLocalError

            for i in range(1, len(data)):
                c_candle = data[i]
                c_time = c_candle[0].split("T")[1][:5]
                c_open, c_high, c_low, c_close = round(float(c_candle[1]), 2), round(float(c_candle[2]), 2), round(float(c_candle[3]), 2), round(float(c_candle[4]), 2)
                
                if setup_active and inside_count >= 1:
                    if is_bullish_first and c_high > trigger_high:
                        buy_list.append(f"🚀 **{symbol}**: BUY @ {c_time} (> ₹{trigger_high:.2f})")
                        daily_signal_fired = True
                        break
                    elif is_bearish_first and c_low < trigger_low:
                        sell_list.append(f"🩸 **{symbol}**: SELL @ {c_time} (< ₹{trigger_low:.2f})")
                        daily_signal_fired = True
                        break

                if not setup_active:
                    continue

                body_max = max(c_open, c_close)
                body_min = min(c_open, c_close)
                
                body_in_upper_half = (body_min >= f_mid)
                body_in_lower_half = (body_max <= f_mid)
                
                is_inside_valid = (is_bullish_first and body_in_upper_half) or (is_bearish_first and body_in_lower_half)
                
                if is_inside_valid:
                    inside_count += 1
                    trigger_high = max(trigger_high, c_high)
                    trigger_low = min(trigger_low, c_low)
                    current_status = f"🔸 **{symbol}**: READY @ {c_time} (H: ₹{trigger_high:.2f} / L: ₹{trigger_low:.2f})"
                else:
                    if inside_count >= 1 and not daily_signal_fired:
                        cancelled_list.append(f"❌ **{symbol}**: Cancelled @ {c_time}")
                    setup_active = False

            if setup_active and inside_count >= 1 and not daily_signal_fired and current_status:
                ready_list.append(current_status)
            
        except Exception:
            continue
            
    report_text = f"🔥 **Setup 2 - Live Radar** 🔥\n🕒 Timeframe: 5 Min\n"
    report_text += "───────────────────\n\n"

    found_any = False
    if buy_list:
        report_text += "🟢 **BUY SIGNALS** 🚀\n" + "\n".join(buy_list) + "\n\n"
        found_any = True
    if sell_list:
        report_text += "🔴 **SELL SIGNALS** 🩸\n" + "\n".join(sell_list) + "\n\n"
        found_any = True
    if ready_list:
        report_text += "⚠️ **READY STOCKS (Watch Zone)** 🎯\n" + "\n".join(ready_list) + "\n\n"
        found_any = True
    if cancelled_list:
        report_text += "❌ **CANCELLED SETUPS**\n" + "\n".join(cancelled_list) + "\n"
        found_any = True

    if not found_any:
        report_text += "⚪ सध्या कोणत्याही स्टॉकमध्ये 'Setup 2' बनलेला नाही."

    return report_text
