import discord
from discord.ext import commands
from dotenv import load_dotenv
import os

load_dotenv()


class Bot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="\x00", intents=discord.Intents.all())

    async def setup_hook(self):
        for filename in os.listdir("./cogs"):
            if filename.endswith(".py") and not filename.startswith("_"):
                await self.load_extension(f"cogs.{filename[:-3]}")
        await self.tree.sync(guild=discord.Object(id=290553862476136449))


bot = Bot()


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")


bot.run(os.getenv("TOKEN", ""))
