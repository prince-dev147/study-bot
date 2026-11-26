# StudyBot

A Discord bot that helps you study. It sets reminders and explains code in plain English using an LLM.

Built with Python, [discord.py](https://discordpy.readthedocs.io/), SQLite, and the Google Gemini API.

<!-- Add a screenshot or GIF of the bot in action here: ![StudyBot demo](docs/demo.png) -->

## Features

| Command | What it does |
|---|---|
| `/ping` | Checks that the bot is alive and shows its latency |
| `/remind <minutes> <message>` | Sets a study reminder (1 minute to 7 days). The bot pings you in the same channel when it is due |
| `/explain <code>` | Explains a code snippet in plain English, like a friendly tutor |

## How it works

```
You type /explain in Discord
        |
        v
Discord sends the command to the bot (bot.py)
        |
        v
The bot sends the code to the Gemini API
        |
        v
Gemini returns an explanation
        |
        v
The bot posts it in the channel
```

`/remind` doesn't use the AI. Reminders are saved in a SQLite database, and a background task checks for due reminders every 30 seconds, so they survive a bot restart.

## Tech stack

- **Python 3.12**
- **discord.py**: slash commands and background tasks
- **SQLite**: reminder storage
- **Google Gemini API** (`google-genai`): code explanations
- **python-dotenv**: configuration from environment variables
- **Railway**: hosting

## Getting started

### Prerequisites

- Python 3.12 or newer
- A Discord account and a test server you manage
- A Google AI Studio API key (free tier available)

### 1. Create the Discord bot

1. Open the [Discord Developer Portal](https://discord.com/developers/applications) and click **New Application**.
2. In the **Bot** tab, click **Reset Token** and copy the token. Keep it secret.
3. In **OAuth2 → URL Generator**, tick the scopes `bot` and `applications.commands`, and the **Send Messages** permission.
4. Open the generated URL and add the bot to your server.

### 2. Get a Gemini API key

Create a key at [Google AI Studio](https://aistudio.google.com).

### 3. Clone and install

```bash
git clone https://github.com/prince-dev147/study-bot.git
cd study-bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 4. Configure

Create a `.env` file in the project root:

```
DISCORD_TOKEN=your_discord_bot_token
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-3.5-flash-lite
```

`GEMINI_MODEL` is optional. Model names change often, so check the [Gemini model list](https://ai.google.dev/gemini-api/docs/models) if you get a "model not found" error.

### 5. Run

```bash
python bot.py
```

You should see `Logged in as studybot#...`. Then try `/ping` in your server.

## Configuration

| Variable | Required | Description |
|---|---|---|
| `DISCORD_TOKEN` | Yes | Your bot token from the Developer Portal |
| `GEMINI_API_KEY` | For `/explain` | Your Google AI Studio API key |
| `GEMINI_MODEL` | No | Preferred Gemini model (default: `gemini-3.5-flash-lite`) |

## Reliability features

- **Model fallback:** if the preferred Gemini model is busy or unavailable, the bot tries backup models automatically.
- **Retries:** temporary server errors (503) are retried before giving up.
- **Cooldown:** `/explain` is limited to one use per user every 10 seconds to protect the API quota.
- **Deferred replies:** commands acknowledge Discord immediately, so slow AI responses don't hit Discord's 3-second limit.

## Project structure

```
study-bot/
├── bot.py              # The whole bot: commands, reminders, AI calls
├── requirements.txt    # Python dependencies
├── Procfile            # Start command for the host (worker: python bot.py)
├── .python-version     # Python version used when deploying
├── .env                # Secrets (never committed)
└── bot.db              # SQLite database, created on first run (never committed)
```

## Deployment

The bot must stay connected to Discord all the time, so it needs a host that doesn't sleep. It is set up for [Railway](https://railway.com):

1. Push the repo to GitHub.
2. Create a Railway project from the repo.
3. Add `DISCORD_TOKEN`, `GEMINI_API_KEY`, and `GEMINI_MODEL` in the service's **Variables** tab.
4. Check the deploy logs for `Logged in as studybot#...`.

> **Note:** hosts with temporary storage wipe local files on redeploy. To keep reminders across redeploys, attach a persistent volume and point `DB_FILE` in `bot.py` at it.

## Known limitations

- Slash command boxes accept one line of text, so multi-line code can't be pasted into `/explain` properly yet.
- Reminders are posted in the channel where they were created. If the bot loses access to that channel, it falls back to a direct message.
- Reminder times are relative (minutes from now), not calendar dates.

## Roadmap

- [ ] Accept uploaded `.py` files in `/explain`
- [ ] Persistent volume for the reminder database
- [ ] `/reminders` to list and cancel pending reminders
- [ ] Unit tests for the reminder logic

## Security

- Never commit `.env`. It is listed in `.gitignore`.
- If a token or API key is ever exposed, reset it immediately in the Discord Developer Portal or Google AI Studio.

## Author

Built by [prince-dev147](https://github.com/prince-dev147).