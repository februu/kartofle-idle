import discord
from discord.ext import commands
from discord import app_commands

import db.controller as db
from utils.embed import CustomEmbed


class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="balance", description="Checks your balance")
    async def balance(self, interaction: discord.Interaction):
        balance = db.get_user_balance(interaction.user.id)
        embed = CustomEmbed(
            title="Balance",
            description=f"You have {balance} kartoffeln.\n-# Use **/transactions** to see your transaction history.",
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="transactions", description="Checks your transaction history")
    async def transactions(self, interaction: discord.Interaction):
        transactions = db.get_user_transactions(interaction.user.id, limit=10)
        if not transactions:
            embed = CustomEmbed(title="Transactions", description="You have no transaction history.")
            await interaction.response.send_message(embed=embed)
            return

        message = "Your last 10 transactions:\n"
        for tx in transactions:
            message += f"-# [ **{'+' if tx.amount >= 0 else '-'}{abs(tx.amount)}** ]\t *{tx.source}* \n"
        embed = CustomEmbed(title="Transactions", description=message)
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Economy(bot))
