import os
import json
import requests
import pandas as pd
import numpy as np
import ccxt

# إعدادات تيليجرام
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_CHAT_ID")

MEMORY_FILE = "suspended_memory.json"

def send_telegram_message(message):
    if TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN":
        print("Telegram tokens not set, skipping message.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload)
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

def main():
    print("Starting KuCoin Scanner...")
    
    # تحميل الذاكرة المستدامة السابقة
    memory = load_memory()
    print(f"Loaded memory state: {memory}")

    exchange = ccxt.kucoin()
    markets = exchange.load_markets()
    print(f"Loaded {len(markets)} markets from KuCoin.")

    # محاكاة بسيطة للفحص وتحديث الذاكرة
    scan_count = memory.get("scan_count", 0) + 1
    memory["scan_count"] = scan_count
    
    # حفظ الحالة الجديدة للذاكرة
    save_memory(memory)

    # إرسال التقرير لتيليجرام
    message = f"🚀 *KuCoin Scanner* executed successfully!\n📊 Scan Iteration: `{scan_count}`\n✅ Persistent memory updated."
    send_telegram_message(message)
    print("Scanner finished successfully and memory committed.")

if __name__ == "__main__":
    main()
