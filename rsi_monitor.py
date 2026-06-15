"""
Forex RSI(14) 4H Monitor - GitHub Actions version
Sends Telegram alerts for pairs with RSI > 70 (overbought) or RSI < 30 (oversold).
Uses only closed 4H candles. Twelve Data free plan compatible.
"""

import os
import time
import json
import urllib.request
import urllib.parse
import urllib.error

API_KEY = os.environ["TWELVE_DATA_API_KEY"]
TG_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TG_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

PAIRS = [
    "EUR/USD","GBP/USD","USD/JPY","AUD/USD","USD/CAD","GBP/JPY","USD/CLP","USD/CHF",
    "NZD/USD","EUR/JPY","EUR/GBP","AUD/JPY","AUD/NZD","USD/COP","AUD/CAD","EUR/AUD",
    "NZD/JPY","EUR/NZD","GBP/NZD","AUD/NOK","GBP/AUD","CAD/CHF","CAD/JPY","GBP/CHF",
    "USD/BRL","AUD/CHF","CHF/JPY","NZD/CAD","GBP/CAD","EUR/CHF","NZD/CHF","CAD/SGD",
    "USD/ZAR","USD/CNH","CHF/SGD","CAD/MXN","EUR/CNH","MXN/JPY","EUR/MXN","USD/HKD",
    "CNH/JPY","NZD/SGD","EUR/CZK","EUR/SGD","GBP/MXN","USD/SGD","EUR/ZAR","GBP/CNH",
    "NZD/CNH","GBP/SGD","NOK/JPY","USD/CZK","SGD/JPY","USD/NOK","CHF/SEK","EUR/TRY",
    "USD/DKK","USD/ILS","USD/SEK","USD/TWD","ZAR/JPY","AUD/HUF","CHF/HUF","EUR/ILS",
    "EUR/NOK","GBP/NOK","NZD/HUF","CHF/NOK","EUR/DKK","EUR/SEK","GBP/HUF","GBP/TRY",
    "USD/IDR","USD/KRW","USD/PLN","AUD/CNH","AUD/DKK","AUD/SGD","CHF/DKK","EUR/PLN",
    "GBP/DKK","GBP/SEK","USD/INR","USD/THB","AUD/PLN","CHF/PLN","NOK/SEK","PLN/JPY",
    "SEK/JPY",
]

RSI_PERIOD = 14
INTERVAL = "4h"
OUTPUT_SIZE = 30
WAIT_BETWEEN_REQUESTS_SEC = 8  # ~7.5 requests/min, under Twelve Data free limit of 8/min


def fetch_closed_candles(symbol):
    url = (
        "https://api.twelvedata.com/time_series?"
        f"symbol={urllib.parse.quote(symbol)}&interval={INTERVAL}"
        f"&outputsize={OUTPUT_SIZE}&order=ASC&apikey={API_KEY}"
    )
    with urllib.request.urlopen(url, timeout=30) as resp:
        data = json.loads(resp.read().decode())

    if data.get("status") == "error" or "code" in data:
        raise RuntimeError(data.get("message", "Erro desconhecido na API"))

    values = data.get("values")
    if not values or not isinstance(values, list):
        raise RuntimeError("Sem dados retornados")

    # Drop the last candle: it may still be open (not closed yet)
    closed = values[:-1]
    closes = [float(v["close"]) for v in closed]
    last = closed[-1]
    return closes, float(last["close"]), last["datetime"]


def calculate_rsi(closes, period=14):
    if len(closes) < period + 1:
        return None

    gains = 0.0
    losses = 0.0
    for i in range(1, period + 1):
        diff = closes[i] - closes[i - 1]
        if diff >= 0:
            gains += diff
        else:
            losses -= diff

    avg_gain = gains / period
    avg_loss = losses / period

    for i in range(period + 1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gain = diff if diff > 0 else 0.0
        loss = -diff if diff < 0 else 0.0
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = json.dumps({"chat_id": TG_CHAT_ID, "text": text}).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp.read()
    except urllib.error.HTTPError as e:
        print(f"Erro ao enviar Telegram: {e.read().decode()}")


def main():
    signals = []
    errors = []

    for i, symbol in enumerate(PAIRS):
        try:
            closes, price, candle_time = fetch_closed_candles(symbol)
            rsi = calculate_rsi(closes, RSI_PERIOD)
            if rsi is not None:
                if rsi > 70:
                    signals.append((symbol, price, rsi, "SOBRECOMPRADO \U0001F534", candle_time))
                elif rsi < 30:
                    signals.append((symbol, price, rsi, "SOBREVENDIDO \U0001F7E2", candle_time))
        except Exception as e:
            errors.append(f"{symbol}: {e}")
            print(f"Erro em {symbol}: {e}")

        if i < len(PAIRS) - 1:
            time.sleep(WAIT_BETWEEN_REQUESTS_SEC)

    if signals:
        lines = ["\U0001F4CA Forex RSI(14) 4H - Sinais ativos:", ""]
        for symbol, price, rsi, state, candle_time in signals:
            lines.append(
                f"{symbol} | Preco: {price:.5f} | RSI: {rsi:.2f} | {state} | {candle_time}"
            )
        message = "\n".join(lines)
    else:
        message = "\u2705 Forex RSI(14) 4H - Nenhum sinal de sobrecompra/sobrevenda neste ciclo."

    if errors:
        message += f"\n\n\u26A0 {len(errors)} pares com erro nesta execucao."

    print(message)
    send_telegram_message(message)


if __name__ == "__main__":
    main()
