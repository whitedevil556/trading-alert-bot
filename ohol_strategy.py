# ==========================================
# 📈 ohol_strategy.py (Open = Low / Open = High Modular Logic)
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

# 🟢 O=L / O=H स्कॅनर मुख्य फंक्शन (Errorless Signature)
def get_angel_scan_results(api_key, client_id, password, totp_key, interval="FIVE_MINUTE", from_time="09:15", to_time="09:20"):
    """
    एंजेल वन API कडून O=L आणि O=H चे लाईव्ह रिझल्ट्स आणणारे फंक्शन
    """
    today_str = get_ist_now().strftime('%Y-%m-%d')
    
    obj = SmartConnect(api_key=api_key)
    try:
        totp = pyotp.TOTP(totp_key).now() if totp_key else ""
        login_data = obj.generateSession(client_id, password, totp)
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
            time.sleep(0.35)
            historicParam = {
                "exchange": "NSE",
                "symboltoken": token,
                "interval": interval,
                "fromdate": from_date_time,
                "todate": to_date_time
            }
            
            candles = fetch_candle_data_with_retry(obj, historicParam, retries=3)
            if not candles:
                continue
            
            target_candle = None
            for c in candles:
                if "09:15" in c[0]:
                    target_candle = c
                    break
            
            if not target_candle:
                target_candle = candles[0]
                
            open_p = round(float(target_candle[1]), 2)
            high_p = round(float(target_candle[2]), 2)
            low_p = round(float(target_candle[3]), 2)

            tol = max(0.10, open_p * 0.0005)

            if abs(open_p - low_p) <= tol:
                bullish_stocks.append({'symbol': symbol, 'open': open_p, 'high': high_p, 'low': low_p})
            elif abs(open_p - high_p) <= tol:
                bearish_stocks.append({'symbol': symbol, 'open': open_p, 'high': high_p, 'low': low_p})
        except Exception:
            continue

    return bullish_stocks, bearish_stocks
