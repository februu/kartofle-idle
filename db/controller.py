import os
from datetime import datetime
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .engine import engine
from .schema import Bet, Game, Option, Transaction, Job, JobLog, PassiveIncome
from .init import init_db, init_dev_db


### ---------------------------------------------- ###
###    Helper functions for database operations    ###
### ---------------------------------------------- ###


def _get_current_time_iso() -> str:
    """Get current time in ISO format without microseconds for consistent DB storage and comparison."""
    return datetime.now().replace(microsecond=0).isoformat()


def settle_unfinished_jobs():
    """Checks for any jobs that should have been completed by now and settles them by creating transactions."""
    with Session(engine) as s:
        now_iso = _get_current_time_iso()
        unfinished_job_logs = s.query(JobLog).filter(JobLog.end_time <= now_iso, JobLog.collected == 0).all()

        for job_log in unfinished_job_logs:
            job = s.get(Job, job_log.job_id)
            if job:
                create_transaction(
                    user_id=job_log.user_id,
                    amount=job.amount,
                    source=f"Completed job: {job.title}",
                    source_id=job.id,
                )

            update_job_log_collected(job_log.id)


def settle_passive_income():
    """Settles all passive income by calculating earned amount based on time elapsed since last settlement."""
    from datetime import datetime as dt

    with Session(engine) as s:
        now_iso = _get_current_time_iso()
        passive_incomes = s.query(PassiveIncome).all()

        for passive in passive_incomes:
            last_settled = dt.fromisoformat(passive.last_settled)
            now = dt.fromisoformat(now_iso)

            seconds_elapsed = (now - last_settled).total_seconds()
            earned_amount = seconds_elapsed * passive.amount_per_second

            if earned_amount > 0:
                create_transaction(
                    user_id=passive.user_id,
                    amount=earned_amount,
                    source=f"Passive income: {passive.title}",
                    source_id=passive.id,
                )

            passive.last_settled = now_iso

        s.commit()


DEV = os.getenv("DEV", "").lower() in {"1", "true", "yes", "on"}

init_db()
if DEV:
    init_dev_db()


# --- GET ---


def get_user_balance(user_id: int) -> float:
    settle_unfinished_jobs()
    settle_passive_income()
    with Session(engine) as s:
        result = s.execute(select(func.coalesce(func.sum(Transaction.amount), 0)).where(Transaction.user_id == user_id))
        return result.scalar_one()


def get_user_transactions(user_id: int, limit: int = 10) -> list[Transaction]:
    settle_unfinished_jobs()
    settle_passive_income()
    with Session(engine) as s:
        return (
            s.query(Transaction)
            .filter(Transaction.user_id == user_id)
            .order_by(Transaction.timestamp.asc())
            .limit(limit)
            .all()
        )


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
        return [user_id for (user_id,) in s.query(Bet.user_id).filter_by(game_id=game_id, option_id=option_id).all()]


def get_user_bet_for_game(user_id: int, game_id: int) -> Bet | None:
    with Session(engine) as s:
        return s.query(Bet).filter_by(user_id=user_id, game_id=game_id).first()


def get_jobs() -> list[Job]:
    with Session(engine) as s:
        return s.query(Job).all()


def get_job_by_id(job_id: int) -> Job | None:
    with Session(engine) as s:
        return s.get(Job, job_id)


def get_unassigned_jobs() -> list[Job]:
    with Session(engine) as s:
        now_iso = _get_current_time_iso()
        active_job_exists = select(JobLog.job_id).where(
            JobLog.job_id == Job.id,
            JobLog.end_time > now_iso,
        )
        return s.query(Job).where(~active_job_exists.exists()).all()


def get_active_job_log_by_user(user_id: int) -> JobLog | None:
    with Session(engine) as s:
        now_iso = _get_current_time_iso()
        job_log = (
            s.query(JobLog)
            .filter(JobLog.user_id == user_id, JobLog.end_time > now_iso)
            .order_by(JobLog.end_time.desc())
            .first()
        )
        if not job_log:
            return None

        return job_log


def get_active_jobs() -> list[Job]:
    with Session(engine) as s:
        now_iso = _get_current_time_iso()
        active_job_logs = s.query(JobLog.job_id.distinct()).filter(JobLog.end_time > now_iso).all()
        if not active_job_logs:
            return []
        job_ids = [log[0] for log in active_job_logs]
        return s.query(Job).filter(Job.id.in_(job_ids)).all()


def get_job_logs() -> list[JobLog]:
    with Session(engine) as s:
        return s.query(JobLog).all()


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


def create_job_log(user_id: int, job_id: int, end_time: str):
    with Session(engine) as s:
        s.add(
            JobLog(
                user_id=user_id,
                job_id=job_id,
                end_time=end_time,
            )
        )
        s.commit()


def create_passive_income(user_id: int, title: str, description: str | None, amount_per_second: float) -> int:
    """Creates a passive income stream for a user. Returns the income_id."""
    with Session(engine) as s:
        passive = PassiveIncome(
            user_id=user_id,
            title=title,
            description=description,
            amount_per_second=amount_per_second,
            last_settled=_get_current_time_iso(),
        )
        s.add(passive)
        s.flush()
        income_id = passive.id
        s.commit()
        return income_id


# --- UPDATE ---


def update_game_message_id(game_id: int, message_id: int):
    with Session(engine) as s:
        game = s.get(Game, game_id)
        if game:
            game.message_id = message_id
            s.commit()


def update_job_log_collected(log_id: int):
    with Session(engine) as s:
        job_log = s.get(JobLog, log_id)
        if job_log:
            job_log.collected = 1
            s.commit()


# --- DELETE ---


def delete_game(game_id: int):
    with Session(engine) as s:
        game = s.get(Game, game_id)
        if game:
            s.delete(game)
            s.commit()
