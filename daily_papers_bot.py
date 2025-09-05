import discord
import feedparser
import asyncio
import os
import sqlite3

TOKEN = os.getenv("TOKEN")  # your bot token in Railway or env
DB_FILE = "bot_data.db"

# Default config
DEFAULT_INTERVAL = 12  # hours
DEFAULT_FEEDS = [
    "https://www.nature.com/nature.rss",
    "https://www.science.org/action/showFeed?type=etoc&feed=rss&jc=science",
    "https://export.arxiv.org/rss/physics",
    "https://export.arxiv.org/rss/cond-mat",
    "https://export.arxiv.org/rss/quant-ph",
    "https://export.arxiv.org/rss/math",
    "https://export.arxiv.org/rss/cs"
]

# ---------- Database Setup ----------
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS keywords (guild_id INTEGER, word TEXT, UNIQUE(guild_id, word))")
    c.execute("CREATE TABLE IF NOT EXISTS seen_links (guild_id INTEGER, link TEXT, UNIQUE(guild_id, link))")
    c.execute("CREATE TABLE IF NOT EXISTS feeds (guild_id INTEGER, url TEXT, UNIQUE(guild_id, url))")
    c.execute("CREATE TABLE IF NOT EXISTS settings (guild_id INTEGER, key TEXT, value TEXT, UNIQUE(guild_id, key))")
    conn.commit()
    conn.close()

def ensure_default_feeds(guild_id):
    """If a guild has no feeds yet, insert default feeds."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM feeds WHERE guild_id=?", (guild_id,))
    count = c.fetchone()[0]
    if count == 0:
        for url in DEFAULT_FEEDS:
            c.execute("INSERT OR IGNORE INTO feeds (guild_id, url) VALUES (?, ?)", (guild_id, url))
        conn.commit()
    conn.close()

def get_keywords(guild_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT word FROM keywords WHERE guild_id=?", (guild_id,))
    rows = [row[0] for row in c.fetchall()]
    conn.close()
    return set(rows)

def add_keyword(guild_id, word):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO keywords (guild_id, word) VALUES (?, ?)", (guild_id, word))
    conn.commit()
    conn.close()

def remove_keyword(guild_id, word):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM keywords WHERE guild_id=? AND word=?", (guild_id, word))
    conn.commit()
    conn.close()

def get_feeds(guild_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT url FROM feeds WHERE guild_id=?", (guild_id,))
    rows = [row[0] for row in c.fetchall()]
    conn.close()
    return set(rows)

def add_feed(guild_id, url):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO feeds (guild_id, url) VALUES (?, ?)", (guild_id, url))
    conn.commit()
    conn.close()

def remove_feed(guild_id, url):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM feeds WHERE guild_id=? AND url=?", (guild_id, url))
    conn.commit()
    conn.close()

def is_seen(guild_id, link):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT 1 FROM seen_links WHERE guild_id=? AND link=?", (guild_id, link))
    found = c.fetchone() is not None
    conn.close()
    return found

def mark_seen(guild_id, link):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO seen_links (guild_id, link) VALUES (?, ?)", (guild_id, link))
    conn.commit()
    conn.close()

def get_interval(guild_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE guild_id=? AND key='interval_hours'", (guild_id,))
    row = c.fetchone()
    conn.close()
    return int(row[0]) if row else DEFAULT_INTERVAL

def set_interval(guild_id, hours):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings (guild_id, key, value) VALUES (?, 'interval_hours', ?)", (guild_id, str(hours)))
    conn.commit()
    conn.close()

# ---------- Discord Bot ----------
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

async def scan_feeds(channel):
    guild_id = channel.guild.id
    ensure_default_feeds(guild_id)  # auto-add defaults if none
    keywords = get_keywords(guild_id)
    feeds = get_feeds(guild_id)
    new_count = 0
    for feed_url in feeds:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries:
            if not is_seen(guild_id, entry.link):
                title = entry.title.lower()
                if not keywords or any(kw.lower() in title for kw in keywords):
                    await channel.send(f"📄 **{entry.title}**\n{entry.link}")
                    mark_seen(guild_id, entry.link)
                    new_count += 1
    await channel.send("✅ Scan complete." if new_count > 0 else "✅ No new matching papers found.")

async def scheduled_check():
    await client.wait_until_ready()
    while not client.is_closed():
        for guild in client.guilds:
            # Find a text channel where bot can send messages
            channel = None
            for ch in guild.text_channels:
                if ch.permissions_for(guild.me).send_messages:
                    channel = ch
                    break
            if channel:
                await scan_feeds(channel)
        await asyncio.sleep(DEFAULT_INTERVAL * 3600)

@client.event
async def on_guild_join(guild):
    """When bot joins a new server, add default feeds."""
    ensure_default_feeds(guild.id)

@client.event
async def on_message(message: discord.Message):
    if message.author == client.user or not message.guild:
        return

    content = message.content.strip()
    guild_id = message.guild.id

    # --- Keyword commands (support multiple) ---
    if content.startswith("!addkeyword "):
        kws = content[len("!addkeyword "):].split(",")
        added = []
        for kw in kws:
            kw = kw.strip()
            if kw:
                add_keyword(guild_id, kw)
                added.append(kw)
        if added:
            await message.channel.send(f"✅ Added keywords: {', '.join(f'`{k}`' for k in added)}")

    elif content.startswith("!removekeyword "):
        kws = content[len("!removekeyword "):].split(",")
        removed = []
        for kw in kws:
            kw = kw.strip()
            if kw:
                remove_keyword(guild_id, kw)
                removed.append(kw)
        if removed:
            await message.channel.send(f"🗑️ Removed keywords: {', '.join(f'`{k}`' for k in removed)}")

    elif content.startswith("!listkeywords"):
        kws = get_keywords(guild_id)
        await message.channel.send("🔑 Keywords:\n" + ", ".join(f"`{kw}`" for kw in kws) if kws else "No keywords set.")

    # --- Feed commands ---
    elif content.startswith("!addfeed "):
        url = content[len("!addfeed "):].strip()
        add_feed(guild_id, url)
        await message.channel.send(f"🌐 Added feed: `{url}`")

    elif content.startswith("!removefeed "):
        url = content[len("!removefeed "):].strip()
        remove_feed(guild_id, url)
        await message.channel.send(f"🗑️ Removed feed: `{url}`")

    elif content.startswith("!listfeeds"):
        feeds = get_feeds(guild_id)
        await message.channel.send("🌐 Feeds:\n" + "\n".join(f"`{url}`" for url in feeds) if feeds else "No feeds set.")

    # --- Interval ---
    elif content.startswith("!setinterval "):
        try:
            hours = int(content[len("!setinterval "):].strip())
            if hours > 0:
                set_interval(guild_id, hours)
                await message.channel.send(f"⏱️ Interval set to {hours} hours.")
        except ValueError:
            await message.channel.send("⚠️ Invalid number.")

    # --- Scan & Reset ---
    elif content.startswith("!scan"):
        await message.channel.send("🔍 Scanning now...")
        await scan_feeds(message.channel)

    elif content.startswith("!resetfeeds"):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("DELETE FROM feeds WHERE guild_id=?", (guild_id,))
        conn.commit()
        conn.close()
        ensure_default_feeds(guild_id)
        await message.channel.send("♻️ Feeds have been reset to default.")

@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")
    client.loop.create_task(scheduled_check())

# Initialize DB and run bot
init_db()
client.run(TOKEN)
