# canela_papers_bot
A discord bot that searches for scientific papers in rss feed using customizable keywords.

Canela Papers Bot 📚🤖

A Discord bot that searches for the latest scientific papers from RSS feeds using customizable keywords.
Stay updated on research that matters to you – directly inside your Discord server!

🚀 Features

Fetches papers daily from RSS feeds.

Filter by custom keywords (add/remove via Discord commands).

Force a manual scan on demand.

Persistent storage of keywords (even after restart).

Easy setup and deployment.

🔧 Installation

Clone the repository

git clone https://github.com/your-username/canela_papers_bot.git
cd canela_papers_bot


Set up a virtual environment (recommended)

python -m venv venv
source venv/bin/activate   # Linux/macOS
venv\Scripts\activate      # Windows


Install dependencies

pip install -r requirements.txt


Configure your bot token

Create a file called .env in the root directory.

Add your Discord bot token:

DISCORD_TOKEN=your_discord_token_here

▶️ Running the Bot
python bot.py

📜 Commands

!addkeyword <word> → Add a keyword to track.

!removekeyword <word> → Remove a keyword.

!listkeywords → Show all active keywords.

!scan → Force the bot to scan feeds right now.

🛠️ Configuration

Default RSS feeds can be set inside feeds.json.

Keywords are saved in keywords.json (persistent across runs).

📌 Example Usage

You: !addkeyword graphene

Bot: ✅ Keyword "graphene" added.

(Next scan will fetch latest papers with “graphene” in the title/summary)

📄 License

This project is licensed under the MIT License – see the LICENSE
 file for details.
