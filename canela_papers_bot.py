import discord
import feedparser
import asyncio
import os
import sqlite3

TOKEN = os.getenv("TOKEN")  # stored in Railway environment variables
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
DB_FILE = "bot_data.db"

# ---------- Database Setup ----------
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # keywords
    c.execute("CREATE TABLE IF NOT EXISTS keywords (word TEXT UNIQUE)")
    # seen links
    c.execute("CREATE TABLE IF NOT EXISTS seen_links (link TEXT UNIQUE)")
    # feeds
    c.execute("CREATE TABLE IF NOT EXISTS feeds (url TEXT UNIQUE)")
    # settings
    c.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT UNIQUE, value TEXT)")
    conn.commit()
    conn.close()

def get_keywords():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT word FROM keywords")
    rows = [row[0] for row in c.fetchall()]
    conn.close()
    return set(rows)

def add_keyword(word):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO keywords (word) VALUES (?)", (word,))
    conn.commit()
    conn.close()

def remove_keyword(word):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM keywords WHERE word=?", (word,))
    conn.commit()
    conn.close()

def get_feeds():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT url FROM feeds")
    rows = [row[0] for row in c.fetchall()]
    conn.close()
    return set(rows)

def add_feed(url):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO feeds (url) VALUES (?)", (url,))
    conn.commit()
    conn.close()

def remove_feed(url):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM feeds WHERE url=?", (url,))
    conn.commit()
    conn.close()

def is_seen(link):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT 1 FROM seen_links WHERE link=?", (link,))
    found = c.fetchone() is not None
    conn.close()
    return found

def mark_seen(link):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO seen_links (link) VALUES (?)", (link,))
    conn.commit()
    conn.close()

def get_interval():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key='interval_hours'")
    row = c.fetchone()
    conn.close()
    return int(row[0]) if row else 24  # default 24h

def set_interval(hours):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('interval_hours', ?)", (str(hours),))
    conn.commit()
    conn.close()

# ---------- Discord Bot ----------
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

async def scan_feeds(channel):
    """Scan feeds and post new matching papers."""
    keywords = get_keywords()
    feeds = get_feeds()
    new_count = 0
    if not feeds:
        await channel.send("⚠️ No feeds configured. Use `!addfeed URL` to add one.")
        return
    for feed_url in feeds:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries:
            if not is_seen(entry.link):
                title = entry.title.lower()
                if any(kw.lower() in title for kw in keywords):
                    await channel.send(f"📄 **{entry.title}**\n{entry.link}")
                    mark_seen(entry.link)
                    new_count += 1
    await channel.send("✅ Scan complete." if new_count > 0 else "✅ No new matching papers found.")

async def scheduled_check():
    await client.wait_for("ready")
    channel = client.get_channel(CHANNEL_ID)
    while True:
        await scan_feeds(channel)
        await asyncio.sleep(get_interval() * 3600)

@client.event
async def on_message(message: discord.Message):
    if message.author == client.user:
        return

    # Restrict commands to the specified channel only
    if message.channel.id != CHANNEL_ID:
        return

    content = message.content.strip()
    # Keyword management
    if content.startswith("!addkeyword "):
        kw = content[len("!addkeyword "):].strip()
        if kw:
            add_keyword(kw)
            await message.channel.send(f"✅ Added keyword: `{kw}`")
        else:
            await message.channel.send("⚠️ Provide a keyword.")
    elif content.startswith("!removekeyword "):
        kw = content[len("!removekeyword "):].strip()
        remove_keyword(kw)
        await message.channel.send(f"🗑️ Removed keyword: `{kw}`")
    elif content.startswith("!listkeywords"):
        kws = get_keywords()
        if kws:
            await message.channel.send("🔑 Keywords:\n" + ", ".join(f"`{kw}`" for kw in kws))
        else:
            await message.channel.send("No keywords set.")
    # Feed management
    elif content.startswith("!addfeed "):
        url = content[len("!addfeed "):].strip()
        add_feed(url)
        await message.channel.send(f"🌐 Added feed: `{url}`")
    elif content.startswith("!removefeed "):
        url = content[len("!removefeed "):].strip()
        remove_feed(url)
        await message.channel.send(f"🗑️ Removed feed: `{url}`")
    elif content.startswith("!listfeeds"):
        feeds = get_feeds()
        if feeds:
            await message.channel.send("🌐 Feeds:\n" + "\n".join(f"`{url}`" for url in feeds))
        else:
            await message.channel.send("No feeds set.")
    # Interval
    elif content.startswith("!setinterval "):
        try:
            hours = int(content[len("!setinterval "):].strip())
            if hours > 0:
                set_interval(hours)
                await message.channel.send(f"⏱️ Interval set to {hours} hours.")
            else:
                await message.channel.send("⚠️ Interval must be > 0.")
        except ValueError:
            await message.channel.send("⚠️ Invalid number.")
    # Manual scan
    elif content.startswith("!scan"):
        await message.channel.send("🔍 Scanning now...")
        await scan_feeds(message.channel)
        # The scan_feeds function itself sends a completion message

@client.event
async def on_ready():
    print(f"Logged in as {client.user}")
    client.loop.create_task(scheduled_check())

# Initialize DB and run bot
init_db()
client.run(TOKEN)
