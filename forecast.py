import os
import pandas as pd
import requests
from prophet import Prophet
import matplotlib.pyplot as plt
from datetime import datetime

# 🔹 Load environment variables (make sure .env has SLACK_WEBHOOK_URL)
from dotenv import load_dotenv
load_dotenv()

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "").strip()
HISTORY_FILE = "news_history.csv"


# ========= SLACK ALERTS =========
def send_slack_alert(message: str):
    """Send alert message to Slack channel."""
    if not SLACK_WEBHOOK_URL:
        print("⚠️ Slack webhook not configured. Skipping alert.")
        return
    try:
        payload = {"text": message}
        requests.post(SLACK_WEBHOOK_URL, json=payload)
        print(f"✅ Sent alert: {message}")
    except Exception as e:
        print("⚠️ Slack error:", e)


# ========= LOAD & PREPARE DATA =========
def load_history():
    if not os.path.exists(HISTORY_FILE):
        print("⚠️ No history file found. Run main.py first and search news.")
        return None

    df = pd.read_csv(HISTORY_FILE)

    # Fix date column
    df["Time"] = pd.to_datetime(df["Time"], errors="coerce")
    df = df.dropna(subset=["Time"])

    # Group by day
    df_daily = df.groupby(df["Time"].dt.date).size().reset_index(name="count")
    df_daily.columns = ["ds", "y"]

    return df_daily


# ========= FORECAST & DETECTION =========
def run_forecast(df_daily):
    model = Prophet()
    model.fit(df_daily)

    # Predict next 7 days
    future = model.make_future_dataframe(periods=7)
    forecast = model.predict(future)

    # Plot forecast
    model.plot(forecast)
    plt.title("📈 News Trend Forecast")
    plt.show()

    return forecast


def detect_spikes(df_daily):
    """Check if latest day has a spike in news volume."""
    if len(df_daily) < 2:
        return None

    latest_day = df_daily.iloc[-1]["y"]
    avg = df_daily["y"].mean()

    if latest_day > avg * 1.5:  # 50% spike
        msg = f"🚨 ALERT: News volume spike detected! ({latest_day} vs avg {avg:.2f})"
        send_slack_alert(msg)
        return msg
    else:
        print("✅ No unusual spike detected.")
        return None


# ========= MAIN =========
def main():
    df_daily = load_history()
    if df_daily is None or df_daily.empty:
        return

    print("✅ Loaded history data:", df_daily.tail())

    # Run forecast
    forecast = run_forecast(df_daily)

    # Detect spikes
    detect_spikes(df_daily)


if __name__ == "__main__":
    main()
