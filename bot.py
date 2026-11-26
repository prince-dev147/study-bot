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