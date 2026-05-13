import math
import discord
from discord.ext import commands
from discord import app_commands

from utils.checks import is_admin, is_sent_in_guild
from utils.embed import CustomEmbed
import db.controller as db

### ---------------------------------------------- ###
###                 UI Components                  ###
### ---------------------------------------------- ###


class PlaceBetModal(discord.ui.Modal, title="Place your bet"):
    amount = discord.ui.TextInput(
        label="Amount to bet",
        style=discord.TextStyle.short,
        required=True,
    )

    def __init__(self, game_id: int, option_id: int, user_balance: float):
        super().__init__()
        self.game_id = game_id
        self.option_id = option_id
        self.user_balance = user_balance
        self.amount.placeholder = f"You currently have {user_balance} kartoffeln."

    async def on_submit(self, interaction: discord.Interaction):
        await place_bet(interaction, self.game_id, self.option_id, float(self.amount.value))

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(
            "An error occurred while processing your bet. Please try again.", ephemeral=True
        )


class OptionButton(discord.ui.Button):
    def __init__(self, label: str, game_id: int, option_id: int):
        super().__init__(label=label, style=discord.ButtonStyle.primary)
        self.game_id = game_id
        self.option_id = option_id

    async def callback(self, interaction: discord.Interaction):
        balance = db.get_user_balance(interaction.user.id)
        await interaction.response.send_modal(PlaceBetModal(self.game_id, self.option_id, balance))


class OptionButtonsView(discord.ui.View):
    def __init__(self, options: list, game_id: int):
        super().__init__(timeout=None)
        for option in options:
            self.add_item(OptionButton(label=option.description, game_id=game_id, option_id=option.id))


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

    if db.get_user_bet_for_game(interaction.user.id, game_id):
        await interaction.response.send_message("You already have a bet on this game.", ephemeral=True)
        return

    bet_id = db.create_bet(interaction.user.id, game_id, option_id, amount)
    db.create_transaction(
        interaction.user.id,
        -amount,
        f"Bet on game {game.title}#{game.id}, option {selected_option.description}",
        bet_id,
    )
    embed = CustomEmbed(
        title="Bet placed",
        description=f"<@{interaction.user.id}> placed a bet of **{amount}** kartoffeln.\n-# Game: **{game.title}** \n-# Option: **{selected_option.description}**",
    )
    await interaction.response.send_message(embed=embed)


async def create_game(interaction: discord.Interaction, title: str, description: str, option_list: list[str]):
    """Handles the logic for creating a betting game, including validation and database updates."""
    parsed_option_list = [opt.strip() for opt in option_list if opt.strip()]
    if len(parsed_option_list) < 2 or len(parsed_option_list) < len(set(parsed_option_list)):
        await interaction.response.send_message(
            "You must provide at least 2 options. All options must be unique.", ephemeral=True
        )
        return
    game_id = db.create_game(title, description, parsed_option_list)
    options = db.get_options_for_game(game_id)
    view = OptionButtonsView(options, game_id)
    embed = CustomEmbed(
        title=f"[#{game_id}] {title}", description=f"{description} \n-# Use the buttons below to place your bets!"
    )
    await interaction.response.send_message(embed=embed, view=view)
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
    embed = CustomEmbed(
        title="Game settled!",
        description=f"**{game.title}**\nWinning option: **{winning_option_description}**\n-# Winners: {' '.join(f'<@{winner}>' for winner in winners) if winners else 'no one won :('}",
    )
    await interaction.response.send_message(embed=embed)
    if game.message_id:
        try:
            channel = interaction.channel
            assert isinstance(channel, discord.abc.Messageable)
            message = await channel.fetch_message(game.message_id)
            view = OptionButtonsView([opt.description for opt in options], game.id)
            for item in view.children:
                if isinstance(item, discord.ui.Button):
                    item.disabled = True
            await message.edit(view=view)
        except discord.NotFound:
            pass


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
