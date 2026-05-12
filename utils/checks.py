import os
import discord

_ADMINS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",")]


def is_admin(user: discord.User | discord.Member) -> bool:
    """Checks if the user is an admin based on their ID."""
    return user.id in _ADMINS


def is_sent_in_guild(interaction: discord.Interaction) -> bool:
    """Checks if the interaction was sent in a guild."""
    return interaction.guild_id is not None
