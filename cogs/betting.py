import math

import discord
from discord.ext import commands
from discord import app_commands
from utils.checks import is_admin, is_sent_in_guild
import db.controller as db

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


async def place_bet(interaction: discord.Interaction, game_id: int, option_id: int, amount: float):
    """Handles the logic for placing a bet, including validation and database updates."""
    game = db.get_game_by_id(int(game_id))
    if not game:
        await interaction.response.send_message("Game not found.", ephemeral=True)
        return

    if game.resolved:
        await interaction.response.send_message("This game was already resolved.", ephemeral=True)
        return

    options = db.get_options_for_game(game_id)
    selected_option = next((opt for opt in options if opt.id == option_id), None)
    if not selected_option:
        await interaction.response.send_message("Option not found.", ephemeral=True)
        return

    amount = math.floor(amount * 100) / 100
    balance = db.get_user_balance(interaction.user.id)
    if balance < amount:
        await interaction.response.send_message("You don't have enough balance to place this bet.", ephemeral=True)
        return

    bet_id = db.create_bet(interaction.user.id, game_id, option_id, amount)
    db.create_transaction(
        interaction.user.id,
        -amount,
        f"Bet on game {game.title}#{game.id}, option {selected_option.description}",
        bet_id,
    )
    await interaction.response.send_message(
        f"<@{interaction.user.id}> bet **{amount}** on option **{selected_option.description}** for game **{game.title}**."
    )


async def create_game(interaction: discord.Interaction, title: str, description: str, options: list[str]):
    """Handles the logic for creating a betting game, including validation and database updates."""
    parsed_options = [opt.strip() for opt in options if opt.strip()]
    if len(parsed_options) < 2 or len(parsed_options) < len(set(parsed_options)):
        await interaction.response.send_message(
            "You must provide at least 2 options. All options must be unique.", ephemeral=True
        )
        return
    game_id = db.create_game(title, description, parsed_options)
    await interaction.response.send_message(f"**{title}**\n{description}\nOptions: {', '.join(options)}")
    message = await interaction.original_response()
    db.update_game_message_id(game_id, message.id)


async def settle_game(interaction: discord.Interaction, id: int, winning_option: int):
    """Handles the logic for settling a betting game, including validation and database updates."""
    game = db.get_game_by_id(id)
    if not game:
        await interaction.response.send_message("Game not found.", ephemeral=True)
        return
    db.create_winning_transactions(game.id, winning_option)
    options = db.get_options_for_game(game.id)
    winning_option_description = next(
        (opt.description for opt in options if opt.id == winning_option), "Unknown option"
    )
    winners = db.get_betters_for_option(game.id, winning_option)
    await interaction.response.send_message(
        f"**{game.title}** has been settled. Winning option: {winning_option_description}. Winners: {', '.join(f'<@{winner}>' for winner in winners) if winners else 'No winners'}."
    )


async def remove_betting_game(channel: discord.abc.Messageable, message_id: int):
    """Handles the logic for removing a betting game when its message is deleted, including refunding bets and updating the database."""
    game = db.get_game_by_message_id(message_id)
    if game and not game.resolved:
        db.create_refund_transactions_for_bets(game.id)
        db.delete_game(game.id)
        await channel.send(f"Betting game **{game.title}** has been removed and all bets have been refunded.")


### ---------------------------------------------- ###
###                 Betting Cog                    ###
### ---------------------------------------------- ###


class BettingCog(commands.Cog):
    def __init__(self, bot):
        self.bot: commands.Bot = bot

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
        await create_game(interaction, title, description, options.split(","))

    @app_commands.command(name="settle", description="[ADMIN ONLY] Settle a betting game")
    @app_commands.describe(game="The betting game to settle", winning_option="The winning option")
    @app_commands.autocomplete(game=autocomplete_games, winning_option=autocomplete_game_options)
    async def settle_game(self, interaction: discord.Interaction, game: int, winning_option: int):
        if not is_sent_in_guild(interaction):
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        if not is_admin(interaction.user):
            await interaction.response.send_message("You lack permissions, what a shame...", ephemeral=True)
            return
        await settle_game(interaction, game, winning_option)

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent):
        channel = self.bot.get_channel(payload.channel_id) or await self.bot.fetch_channel(payload.channel_id)
        assert isinstance(channel, discord.abc.Messageable)
        await remove_betting_game(channel, payload.message_id)


async def setup(bot: commands.Bot):
    await bot.add_cog(BettingCog(bot))
