from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
import time
import requests

# --- إعدادات تليجرام ---
TELEGRAM_BOT_TOKEN = "8303939053:AAGvQZLB8tGVPIR5LER4muufsQFBIbh3MiQ"
TELEGRAM_CHAT_ID = "6312720789"

# مسارات الملفات والذاكرة الدائمة على الهاتف
DOWNLOAD_DIR = "/storage/emulated/0/Download"
MEMORY_FILE_PATH = os.path.join(DOWNLOAD_DIR, "suspended_memory.json")


def load_persistent_memory():
  """قراءة الذاكرة السابقة من ملف على الهاتف لضمان عدم ضياعها عند إعادة التشغيل"""
  if os.path.exists(MEMORY_FILE_PATH):
    try:
      with open(MEMORY_FILE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
        return set(data)
    except Exception:
      pass
  return set()


def save_persistent_memory(coins_set):
  """حفظ الذاكرة الحالية في ملف على الهاتف بشكل دائم"""
  try:
    with open(MEMORY_FILE_PATH, "w", encoding="utf-8") as f:
      json.dump(list(coins_set), f, ensure_ascii=False)
  except Exception:
    pass


def send_telegram_alert(message):
  if TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
    return
  url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
  payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
  try:
    requests.post(url, json=payload, timeout=3)
  except Exception:
    pass


def get_market_stats():
  url = "https://api.kucoin.com/api/v1/market/allTickers"
  try:
    response = requests.get(url, timeout=5)
    data = response.json()
    stats_map = {}
    if data.get("code") == "200000":
      for ticker in data["data"].get("ticker", []):
        symbol_pair = ticker.get("symbol", "")
        if symbol_pair.endswith("-USDT"):
          base = symbol_pair.split("-")[0]
          stats_map[base] = {
              "price": float(ticker.get("last", 0) or 0),
              "change": float(ticker.get("changeRate", 0) or 0) * 100,
              "vol": float(ticker.get("vol", 0) or 0),
          }
    return stats_map
  except Exception:
    return {}


def calculate_rsi(closes, period=14):
  if len(closes) < period + 1:
    return 50.0
  gains, losses = [], []
  for i in range(1, len(closes)):
    diff = closes[i] - closes[i - 1]
    if diff >= 0:
      gains.append(diff)
      losses.append(0)
    else:
      gains.append(0)
      losses.append(abs(diff))

  avg_gain = sum(gains[:period]) / period
  avg_loss = sum(losses[:period]) / period

  for i in range(period, len(gains)):
    avg_gain = (avg_gain * (period - 1) + gains[i]) / period
    avg_loss = (avg_loss * (period - 1) + losses[i]) / period

  if avg_loss == 0:
    return 100.0
  rs = avg_gain / avg_loss
  return 100 - (100 / (1 + rs))


def calculate_mfi(candles, period=14):
  if len(candles) < period + 1:
    return 50.0
  typical_prices = []
  raw_money_flows = []

  for c in candles:
    high = float(c[3])
    low = float(c[4])
    close = float(c[2])
    vol = float(c[5])
    tp = (high + low + close) / 3
    typical_prices.append(tp)
    raw_money_flows.append(tp * vol)

  pos_flow = 0.0
  neg_flow = 0.0

  for i in range(1, min(period + 1, len(typical_prices))):
    if typical_prices[i] > typical_prices[i - 1]:
      pos_flow += raw_money_flows[i]
    elif typical_prices[i] < typical_prices[i - 1]:
      neg_flow += raw_money_flows[i]

  if neg_flow == 0:
    return 100.0
  mfi_ratio = pos_flow / neg_flow
  return 100 - (100 / (1 + mfi_ratio))


def calculate_opportunity_score_and_analytics(symbol, change):
  klines_url = (
      f"https://api.kucoin.com/api/v1/market/candles?symbol={symbol}-USDT&type=1hour"
  )
  ob_url = (
      f"https://api.kucoin.com/api/v1/market/orderbook/level2_100?symbol={symbol}-USDT"
  )

  rsi = 50.0
  mfi = 50.0
  vol_spike = 1.0
  ob_ratio = 1.0
  breakout_ready = False
  spread_ok = True

  try:
    res_k = requests.get(klines_url, timeout=3)
    data_k = res_k.json()
    if data_k.get("code") == "200000":
      candles = data_k.get("data", [])
      if candles:
        rev_candles = list(reversed(candles))
        closes = [float(c[2]) for c in rev_candles]
        volumes = [float(c[5]) for c in rev_candles]

        rsi = calculate_rsi(closes)
        mfi = calculate_mfi(rev_candles)

        if len(volumes) >= 5:
          avg_vol = sum(volumes[:-1]) / (len(volumes) - 1)
          latest_vol = volumes[-1]
          vol_spike = latest_vol / avg_vol if avg_vol > 0 else 1.0
  except Exception:
    pass

  try:
    res_ob = requests.get(ob_url, timeout=3)
    data_ob = res_ob.json()
    if data_ob.get("code") == "200000":
      ob = data_ob.get("data", {})
      bids = ob.get("bids", [])
      asks = ob.get("asks", [])

      total_bids = sum(float(b[1]) for b in bids)
      total_asks = sum(float(a[1]) for a in asks)
      if total_asks > 0:
        ob_ratio = total_bids / total_asks
      else:
        ob_ratio = 5.0

      if bids and asks:
        best_bid = float(bids[0][0])
        best_ask = float(asks[0][0])
        if best_bid > 0:
          spread_pct = ((best_ask - best_bid) / best_bid) * 100
          if spread_pct > 3.5:
            spread_ok = False

        ask_volumes = [float(a[1]) for a in asks[:15]]
        if ask_volumes and total_asks > 0:
          max_near_ask = max(ask_volumes)
          avg_ask = sum(ask_volumes) / len(ask_volumes)
          if max_near_ask < (avg_ask * 2.5) and ob_ratio > 1.2:
            breakout_ready = True
  except Exception:
    pass

  if change < -30.0 or ob_ratio < 0.3 or not spread_ok:
    return 0, rsi, mfi, vol_spike, False, "Potential ST / Risk ⚠️"

  score = 35

  if rsi <= 30:
    score += 20
  elif rsi <= 45:
    score += 10

  if mfi <= 25:
    score += 20
  elif mfi <= 45:
    score += 10

  if vol_spike >= 3.0:
    score += 15
  elif vol_spike >= 1.5:
    score += 8

  if ob_ratio >= 1.5:
    score += 10

  if breakout_ready:
    score += 15

  final_score = max(5, min(99, score))
  status_text = (
      "Ready to Breakout 🚀" if breakout_ready else "Healthy Accumulation 🟢"
  )

  return final_score, rsi, mfi, vol_spike, breakout_ready, status_text


def get_active_trading_symbols():
  url = "https://api.kucoin.com/api/v1/symbols"
  try:
    response = requests.get(url, timeout=5)
    data = response.json()
    active_coins = set()
    if data.get("code") == "200000":
      for s in data["data"]:
        base = s.get("baseCurrency")
        if base and s.get("enableTrading") is True:
          active_coins.add(base)
    return active_coins
  except Exception:
    return set()


def process_single_currency(symbol, market_stats):
  detail_url = f"https://api.kucoin.com/api/v3/currencies/{symbol}"
  try:
    res_detail = requests.get(detail_url, timeout=3)
    detail_data = res_detail.json()
  except Exception:
    return None

  if detail_data and detail_data.get("code") == "200000":
    curr_info = detail_data.get("data")
    if not curr_info:
      return None

    chains = curr_info.get("chains", [])
    if not chains:
      return None

    all_deposits_disabled = True
    any_withdraw_enabled = False
    has_valid_chain = False

    for chain in chains:
      if not chain:
        continue
      chain_name = chain.get("chainName") or chain.get("chain", "Unknown")

      if chain_name in ["BEP2", "Omni"]:
        continue

      has_valid_chain = True
      is_deposit = bool(chain.get("isDepositEnabled"))
      is_withdraw = bool(chain.get("isWithdrawEnabled"))

      if is_deposit:
        all_deposits_disabled = False
      if is_withdraw:
        any_withdraw_enabled = True

    if has_valid_chain:
      stat = market_stats.get(symbol, {})
      price = stat.get("price", 0)
      change = stat.get("change", 0)

      score, rsi, mfi, vol_spike, breakout, status_msg = (
          calculate_opportunity_score_and_analytics(symbol, change)
      )

      result_item = {
          "symbol": symbol,
          "price": price,
          "change": change,
          "score": score,
          "status": status_msg,
      }

      is_suspended_type = bool(
          all_deposits_disabled and any_withdraw_enabled
      )
      return (result_item, is_suspended_type)

  return None


def run_scan_cycle():
  print("--- Starting Persistent Memory Scan Cycle ---")

  # تحميل الذاكرة الدائمة من هاتف المستخدم
  previous_suspended_coins = load_persistent_memory()

  active_coins = get_active_trading_symbols()
  if not active_coins:
    print("Failed to fetch active markets.")
    return

  market_stats = get_market_stats()
  url_list = "https://api.kucoin.com/api/v1/currencies"

  if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

  file_suspended = os.path.join(DOWNLOAD_DIR, "kucoin_suspended_report.txt")
  file_normal = os.path.join(DOWNLOAD_DIR, "kucoin_normal_report.txt")

  try:
    response = requests.get(url_list, timeout=5)
    data = response.json()

    if data.get("code") == "200000" and "data" in data:
      currencies = data["data"]
      symbols_to_check = []

      for curr in currencies:
        symbol = curr.get("currency")
        if symbol and symbol in active_coins:
          symbols_to_check.append(symbol)

      suspended_results = []
      normal_results = []

      print(f"Scanning {len(symbols_to_check)} coins concurrently...")

      with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(
                process_single_currency, sym, market_stats
            ): sym
            for sym in symbols_to_check
        }

        for future in as_completed(futures):
          res = future.result()
          if res:
            item, is_suspended = res
            if is_suspended:
              suspended_results.append(item)
            else:
              normal_results.append(item)

      # ترتيب النتائج (الأعلى أولاً)
      suspended_results.sort(key=lambda x: x["score"], reverse=True)
      normal_results.sort(key=lambda x: x["score"], reverse=True)

      current_suspended_symbols = {item["symbol"] for item in suspended_results}

      # -------------------------------------------------------------
      # 1. إرسال تقرير الحيتان مع تمييز العملات الجديدة اعتماداً على الذاكرة الدائمة
      # -------------------------------------------------------------
      report_suspended = (
          "🚨 *تقرير الحيتان والعملات الخاصة (إيداع مغلق - الأعلى أولاً)*:\n\n"
      )
      for item in suspended_results:
        sym = item["symbol"]
        # مقارنة مع الذاكرة المحفوظة في ملف الهاتف
        is_brand_new = (
            sym not in previous_suspended_coins
            and len(previous_suspended_coins) > 0
        )
        tag = " 🔥 *[جديدة]*" if is_brand_new else ""

        report_suspended += (
            f"• `{sym}`{tag} | Score: *{item['score']}%* | السعر:"
            f" `{item['price']}` | التغير: `{item['change']:+.2f}%` | الحالة:"
            f" `{item['status']}`\n"
        )
      report_suspended += f"\n*إجمالي العملات الخاصة: {len(suspended_results)}*"

      print("Sending Suspended Coins Report...")
      send_telegram_alert(report_suspended)

      try:
        with open(file_suspended, "w", encoding="utf-8") as f:
          f.write(report_suspended)
      except Exception:
        pass

      # تحديث وحفظ الذاكرة الدائمة الجديدة في ملف الهاتف
      save_persistent_memory(current_suspended_symbols)

      time.sleep(3)

      # -------------------------------------------------------------
      # 2. إرسال تقرير السوق العادي
      # -------------------------------------------------------------
      top_normal_results = normal_results[:45]

      report_normal = (
          "🟢 *تقرير السوق العادي (إيداع مفتوح - أعلى الفرص)*:\n\n"
      )
      for item in top_normal_results:
        report_normal += (
            f"• `{item['symbol']}` | Score: *{item['score']}%* | السعر:"
            f" `{item['price']}` | التغير: `{item['change']:+.2f}%` | الحالة:"
            f" `{item['status']}`\n"
        )
      report_normal += (
          f"\n*تم عرض أعلى {len(top_normal_results)} عملة من أصل"
          f" {len(normal_results)} لضمان الاكتمال*"
      )

      full_normal_file_content = (
          "🟢 *تقرير السوق العادي (إيداع مفتوح - القائمة الكاملة)*:\n\n"
      )
      for item in normal_results:
        full_normal_file_content += (
            f"• `{item['symbol']}` | Score: *{item['score']}%* | السعر:"
            f" `{item['price']}` | التغير: `{item['change']:+.2f}%` | الحالة:"
            f" `{item['status']}`\n"
        )
      full_normal_file_content += (
          f"\n*إجمالي العملات العادية: {len(normal_results)}*"
      )

      print("Sending Normal Market Report...")
      send_telegram_alert(report_normal)

      try:
        with open(file_normal, "w", encoding="utf-8") as f:
          f.write(full_normal_file_content)
      except Exception:
        pass

      print("Scan Cycle Completed with Persistent Storage!")

  except Exception as e:
    print(f"An error occurred: {e}")


if __name__ == "__main__":
  print("--- Persistent Bot Started ---")
  while True:
    run_scan_cycle()
    print("\n[💤 Waiting 1 hour for the next scan cycle...]\n")
    time.sleep(3600)
