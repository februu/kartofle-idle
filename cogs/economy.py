import discord
from discord.ext import commands
from discord import app_commands

import db


class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="balance", description="Checks your balance")
    async def balance(self, interaction: discord.Interaction):
        balance = db.get_user_balance(interaction.user.id)
        await interaction.response.send_message(f"Siema, masz na koncie {balance} kartofli.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Economy(bot))
