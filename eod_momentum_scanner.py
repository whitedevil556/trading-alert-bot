# ==========================================
# 🎯 eod_momentum_scanner.py (Institutional EOD Squeeze Bot)
# ==========================================
import time
import datetime
from SmartApi import SmartConnect
import pyotp

# 🌐 IST टाइमझोन हेल्पर्स
IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))

def get_ist_now():
    return datetime.datetime.now(IST)

# 🔁 API डेटा री-ट्राय हँडलर
def fetch_candle_data(obj, historicParam, retries=3):
    for attempt in range(retries):
        try:
            resp = obj.getCandleData(historicParam)
            if resp and isinstance(resp, dict) and resp.get('status') is True and 'data' in resp and resp['data']:
                return resp['data']
            elif resp and resp.get('errorcode') == 'AB1021':
                time.sleep(1.0)
                continue
        except Exception:
            pass
        time.sleep(0.35)
    return None

# 📊 200 EMA कॅल्क्युलेटर (Pure Python - No Pandas needed)
def calculate_ema(prices, period=200):
    if not prices or len(prices) < period:
        return [0] * len(prices)
    ema = []
    multiplier = 2 / (period + 1)
    sma = sum(prices[:period]) / period
    for i, p in enumerate(prices):
        if i < period - 1:
            ema.append(0)
        elif i == period - 1:
            ema.append(sma)
        else:
            ema.append((p - ema[-1]) * multiplier + ema[-1])
    return ema

# 🚀 मुख्य स्कॅनर फंक्शन
def get_eod_momentum_stocks(api_key, client_id, password, totp_key):
    obj = SmartConnect(api_key=api_key)
    try:
        totp = pyotp.TOTP(totp_key).now() if totp_key else ""
        login_data = obj.generateSession(client_id, password, totp)
        if not (login_data and login_data.get('status')):
            return "❌ एंजेल वन सर्व्हर कनेक्टिव्हिटी एरर!"
    except Exception:
        return "❌ एंजेल वन लॉगिन एरर!"

    WATCHLIST = {
        'RELIANCE': '2885', 'HDFCBANK': '1333', 'ICICIBANK': '4963', 'INFY': '1594',
        'TCS': '11536', 'ITC': '1660', 'LT': '11483', 'AXISBANK': '5900',
        'SBIN': '3045', 'BHARTIARTL': '10604', 'KOTAKBANK': '1922', 'TATAMOTORS': '3456',
        'M&M': '2031', 'NTPC': '11630', 'TITAN': '3506', 'SUNPHARMA': '3351',
        'MARUTI': '10999', 'ULTRACEMCO': '11532', 'ASIANPAINT': '236', 'BAJFINANCE': '317',
        'TATASTEEL': '3499', 'WIPRO': '3787', 'ADANIENT': '25', 'HCLTECH': '7229',
        'BAJAJ-AUTO': '16669', 'POWERGRID': '14977', 'ONGC': '2475', 'COALINDIA': '20374'
        # तुम्ही इथे हवे तेवढे ५० स्टॉक्स ॲड करू शकता
    }

    now = get_ist_now()
    # 5-Min डेटासाठी मागचे ४ दिवस (200 EMA कॅल्क्युलेट करण्यासाठी)
    from_date_5m = (now - datetime.timedelta(days=6)).strftime('%Y-%m-%d 09:15')
    # Daily डेटासाठी मागचे १५ दिवस (NR7 कॅल्क्युलेट करण्यासाठी)
    from_date_1d = (now - datetime.timedelta(days=20)).strftime('%Y-%m-%d 09:15')
    to_date = now.strftime('%Y-%m-%d 15:30')

    bullish_list = []
    bearish_list = []
    watch_list = []

    for symbol, token in WATCHLIST.items():
        try:
            # १. Daily Data फेच करणे
            param_1d = {"exchange": "NSE", "symboltoken": token, "interval": "ONE_DAY", "fromdate": from_date_1d, "todate": to_date}
            daily_candles = fetch_candle_data(obj, param_1d)
            if not daily_candles or len(daily_candles) < 8:
                continue
            
            # २. 5-Min Data फेच करणे
            param_5m = {"exchange": "NSE", "symboltoken": token, "interval": "FIVE_MINUTE", "fromdate": from_date_5m, "todate": to_date}
            candles_5m = fetch_candle_data(obj, param_5m)
            if not candles_5m or len(candles_5m) < 200:
                continue

            # === DAILY LOGIC ===
            prev_cndl = daily_candles[-2]
            curr_cndl = daily_candles[-1]
            actual_today_str = curr_cndl[0][:10] # हे वीकेंडला आपोआप शुक्रवारचा डेटा घेईल
            
            curr_O, curr_H, curr_L, curr_C = float(curr_cndl[1]), float(curr_cndl[2]), float(curr_cndl[3]), float(curr_cndl[4])
            prev_H, prev_L = float(prev_cndl[2]), float(prev_cndl[3])
            curr_range = curr_H - curr_L

            if curr_range <= 0: continue

            # NR7 Logic
            last_7_ranges = [(float(c[2]) - float(c[3])) for c in daily_candles[-7:]]
            is_nr7 = (curr_range == min(last_7_ranges))

            # Inside Day Sweep
            is_inside_day = (curr_O <= prev_H) and (curr_C >= prev_L)
            is_sweep_trap = is_inside_day and (curr_H > prev_H or curr_L < prev_L)

            # Tomorrow CPR
            pivot = (curr_H + curr_L + curr_C) / 3
            bc = (curr_H + curr_L) / 2
            tc = (pivot - bc) + pivot
            cpr_width = abs(tc - bc) / pivot * 100
            is_narrow_cpr = (cpr_width <= 0.25)

            # Power Close (Top/Bottom 20%)
            is_bullish_close = curr_C >= curr_L + (curr_range * 0.8)
            is_bearish_close = curr_C <= curr_L + (curr_range * 0.2)

            # === 5-MIN LOGIC ===
            today_5m = [c for c in candles_5m if actual_today_str in c[0]]
            if len(today_5m) < 30: continue

            # 1st 5-Min & 15-Min Hold Logic
            c1_H, c1_L = float(today_5m[0][2]), float(today_5m[0][3])
            m15_H = max(float(c[2]) for c in today_5m[:3])
            m15_L = min(float(c[3]) for c in today_5m[:3])
            last_C = float(today_5m[-1][4])

            out_5m_count = sum(1 for c in today_5m if float(c[4]) > c1_H or float(c[4]) < c1_L)
            out_15m_count = sum(1 for c in today_5m if float(c[4]) > m15_H or float(c[4]) < m15_L)

            is_5m_hold = (out_5m_count <= 4) and (c1_L <= last_C <= c1_H)
            is_15m_hold = (out_15m_count <= 4) and (m15_L <= last_C <= m15_H)

            # Half-Day Squeeze (Last 37 candles ~ 12:25 PM onwards)
            half_day_candles = today_5m[-37:] if len(today_5m) >= 37 else today_5m
            hd_H = max(float(c[2]) for c in half_day_candles)
            hd_L = min(float(c[3]) for c in half_day_candles)
            is_half_day_sqz = (((hd_H - hd_L) / hd_L) * 100) < 0.8

            # 200 EMA Hugging
            closes_5m = [float(c[4]) for c in candles_5m]
            emas = calculate_ema(closes_5m, 200)
            today_emas = emas[-len(today_5m):]
            
            near_ema_list = [1 if abs(float(c[4]) - e)/e < 0.002 else 0 for c, e in zip(today_5m, today_emas)]
            ema_full = sum(near_ema_list) >= 12
            ema_half = sum(near_ema_list[-37:]) >= 6
            ema_30m = sum(near_ema_list[-6:]) >= 2

            # === SCORING SYSTEM (Max 10 Points) ===
            score = 0
            if is_nr7: score += 2
            if is_inside_day: score += 2
            
            if ema_full: score += 3
            elif ema_half: score += 2
            elif ema_30m: score += 1
            
            if is_5m_hold: score += 1
            if is_15m_hold: score += 1
            if is_half_day_sqz: score += 1

            # === SELECTION FILTER ===
            if score >= 4:
                flags = []
                if is_narrow_cpr: flags.append("🚆 Express CPR")
                if is_sweep_trap: flags.append("🚨 Op-Trap (Sweep)")
                if ema_full: flags.append("🎯 VWAP/EMA Hug")
                
                flag_str = " | ".join(flags) if flags else "⚡ Pure Squeeze"
                
                stock_text = f"**{symbol}** (Score: {score}/10)\n↳ 📌 *Flags:* {flag_str}"
                
                if is_bullish_close:
                    bullish_list.append(stock_text)
                elif is_bearish_close:
                    bearish_list.append(stock_text)
                else:
                    watch_list.append(stock_text)
                    
        except Exception:
            continue

    # === GENERATE TELEGRAM REPORT ===
    report = f"🏦 **SMART MONEY WATCHLIST** 🏦\n*(Next Trading Day Jackpot)*\n───────────────────\n\n"
    
    found = False
    if bullish_list:
        report += "🟢 **BULLISH MOMENTUM (Buy Focus):**\n" + "\n\n".join(bullish_list) + "\n\n"
        found = True
    if bearish_list:
        report += "🔴 **BEARISH MOMENTUM (Sell Focus):**\n" + "\n\n".join(bearish_list) + "\n\n"
        found = True
    if watch_list:
        report += "⚪ **SIDEWAYS SQUEEZE (Wait & Watch):**\n" + "\n\n".join(watch_list) + "\n\n"
        found = True
        
    if not found:
        report += "⚪ उद्यासाठी कोणताही परफेक्ट इन्स्टिट्यूशनल सेटअप मिळालेला नाही. (Market is noisy)."
        
    return report
