import os
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db_schema import Bet, Base, Game, Job, JobLog, Option, PassiveIncome, Transaction, engine
from init_db import init_db, init_dev_db

DEV = os.getenv("DEV", "").lower() in {"1", "true", "yes", "on"}


# --- public API ---


def get_user_balance(user_id) -> float:
    with Session(engine) as s:
        result = s.execute(select(func.coalesce(func.sum(Transaction.amount), 0)).where(Transaction.user_id == user_id))
        return result.scalar_one()


def create_game(title, description, options) -> int:
    with Session(engine) as s:
        game = Game(title=title, description=description, options=[Option(description=opt) for opt in options])
        s.add(game)
        s.flush()
        game_id = game.id
        s.commit()
        return game_id


def update_game_message_id(game_id, message_id):
    with Session(engine) as s:
        game = s.get(Game, game_id)
        if game:
            game.message_id = message_id
            s.commit()


def remove_game_by_message_id(message_id) -> bool:
    with Session(engine) as s:
        game = s.query(Game).filter_by(message_id=message_id).first()
        if not game:
            return False
        s.delete(game)
        s.commit()
        return True


def find_game_by_id(game_id) -> Game | None:
    with Session(engine) as s:
        return s.get(Game, game_id)


def create_winning_transactions(game: Game, winning_option_id: int):
    with Session(engine) as s:
        live_game = s.get(Game, game.id)
        if not live_game:
            return

        total_pot: float = s.execute(
            select(func.coalesce(func.sum(Bet.amount), 0)).where(Bet.game_id == live_game.id)
        ).scalar_one()

        winning_pool: float = s.execute(
            select(func.coalesce(func.sum(Bet.amount), 0)).where(
                Bet.game_id == live_game.id, Bet.option_id == winning_option_id
            )
        ).scalar_one()

        if winning_pool > 0:
            winners = (
                s.query(Bet.user_id, Bet.amount).filter_by(game_id=live_game.id, option_id=winning_option_id).all()
            )
            s.add_all(
                [
                    Transaction(
                        user_id=user_id,
                        amount=(amount / winning_pool) * total_pot,
                        source="game",
                        source_id=live_game.id,
                    )
                    for user_id, amount in winners
                ]
            )

        live_game.resolved = True
        s.commit()


def get_open_games() -> list[Game]:
    with Session(engine) as s:
        return s.query(Game).filter_by(resolved=False).all()


def get_game_by_id(game_id) -> Game | None:
    with Session(engine) as s:
        return s.get(Game, game_id)


def get_options_for_game(game_id) -> list[Option]:
    with Session(engine) as s:
        return s.query(Option).filter_by(game_id=game_id).all()


def create_bet(user_id, game_id, option_id, amount) -> int:
    with Session(engine) as s:
        bet = Bet(user_id=user_id, game_id=game_id, option_id=option_id, amount=amount)
        s.add(bet)
        s.commit()
        s.flush()
        return bet.id


def create_transaction(user_id, amount, source, source_id):
    with Session(engine) as s:
        transaction = Transaction(user_id=user_id, amount=amount, source=source, source_id=source_id)
        s.add(transaction)
        s.commit()


init_db()
if DEV:
    init_dev_db()
