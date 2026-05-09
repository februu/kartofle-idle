import discord
from discord.ext import commands
from discord import app_commands
import os

import db as db

### ---------------------------------------------- ###
###  Helper functions and logic for betting games  ###
### ---------------------------------------------- ###


async def autocomplete_games(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    """Returns open betting games as autocomplete choices."""
    games = db.get_open_games()
    return [
        app_commands.Choice(name=game.title, value=str(game.id))
        for game in games
        if current.lower() in game.title.lower()
    ][:25]


async def autocomplete_game_options(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    """Returns options for the game selected in the previous argument."""
    game_id = interaction.namespace.game
    if not game_id:
        return []
    options = db.get_options_for_game(int(game_id))
    if not options:
        return []
    return [
        app_commands.Choice(name=option.description, value=str(option.id))
        for option in options
        if current.lower() in option.description.lower()
    ][:25]


_ADMINS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",")]


def is_admin(user: discord.User | discord.Member) -> bool:
    """Checks if the user is an admin based on their ID."""
    return user.id in _ADMINS


def is_sent_in_guild(interaction: discord.Interaction) -> bool:
    """Checks if the interaction was sent in a guild."""
    return interaction.guild_id is not None


async def place_bet(interaction: discord.Interaction, game_id: int, option_id: int, amount: float):
    game = db.get_game_by_id(int(game_id))
    if not game:
        await interaction.response.send_message("Game not found.", ephemeral=True)
        return
    option = db.get_options_for_game(game_id)
    if option_id not in [opt.id for opt in option]:
        await interaction.response.send_message("Option not found.", ephemeral=True)
        return
    balance = db.get_user_balance(interaction.user.id)
    if balance < amount:
        await interaction.response.send_message("You don't have enough balance to place this bet.", ephemeral=True)
        return
    bet_id = db.create_bet(interaction.user.id, game_id, option_id, amount)
    db.create_transaction(interaction.user.id, -amount, f"Bet on game {game_id}, option {option_id}", bet_id)
    await interaction.response.send_message(
        f"Bet placed: {amount} on option {option[option_id].description} for game {game.description}."
    )
    # TODO: Fix option[option_id]


async def create_game(interaction: discord.Interaction, title, description, options):
    game_id = db.create_game(title, description, options)
    message = await interaction.response.send_message(f"**{title}**\n{description}\nOptions: {', '.join(options)}")
    db.update_game_message_id(game_id, message.id)


async def settle_game(interaction: discord.Interaction, id, winning_option):
    # find game by id
    game = db.find_game_by_id(id)
    if not game:
        await interaction.response.send_message("Game not found.", ephemeral=True)
        return
    # create transactions for all winning bets
    db.create_winning_transactions(game, winning_option)
    # edit message to show that the game is settled and what the winning option was
    await interaction.response.send_message(f"game has been settled. Winning option: {winning_option}")


async def remove_betting_game(message_id):
    if db.remove_game_by_message_id(message_id):
        # TODO: Return money to all players who placed bets on this game
        ...


### ---------------------------------------------- ###
###                 Betting Cog                    ###
### ---------------------------------------------- ###


class BettingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="bet", description="Place a bet")
    @app_commands.describe(
        game="The betting game to place a bet on",
        option="The option you want to bet on",
        amount="The amount of currency to bet",
    )
    @app_commands.autocomplete(game=autocomplete_games, option=autocomplete_game_options)
    async def place_bet(self, interaction: discord.Interaction, game: int, option: int, amount: float):
        if not is_sent_in_guild(interaction):
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        await place_bet(interaction, game, option, amount)

    @app_commands.command(name="create_game", description="[ADMIN ONLY] Create a betting game")
    @app_commands.describe(
        title="Title of the betting game",
        description="Description of the betting game",
        options="Comma-separated list of options (e.g. Option 1,Option 2,Option 3)",
    )
    async def create_game(self, interaction: discord.Interaction, title: str, description: str, options: str):
        if not is_sent_in_guild(interaction):
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        if not is_admin(interaction.user):
            await interaction.response.send_message("You lack permissions, what a shame...", ephemeral=True)
            return
        parsed_options = [opt.strip() for opt in options.split(",") if opt.strip()]
        if len(parsed_options) < 2:
            await interaction.response.send_message("Please provide at least 2 options.", ephemeral=True)
            return
        await create_game(interaction, title, description, parsed_options)

    @app_commands.command(name="settle", description="[ADMIN ONLY] Settle a betting game")
    @app_commands.describe(game="The betting game to settle", winning_option="The winning option")
    @app_commands.autocomplete(game=autocomplete_games, winning_option=autocomplete_game_options)
    async def settle_game(self, interaction: discord.Interaction, game: str, winning_option: str):
        if not is_sent_in_guild(interaction):
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        if not is_admin(interaction.user):
            await interaction.response.send_message("You lack permissions, what a shame...", ephemeral=True)
            return
        await settle_game(interaction, game, winning_option)


async def setup(bot: commands.Bot):
    await bot.add_cog(BettingCog(bot))
