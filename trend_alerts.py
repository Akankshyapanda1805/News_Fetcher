import os
import pandas as pd
import requests
from prophet import Prophet
import matplotlib.pyplot as plt
from datetime import datetime
from dotenv import load_dotenv

# -----------------------------
# Load environment variables
# -----------------------------
load_dotenv()
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "").strip()
HISTORY_FILE = "news_history.csv"

# -----------------------------
# Slack alert function
# -----------------------------
def send_slack_alert(message="🚨 Test alert from News Aggregator"):
    if not SLACK_WEBHOOK_URL:
        print("⚠️ Slack webhook not configured in .env")
        return
    
    try:
        resp = requests.post(
            SLACK_WEBHOOK_URL,
            json={"text": message},
            timeout=10
        )
        print("🔍 Slack response:", resp.status_code, resp.text)
        
        if resp.status_code == 200:
            print("✅ Slack alert sent successfully!")
        else:
            print(f"⚠️ Failed to send Slack alert: {resp.status_code}, {resp.text}")
    except Exception as e:
        print(f"⚠️ Slack exception: {e}")

# -----------------------------
# Load history function
# -----------------------------
def load_history(filename=HISTORY_FILE):
    if not os.path.exists(filename):
        print(f"⚠️ History file '{filename}' not found. Run main.py and fetch news first.")
        return None

    df = pd.read_csv(filename)

    # Ensure Time column is datetime
    df["Time"] = pd.to_datetime(df["Time"], errors="coerce")
    df = df.dropna(subset=["Time"])

    # Group by date
    df_daily = df.groupby(df["Time"].dt.date).size().reset_index(name="count")
    df_daily.columns = ["ds", "y"]

    return df_daily

# -----------------------------
# Forecast function
# -----------------------------
def run_forecast(df_daily):
    model = Prophet()
    model.fit(df_daily)

    # Predict next 7 days
    future = model.make_future_dataframe(periods=7)
    forecast = model.predict(future)

    # Plot forecast
    fig = model.plot(forecast)
    plt.title("News Trend Forecast")
    plt.show(block=True)  # Keep window open

    # Save figure
    fig.savefig("forecast.png")
    print("📈 Forecast graph saved as 'forecast.png'")

    return forecast

# -----------------------------
# Spike detection
# -----------------------------
def detect_spike(df_daily, threshold=1.5):
    """Alert if latest day's news count > threshold * average of previous days."""
    if df_daily is None or len(df_daily) < 2:
        print("⚠️ Not enough data to detect spikes.")
        return None

    latest_day = df_daily.iloc[-1]["y"]
    avg = df_daily["y"][:-1].mean()

    if latest_day > avg * threshold:
        msg = f"🚨 ALERT: News spike detected! {latest_day} articles vs avg {avg:.2f}"
        send_slack_alert(msg)
        return msg
    else:
        print(f"✅ No unusual spike. Latest={latest_day}, Avg={avg:.2f}")
        return None

# -----------------------------
# Main function
# -----------------------------
def main():
    df_daily = load_history()
    if df_daily is None or df_daily.empty:
        print("⚠️ No data available to process.")
        return

    # Test Slack alert
    send_slack_alert("🔔 Test alert: Slack integration is working!")

    # Run forecast
    forecast = run_forecast(df_daily)

    # Detect spike (50% threshold)
    detect_spike(df_daily, threshold=1.5)

# -----------------------------
# Entry point
# -----------------------------
if __name__ == "__main__":
    main()
