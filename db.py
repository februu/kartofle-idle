import os
from sqlalchemy import create_engine, ForeignKey, func, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, Session

_db_path = os.getenv("SQLITE_PATH", ":memory:")
engine = create_engine(f"sqlite:///{_db_path}")


class Base(DeclarativeBase):
    pass


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column("transaction_id", primary_key=True)
    user_id: Mapped[int]
    amount: Mapped[float]
    timestamp: Mapped[str] = mapped_column(server_default=text("(datetime('now'))"))
    source: Mapped[str]
    source_id: Mapped[int]


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column("job_id", primary_key=True)
    title: Mapped[str]
    description: Mapped[str | None]
    amount: Mapped[float]
    duration_seconds: Mapped[int]


class JobLog(Base):
    __tablename__ = "job_log"

    id: Mapped[int] = mapped_column("log_id", primary_key=True)
    user_id: Mapped[int]
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.job_id"))
    end_time: Mapped[str]
    collected: Mapped[int] = mapped_column(default=0)


class PassiveIncome(Base):
    __tablename__ = "passive_income"

    id: Mapped[int] = mapped_column("income_id", primary_key=True)
    user_id: Mapped[int]
    title: Mapped[str]
    description: Mapped[str | None]
    amount_per_second: Mapped[float]


class Game(Base):
    __tablename__ = "games"

    id: Mapped[int] = mapped_column("game_id", primary_key=True)
    message_id: Mapped[int] = mapped_column(default=0)
    title: Mapped[str]
    description: Mapped[str | None]
    resolved: Mapped[bool] = mapped_column(default=False)

    options: Mapped[list["Option"]] = relationship(back_populates="game", cascade="all, delete-orphan")
    bets: Mapped[list["Bet"]] = relationship(back_populates="game", cascade="all, delete-orphan")


class Option(Base):
    __tablename__ = "options"

    id: Mapped[int] = mapped_column("option_id", primary_key=True)
    description: Mapped[str]
    game_id: Mapped[int] = mapped_column(ForeignKey("games.game_id"))

    game: Mapped["Game"] = relationship(back_populates="options")


class Bet(Base):
    __tablename__ = "bets"

    id: Mapped[int] = mapped_column("bet_id", primary_key=True)
    user_id: Mapped[int]
    game_id: Mapped[int] = mapped_column(ForeignKey("games.game_id"))
    amount: Mapped[float]
    option_id: Mapped[int] = mapped_column(ForeignKey("options.option_id"))

    game: Mapped["Game"] = relationship(back_populates="bets")


Base.metadata.create_all(engine)


# --- GET ---


def get_user_balance(user_id: int) -> float:
    with Session(engine) as s:
        result = s.execute(select(func.coalesce(func.sum(Transaction.amount), 0)).where(Transaction.user_id == user_id))
        return result.scalar_one()


def get_game_by_message_id(message_id: int) -> Game | None:
    with Session(engine) as s:
        return s.query(Game).filter_by(message_id=message_id).first()


def get_open_games() -> list[Game]:
    with Session(engine) as s:
        return s.query(Game).filter_by(resolved=False).all()


def get_game_by_id(game_id: int) -> Game | None:
    with Session(engine) as s:
        return s.get(Game, game_id)


def get_options_for_game(game_id: int) -> list[Option]:
    with Session(engine) as s:
        return s.query(Option).filter_by(game_id=game_id).all()


def get_betters_for_option(game_id: int, option_id: int) -> list[int]:
    with Session(engine) as s:
        return list(s.scalars(select(Bet.user_id).filter_by(game_id=game_id, option_id=option_id)).all())


# --- CREATE ---


def create_game(title: str, description: str, options: list[str]) -> int:
    with Session(engine) as s:
        game = Game(title=title, description=description, options=[Option(description=opt) for opt in options])
        s.add(game)
        s.flush()
        game_id = game.id
        s.commit()
        return game_id


def create_bet(user_id: int, game_id: int, option_id: int, amount: float) -> int:
    with Session(engine) as s:
        bet = Bet(user_id=user_id, game_id=game_id, option_id=option_id, amount=amount)
        s.add(bet)
        s.commit()
        s.flush()
        return bet.id


def create_transaction(user_id: int, amount: float, source: str, source_id: int):
    with Session(engine) as s:
        transaction = Transaction(user_id=user_id, amount=amount, source=source, source_id=source_id)
        s.add(transaction)
        s.commit()


def create_winning_transactions(game_id: int, winning_option_id: int):
    with Session(engine) as s:
        live_game = s.get(Game, game_id)
        if not live_game:
            return

        winners = s.query(Bet.user_id, Bet.amount).filter_by(game_id=live_game.id, option_id=winning_option_id).all()
        amount_of_options = s.execute(
            select(func.coalesce(func.count(Option.id), 0)).where(Option.game_id == live_game.id)
        ).scalar_one()

        s.add_all(
            [
                Transaction(
                    user_id=user_id,
                    amount=amount * amount_of_options,
                    source=f"Won bet on {live_game.title}#{live_game.id}",
                    source_id=live_game.id,
                )
                for user_id, amount in winners
            ]
        )

        live_game.resolved = True
        s.commit()


def create_refund_transactions_for_bets(game_id: int):
    with Session(engine) as s:
        live_game = s.get(Game, game_id)
        if not live_game or live_game.resolved:
            return
        bets = s.query(Bet.user_id, Bet.amount).filter_by(game_id=game_id).all()
        s.add_all(
            [
                Transaction(
                    user_id=user_id,
                    amount=amount,
                    source=f"Refund for cancelled game {live_game.title}#{live_game.id}",
                    source_id=game_id,
                )
                for user_id, amount in bets
            ]
        )
        live_game.resolved = True
        s.commit()


# --- UPDATE ---


def update_game_message_id(game_id: int, message_id: int):
    with Session(engine) as s:
        game = s.get(Game, game_id)
        if game:
            game.message_id = message_id
            s.commit()


create_transaction(user_id=175652881456693249, amount=1000, source="init", source_id=0)
