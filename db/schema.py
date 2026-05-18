from sqlalchemy import ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from .engine import engine


class Base(DeclarativeBase):
    pass


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column("transaction_id", primary_key=True)
    user_id: Mapped[int]
    amount: Mapped[float]
    timestamp: Mapped[str] = mapped_column(server_default="(datetime('now'))")
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
    collected: Mapped[int] = mapped_column(default=0, server_default="0")


class PassiveIncome(Base):
    __tablename__ = "passive_income"

    id: Mapped[int] = mapped_column("income_id", primary_key=True)
    user_id: Mapped[int]
    title: Mapped[str]
    description: Mapped[str | None]
    amount_per_second: Mapped[float]
    last_settled: Mapped[str] = mapped_column(default=None) 


class Game(Base):
    __tablename__ = "games"

    id: Mapped[int] = mapped_column("game_id", primary_key=True)
    message_id: Mapped[int | None] = mapped_column(default=None)
    title: Mapped[str]
    description: Mapped[str | None]
    resolved: Mapped[bool] = mapped_column(default=False, server_default="0")

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
