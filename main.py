import discord
from discord.ext import commands
from pathlib import Path
import os

from config import config


class Bot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="\x00", intents=discord.Intents.all())

    async def setup_hook(self):
        for filename in os.listdir("./cogs"):
            if filename.endswith(".py") and not filename.startswith("_"):
                await self.load_extension(f"cogs.{filename[:-3]}")
        guild = discord.Object(id=config.guild_id)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)


bot = Bot()


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    if not config.dev and Path("/.dockerenv").exists():
        Path(".connected").touch()


bot.run(config.token)
