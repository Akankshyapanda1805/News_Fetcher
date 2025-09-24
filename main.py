# main.py
import os
import tweepy
import requests
from dotenv import load_dotenv
from datetime import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pandas as pd
import re

# -------------------------
# Load environment variables
# -------------------------
load_dotenv()
HISTORY_FILE = "news_history.csv"
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "").strip()
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")
NEWSAPI_ENDPOINT = "https://newsapi.org/v2/everything"

# -------------------------
# Slack function
# -------------------------
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

# -------------------------
# Utility functions
# -------------------------
def clean_text(text):
    if not text:
        return "Unknown"
    text = re.sub(r"http\S+", "", text)
    text = re.sub(r"[@#]\w+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text.strip()

def format_datetime(date_str):
    if not date_str:
        return "Unknown"
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M:%S")
    except:
        try:
            return datetime.strptime(str(date_str), "%Y-%m-%d %H:%M:%S%z").strftime("%Y-%m-%d %H:%M:%S")
        except:
            return str(date_str)

# -------------------------
# History saving / dedupe
# -------------------------
def save_to_history(data, filename=HISTORY_FILE):
    if not data:
        return False
    try:
        df_new = pd.DataFrame(data)
        expected_cols = ["Platform", "Time", "Author", "Title", "Description", "URL"]
        for c in expected_cols:
            if c not in df_new.columns:
                df_new[c] = ""

        if os.path.exists(filename):
            df_new.to_csv(filename, mode="a", header=False, index=False, encoding="utf-8")
        else:
            df_new.to_csv(filename, index=False, encoding="utf-8")
        dedupe_history(filename)
        return True
    except Exception as e:
        print("Error saving history:", e)
        return False

def dedupe_history(filename=HISTORY_FILE):
    try:
        if not os.path.exists(filename):
            return
        df = pd.read_csv(filename, dtype=str)
        for col in ["URL", "Title", "Description"]:
            if col not in df.columns:
                df[col] = ""
        df["URL"] = df["URL"].fillna("").astype(str).str.strip()
        df["Title"] = df["Title"].fillna("").astype(str).str.strip()
        df["Description"] = df["Description"].fillna("").astype(str).str.strip()
        if df["URL"].astype(bool).any():
            df = df.drop_duplicates(subset=["URL"], keep="first")
        df = df.drop_duplicates(subset=["Title", "Description"], keep="first")
        df.to_csv(filename, index=False, encoding="utf-8")
    except Exception as e:
        print("Error deduping history:", e)

# -------------------------
# Twitter fetcher
# -------------------------
client = tweepy.Client(bearer_token=TWITTER_BEARER_TOKEN)

def fetch_twitter_news(query, count=10):
    try:
        tweets = client.search_recent_tweets(
            query=query,
            max_results=min(max(count, 10), 100),
            tweet_fields=["created_at", "text", "author_id"]
        )
        results = []
        if tweets and getattr(tweets, "data", None):
            for tweet in tweets.data:
                tweet_time = format_datetime(str(tweet.created_at)) if tweet.created_at else "Unknown"
                text_cleaned = clean_text(tweet.text)
                results.append({
                    "Platform": "Twitter",
                    "Time": tweet_time,
                    "Author": tweet.author_id,
                    "Title": text_cleaned[:60] + "...",
                    "Description": text_cleaned,
                    "URL": f"https://twitter.com/user/status/{tweet.id}"
                })
        return results
    except Exception as e:
        messagebox.showerror("Error", f"⚠️ Error fetching tweets: {e}")
        return []

# -------------------------
# Google News fetcher
# -------------------------
def fetch_google_news(query, count=40):
    try:
        params = {"q": query, "apiKey": NEWSAPI_KEY, "language": "en", "pageSize": count}
        response = requests.get(NEWSAPI_ENDPOINT, params=params, timeout=15)
        data = response.json()
    except Exception as e:
        messagebox.showerror("Error", f"⚠️ Error fetching Google News: {e}")
        return []

    results = []
    if "articles" in data:
        for article in data["articles"]:
            pub_time = format_datetime(article.get("publishedAt", ""))
            title_cleaned = clean_text(article.get("title", ""))
            desc_cleaned = clean_text(article.get("description", "No description"))
            results.append({
                "Platform": "Google News",
                "Time": pub_time,
                "Author": article.get("author", "Unknown"),
                "Title": title_cleaned,
                "Description": desc_cleaned,
                "URL": article.get("url", "")
            })
    return results

# -------------------------
# GUI logic
# -------------------------
latest_results = []

def show_results():
    query = search_entry.get().strip()
    if not query:
        messagebox.showwarning("Input Error", "Please enter a keyword to search news.")
        return

    for tree in (tree_twitter, tree_google):
        for row in tree.get_children():
            tree.delete(row)

    google_news = fetch_google_news(query, count=40)
    twitter_news = fetch_twitter_news(query, count=10)

    for news in twitter_news:
        tree_twitter.insert("", "end", values=(news["Platform"], news["Time"], news["Author"],
                                               news["Title"], news["Description"], news["URL"]))
    for news in google_news:
        tree_google.insert("", "end", values=(news["Platform"], news["Time"], news["Author"],
                                              news["Title"], news["Description"], news["URL"]))

    global latest_results
    latest_results = google_news + twitter_news

    if latest_results:
        success = save_to_history(latest_results, HISTORY_FILE)
        if success:
            count_google = len(google_news)
            count_twitter = len(twitter_news)
            total_count = len(latest_results)
            status_label.config(text=f"✅ Saved {total_count} news items to history", fg="#00ffcc")
            # Send Slack alert automatically
            send_slack_alert(f"✅ {count_twitter} Twitter + {count_google} Google News items saved for keyword: {query}")
        else:
            status_label.config(text="⚠️ Error saving history", fg="red")
    else:
        status_label.config(text="⚠️ No results to save", fg="orange")

def save_results():
    if not latest_results:
        messagebox.showinfo("No Data", "No news to save. Please search first.")
        return
    file_path = filedialog.asksaveasfilename(defaultextension=".csv",
                                             filetypes=[("CSV Files", "*.csv")])
    if file_path:
        pd.DataFrame(latest_results).to_csv(file_path, index=False, encoding="utf-8")
        messagebox.showinfo("Success", f"Results saved to {file_path}")

def send_test_slack():
    send_slack_alert("🔔 Test alert from GUI button!")
    messagebox.showinfo("Slack Test", "Test Slack alert sent!")

# -------------------------
# Tkinter UI
# -------------------------
root = tk.Tk()
root.title("⚡ News Aggregator - Twitter & Google News")
root.geometry("1250x750")
root.configure(bg="#1a1a1a")

style = ttk.Style()
style.theme_use("clam")
style.configure("Treeview",
                background="#262626",
                foreground="white",
                rowheight=28,
                fieldbackground="#262626",
                font=("Consolas", 10))
style.map("Treeview", background=[("selected", "#00b894")])
style.configure("Treeview.Heading",
                background="#0f0f0f",
                foreground="#00ffcc",
                font=("Consolas", 11, "bold"))

frame_top = tk.Frame(root, bg="#1a1a1a")
frame_top.pack(fill="x", pady=15, padx=20)

tk.Label(frame_top, text="🔎 Enter Keyword:", font=("Consolas", 13, "bold"),
         bg="#1a1a1a", fg="#00ffcc").pack(side=tk.LEFT, padx=5)

search_entry = tk.Entry(frame_top, font=("Consolas", 13), width=35,
                        bg="#0f0f0f", fg="white", insertbackground="white", relief="flat")
search_entry.pack(side=tk.LEFT, padx=5)

def hover_btn(e): e.widget.config(bg="#0984e3")
def leave_btn(e): e.widget.config(bg="#00b894")

btn_search = tk.Button(frame_top, text="SEARCH", command=show_results,
                       font=("Consolas", 12, "bold"),
                       bg="#00b894", fg="white", relief="flat", padx=15, pady=5)
btn_search.pack(side=tk.LEFT, padx=8)
btn_search.bind("<Enter>", hover_btn)
btn_search.bind("<Leave>", leave_btn)

btn_save = tk.Button(frame_top, text="SAVE", command=save_results,
                     font=("Consolas", 12, "bold"),
                     bg="#00b894", fg="white", relief="flat", padx=15, pady=5)
btn_save.pack(side=tk.LEFT, padx=8)
btn_save.bind("<Enter>", hover_btn)
btn_save.bind("<Leave>", leave_btn)

# Test Slack Button
btn_test_slack = tk.Button(frame_top, text="Send Slack Test Alert", command=send_test_slack,
                            font=("Consolas", 12, "bold"), bg="#0984e3", fg="white", relief="flat", padx=15, pady=5)
btn_test_slack.pack(side=tk.LEFT, padx=8)
btn_test_slack.bind("<Enter>", lambda e: e.widget.config(bg="#0984e3"))
btn_test_slack.bind("<Leave>", lambda e: e.widget.config(bg="#0984e3"))

notebook = ttk.Notebook(root)
notebook.pack(fill="both", expand=True, padx=15, pady=15)

frame_twitter = tk.Frame(notebook, bg="#1a1a1a")
notebook.add(frame_twitter, text="🐦 Twitter News")

columns = ("Platform", "Time", "Author", "Title", "Description", "URL")
tree_twitter = ttk.Treeview(frame_twitter, columns=columns, show="headings")
for col in columns:
    tree_twitter.heading(col, text=col)
    tree_twitter.column(col, width=180, anchor="center")
tree_twitter.pack(fill="both", expand=True)

frame_google = tk.Frame(notebook, bg="#1a1a1a")
notebook.add(frame_google, text="🌍 Google News")

tree_google = ttk.Treeview(frame_google, columns=columns, show="headings")
for col in columns:
    tree_google.heading(col, text=col)
    tree_google.column(col, width=180, anchor="center")
tree_google.pack(fill="both", expand=True)

# Status label at bottom
status_label = tk.Label(root, text="Ready", font=("Consolas", 11),
                        bg="#1a1a1a", fg="white", anchor="w")
status_label.pack(fill="x", padx=15, pady=5)

root.mainloop()
