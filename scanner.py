from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import time
import requests

# --- إعدادات تليجرام ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_CHAT_ID")

MEMORY_FILE = "suspended_memory.json"

def send_telegram_alert(message):
    if TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN" or not TELEGRAM_BOT_TOKEN:
        print("Telegram tokens not set, skipping message.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload, timeout=15)
        response.raise_for_status()
    except Exception as e:
        print(f"Failed to send Telegram message: {e}")

def load_memory():
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading memory: {e}")
    return {}

def save_memory(memory_data):
    try:
        with open(MEMORY_FILE, "w") as f:
            json.dump(memory_data, f, indent=4)
    except Exception as e:
        print(f"Error saving memory: {e}")

def get_market_stats():
    url = "https://api.kucoin.com/api/v1/market/allTickers"
    try:
        response = requests.get(url, timeout=15)
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
                        "vol": float(ticker.get("vol", 0) or 0)
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
    klines_url = f"https://api.kucoin.com/api/v1/market/candles?symbol={symbol}-USDT&type=1hour"
    ob_url = f"https://api.kucoin.com/api/v1/market/orderbook/level2_100?symbol={symbol}-USDT"

    rsi = 50.0
    mfi = 50.0
    vol_spike = 1.0
    ob_ratio = 1.0
    breakout_ready = False
    spread_ok = True

    try:
        res_k = requests.get(klines_url, timeout=8)
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
        res_ob = requests.get(ob_url, timeout=8)
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
    status_text = "Ready to Breakout 🚀" if breakout_ready else "Healthy Accumulation 🟢"

    return final_score, rsi, mfi, vol_spike, breakout_ready, status_text

def get_active_trading_symbols():
    url = "https://api.kucoin.com/api/v1/symbols"
    try:
        response = requests.get(url, timeout=15)
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
        res_detail = requests.get(detail_url, timeout=8)
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

            score, rsi, mfi, vol_spike, breakout, status_msg = calculate_opportunity_score_and_analytics(symbol, change)

            result_item = {
                "symbol": symbol,
                "price": price,
                "change": change,
                "score": score,
                "status": status_msg
            }

            is_suspended_type = bool(all_deposits_disabled and any_withdraw_enabled)
            return (result_item, is_suspended_type)

    return None

def main():
    print("--- Starting GitHub Actions KuCoin Scan Cycle (Optimized) ---")

    memory = load_memory()
    scan_count = memory.get("scan_count", 0) + 1
    memory["scan_count"] = scan_count
    save_memory(memory)

    active_coins = get_active_trading_symbols()
    if not active_coins:
        print("Failed to fetch active markets.")
        return

    market_stats = get_market_stats()
    url_list = "https://api.kucoin.com/api/v1/currencies"

    try:
        response = requests.get(url_list, timeout=15)
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

            print(f"Scanning {len(symbols_to_check)} coins with stable thread pacing...")

            # تقليل عدد العمليات المتوازية إلى 4 لضمان عدم ضياع أي طلب بسبب سرعة السيرفرات الزائدة
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = {executor.submit(process_single_currency, sym, market_stats): sym for sym in symbols_to_check}

                for future in as_completed(futures):
                    res = future.result()
                    if res:
                        item, is_suspended = res
                        if is_suspended:
                            suspended_results.append(item)
                        else:
                            normal_results.append(item)

            suspended_results.sort(key=lambda x: x["score"], reverse=True)
            normal_results.sort(key=lambda x: x["score"], reverse=True)

            # 1. إرسال تقرير العملات الخاصة بكامل العدد الصحيح
            if suspended_results:
                report_suspended = f"🚨 *تقرير الحيتان والعملات الخاصة (إيداع مغلق - Scan #{scan_count})*:\n\n"
                for item in suspended_results:
                    report_suspended += f"• `{item['symbol']}` | 📊 `Score: {item['score']}%` | 💰 `السعر: {item['price']}` | 📉 `التغير: {item['change']:+.2f}%` | `{item['status']}`\n"
                report_suspended += f"\n*إجمالي العملات الخاصة: {len(suspended_results)}*"
                send_telegram_alert(report_suspended)
                time.sleep(3)

            # 2. إرسال تقرير السوق العادي
            top_normal_results = normal_results[:45]
            report_normal = f"🚀 *KuCoin Scanner* - Scan Iteration: `{scan_count}`\n\n🟢 *تقرير السوق العادي (أعلى الفرص)*:\n\n"
            for item in top_normal_results:
                report_normal += f"• `{item['symbol']}` | 📊 `Score: {item['score']}%` | 💰 `السعر: {item['price']}` | 📉 `التغير: {item['change']:+.2f}%` | `{item['status']}`\n"
            report_normal += f"\n📊 تم عرض أعلى {len(top_normal_results)} عملة من أصل {len(normal_results)} سوق لضمان الاكتمال\n✅ Persistent memory updated."

            send_telegram_alert(report_normal)
            print("Scan Cycle Completed and Accurate Reports Sent Successfully!")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
