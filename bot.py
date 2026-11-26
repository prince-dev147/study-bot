import asyncio
import os
import sqlite3
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import tasks
from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
DB_FILE = "bot.db"

# Preferred model first, then backups (duplicates removed, order kept)
MODEL_CHAIN = list(
    dict.fromkeys(
        [GEMINI_MODEL, "gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-3.6-flash"]
    )
)

ai_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

EXPLAIN_INSTRUCTIONS = (
    "You are a friendly coding tutor for beginners. Explain the code the user "
    "sends in plain English: first one sentence on what it does overall, then a "
    "short step-by-step walkthrough. If you spot a bug or bad practice, mention "
    "it briefly. Keep the whole answer under 1500 characters."
)


def init_db():
    """Create the reminders table if it doesn't exist yet."""
    conn = sqlite3.connect(DB_FILE)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            channel_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            remind_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


async def ask_gemini(code):
    """Ask Gemini to explain the code. Tries each model, retrying on busy errors.

    Returns the explanation text, or None if every model failed.
    """
    for model in MODEL_CHAIN:
        for attempt in range(2):
            try:
                response = await ai_client.aio.models.generate_content(
                    model=model,
                    contents=f"Explain this code:\n\n{code}",
                    config=types.GenerateContentConfig(
                        system_instruction=EXPLAIN_INSTRUCTIONS
                    ),
                )
                if response.text:
                    return response.text
                break  # empty answer: try the next model
            except errors.ServerError as error:
                print(f"[WARN] {model} busy ({error.code}), attempt {attempt + 1}")
                await asyncio.sleep(2)
            except errors.ClientError as error:
                print(f"[WARN] {model} failed ({error.code})")
                if error.code in (404, 429):
                    break  # model gone or quota hit: try the next model
                raise
    return None


class StudyBot(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.default())
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        init_db()
        await self.tree.sync()  # registers the slash commands with Discord
        self.check_reminders.start()

    async def on_ready(self):
        print(f"Logged in as {self.user}")

    @tasks.loop(seconds=30)
    async def check_reminders(self):
        """Every 30 seconds, send any reminders that are due."""
        now = datetime.now(timezone.utc).isoformat()
        conn = sqlite3.connect(DB_FILE)
        due = conn.execute(
            "SELECT id, user_id, channel_id, message FROM reminders WHERE remind_at <= ?",
            (now,),
        ).fetchall()

        for reminder_id, user_id, channel_id, message in due:
            try:
                target = self.get_channel(channel_id) or await self.fetch_user(user_id)
                await target.send(f"<@{user_id}> reminder: {message}")
            except discord.HTTPException as error:
                print(f"[ERROR] Could not send reminder {reminder_id}: {error}")
            conn.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))

        conn.commit()
        conn.close()

    @check_reminders.before_loop
    async def before_check_reminders(self):
        await self.wait_until_ready()


bot = StudyBot()


@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
):
    """Handle command errors, like the /explain cooldown."""
    if isinstance(error, app_commands.CommandOnCooldown):
        message = f"Slow down! Try again in {error.retry_after:.0f} seconds."
    else:
        print(f"[ERROR] Command error: {error}")
        message = "Something went wrong. Please try again."

    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)


@bot.tree.command(name="ping", description="Check that the bot is alive")
async def ping(interaction: discord.Interaction):
    await interaction.response.defer()  # tell Discord "working on it" right away
    latency_ms = round(bot.latency * 1000)
    await interaction.followup.send(f"Pong! Latency: {latency_ms} ms")


@bot.tree.command(name="remind", description="Set a study reminder")
@app_commands.describe(
    minutes="How many minutes from now (1 to 10080)",
    message="What should I remind you about?",
)
async def remind(
    interaction: discord.Interaction,
    minutes: app_commands.Range[int, 1, 10080],
    message: str,
):
    await interaction.response.defer()

    remind_at = datetime.now(timezone.utc) + timedelta(minutes=minutes)

    conn = sqlite3.connect(DB_FILE)
    conn.execute(
        "INSERT INTO reminders (user_id, channel_id, message, remind_at) VALUES (?, ?, ?, ?)",
        (interaction.user.id, interaction.channel_id, message, remind_at.isoformat()),
    )
    conn.commit()
    conn.close()

    await interaction.followup.send(
        f"Got it! I'll remind you in {minutes} minute(s): {message}"
    )


@bot.tree.command(name="explain", description="Explain a piece of code in plain English")
@app_commands.describe(code="The code you want explained")
@app_commands.checks.cooldown(1, 10.0, key=lambda i: i.user.id)
async def explain(
    interaction: discord.Interaction,
    code: app_commands.Range[str, 1, 3000],
):
    await interaction.response.defer()  # the AI call can take several seconds

    if ai_client is None:
        await interaction.followup.send("GEMINI_API_KEY is missing in my .env file.")
        return

    try:
        answer = await ask_gemini(code)
    except Exception as error:
        print(f"[ERROR] /explain failed: {error}")
        answer = None

    if answer is None:
        await interaction.followup.send(
            "Sorry, the AI is busy right now. Please try again in a minute."
        )
        return

    # Discord messages are limited to 2000 characters
    await interaction.followup.send(answer[:1900])


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("DISCORD_TOKEN is missing. Add it to your .env file.")
    bot.run(TOKEN)