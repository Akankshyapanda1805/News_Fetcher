import os 
import tweepy
import requests
from dotenv import load_dotenv
from datetime import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pandas as pd
import re

load_dotenv()

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

TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")
client = tweepy.Client(bearer_token=TWITTER_BEARER_TOKEN)



def fetch_twitter_news(query, count=10):
    try:
        tweets = client.search_recent_tweets(
            query=query,
            max_results=min(max(count, 10), 100),
            tweet_fields=["created_at", "text", "author_id"]
        )
        results = []
        if tweets.data:
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


NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")
NEWSAPI_ENDPOINT = "https://newsapi.org/v2/everything"



def fetch_google_news(query, count=40):
    params = {"q": query, "apiKey": NEWSAPI_KEY, "language": "en", "pageSize": count}
    response = requests.get(NEWSAPI_ENDPOINT, params=params)
    data = response.json()
    results = []
    if "articles" in data:
        for article in data["articles"]:
            pub_time = format_datetime(article.get("publishedAt", ""))
            title_cleaned = clean_text(article["title"])
            desc_cleaned = clean_text(article.get("description", "No description"))
            results.append({
                "Platform": "Google News",
                "Time": pub_time,
                "Author": article.get("author", "Unknown"),
                "Title": title_cleaned,
                "Description": desc_cleaned,
                "URL": article["url"]
            })
    return results




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

def save_results():
    if not latest_results:
        messagebox.showinfo("No Data", "No news to save. Please search first.")
        return
    file_path = filedialog.asksaveasfilename(defaultextension=".csv",
                                             filetypes=[("CSV Files", "*.csv")])
    if file_path:
        pd.DataFrame(latest_results).to_csv(file_path, index=False, encoding="utf-8")
        messagebox.showinfo("Success", f"Results saved to {file_path}")




root = tk.Tk()
root.title("⚡ News Aggregator - Twitter & Google News")
root.geometry("1250x720")
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

latest_results = []
root.mainloop()
