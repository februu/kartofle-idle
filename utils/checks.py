import os
import discord
from discord import app_commands

_ADMINS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",")]


# NOTE: Remove those redundant checks below, use decotators instead
def is_admin(user: discord.User | discord.Member) -> bool:
    """Checks if the user is an admin based on their ID."""
    return user.id in _ADMINS


def is_sent_in_guild(interaction: discord.Interaction) -> bool:
    """Checks if the interaction was sent in a guild."""
    return interaction.guild_id is not None


def admin_only():
    """A decorator that checks if the user is an admin."""

    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.user.id not in _ADMINS:
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
