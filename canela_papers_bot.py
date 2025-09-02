import discord
import feedparser
import asyncio
import os
import sqlite3

TOKEN = os.getenv("TOKEN")  # your bot token in Railway or env
DB_FILE = "bot_data.db"

# ---------- Database Setup ----------
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # keywords per guild
    c.execute("CREATE TABLE IF NOT EXISTS keywords (guild_id INTEGER, word TEXT, UNIQUE(guild_id, word))")
    # seen links per guild
    c.execute("CREATE TABLE IF NOT EXISTS seen_links (guild_id INTEGER, link TEXT, UNIQUE(guild_id, link))")
    # feeds per guild
    c.execute("CREATE TABLE IF NOT EXISTS feeds (guild_id INTEGER, url TEXT, UNIQUE(guild_id, url))")
    # settings per guild
    c.execute("CREATE TABLE IF NOT EXISTS settings (guild_id INTEGER, key TEXT, value TEXT, UNIQUE(guild_id, key))")
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
    return int(row[0]) if row else 24  # default 24h

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
    keywords = get_keywords(guild_id)
    feeds = get_feeds(guild_id)
    new_count = 0
    if not feeds:
        await channel.send("⚠️ No feeds configured. Use `!addfeed URL` to add one.")
        return
    for feed_url in feeds:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries:
            if not is_seen(guild_id, entry.link):
                title = entry.title.lower()
                if any(kw.lower() in title for kw in keywords):
                    await channel.send(f"📄 **{entry.title}**\n{entry.link}")
                    mark_seen(guild_id, entry.link)
                    new_count += 1
    await channel.send("✅ Scan complete." if new_count > 0 else "✅ No new matching papers found.")

async def scheduled_check():
    await client.wait_until_ready()
    while not client.is_closed():
        for guild in client.guilds:
            # Try to find the bot's designated channel per guild (here channels where the bot can send messages)
            # For simplicity, using the first text channel where the bot has send permission
            channel = None
            for ch in guild.text_channels:
                if ch.permissions_for(guild.me).send_messages:
                    channel = ch
                    break
            if channel:
                await scan_feeds(channel)
        await asyncio.sleep(43200)  # Run hourly, or adjust as needed

@client.event
async def on_message(message: discord.Message):
    if message.author == client.user:
        return
    if not message.guild:  # ignore DMs
        return

    content = message.content.strip()
    guild_id = message.guild.id

    # Commands work only in channels where bot has permissions, no hard restriction currently
    # Keyword management
    if content.startswith("!addkeyword "):
        kw = content[len("!addkeyword "):].strip()
        if kw:
            add_keyword(guild_id, kw)
            await message.channel.send(f"✅ Added keyword: `{kw}`")
        else:
            await message.channel.send("⚠️ Provide a keyword.")
    elif content.startswith("!removekeyword "):
        kw = content[len("!removekeyword "):].strip()
        remove_keyword(guild_id, kw)
        await message.channel.send(f"🗑️ Removed keyword: `{kw}`")
    elif content.startswith("!listkeywords"):
        kws = get_keywords(guild_id)
        if kws:
            await message.channel.send("🔑 Keywords:\n" + ", ".join(f"`{kw}`" for kw in kws))
        else:
            await message.channel.send("No keywords set.")
    # Feed management
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
        if feeds:
            await message.channel.send("🌐 Feeds:\n" + "\n".join(f"`{url}`" for url in feeds))
        else:
            await message.channel.send("No feeds set.")
    # Interval
    elif content.startswith("!setinterval "):
        try:
            hours = int(content[len("!setinterval "):].strip())
            if hours > 0:
                set_interval(guild_id, hours)
                await message.channel.send(f"⏱️ Interval set to {hours} hours.")
            else:
                await message.channel.send("⚠️ Interval must be > 0.")
        except ValueError:
            await message.channel.send("⚠️ Invalid number.")
    # Manual scan
    elif content.startswith("!scan"):
        await message.channel.send("🔍 Scanning now...")
        await scan_feeds(message.channel)
        # Completion message sent inside scan_feeds()

@client.event
async def on_ready():
    print(f"Logged in as {client.user}")
    client.loop.create_task(scheduled_check())

# Initialize Db and run bot
init_db()
client.run(TOKEN)

