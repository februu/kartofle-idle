import discord
from discord import app_commands

from config import config


def admin_only():
    """A decorator that checks if the user is an admin."""

    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.user.id not in config.admin_ids:
            await interaction.response.send_message("You lack permissions, what a shame...", ephemeral=True)
            raise app_commands.CheckFailure()
        return True

    return app_commands.check(predicate)


def guild_only():
    """A decorator that checks if the command is used in a guild."""

    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.guild_id is None:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return False
        return True

    return app_commands.check(predicate)
