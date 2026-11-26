import os
import sqlite3
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import tasks
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
DB_FILE = "bot.db"


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


@bot.tree.command(name="ping", description="Check that the bot is alive")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("Pong!")


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
    remind_at = datetime.now(timezone.utc) + timedelta(minutes=minutes)

    conn = sqlite3.connect(DB_FILE)
    conn.execute(
        "INSERT INTO reminders (user_id, channel_id, message, remind_at) VALUES (?, ?, ?, ?)",
        (interaction.user.id, interaction.channel_id, message, remind_at.isoformat()),
    )
    conn.commit()
    conn.close()

    await interaction.response.send_message(
        f"Got it! I'll remind you in {minutes} minute(s): {message}"
    )


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("DISCORD_TOKEN is missing. Add it to your .env file.")
    bot.run(TOKEN)