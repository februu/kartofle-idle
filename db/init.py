from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .engine import engine
from .schema import Job, Transaction, PassiveIncome

# To refactor in future
from datetime import datetime


def _get_current_time_iso() -> str:
    """Get current time in ISO format without microseconds for consistent DB storage and comparison."""
    return datetime.now().replace(microsecond=0).isoformat()


def init_db() -> None:
    with Session(engine) as session:
        jobs_count = session.execute(select(func.count()).select_from(Job)).scalar_one()
        if jobs_count:
            return

        session.add_all(
            [
                Job(
                    title="Kartofel Farmer",
                    description="Zbierasz kartofle na polu i sprzedajesz je na targu.",
                    amount=25.0,
                    duration_seconds=5,
                ),
                Job(
                    title="Skladacz Skrzynek",
                    description="Układasz kartofle w skrzynkach do wysyłki.",
                    amount=40.0,
                    duration_seconds=10,
                ),
                Job(
                    title="Nocny Dostawca",
                    description="Dostarczasz kartofle do sklepu po zmroku.",
                    amount=60.0,
                    duration_seconds=15,
                ),
                PassiveIncome(
                    user_id=313026957044350977,
                    title="Kartofelowy Plantator",
                    description="Posiadasz własne pole kartofli, które generuje dochód pasywny.",
                    amount_per_second=0.5,
                    last_settled=_get_current_time_iso(),
                ),
            ]
        )
        session.commit()


def init_dev_db() -> None:
    with Session(engine) as session:
        transactions_count = session.execute(select(func.count()).select_from(Transaction)).scalar_one()
        if transactions_count:
            return

        session.add_all(
            [
                Transaction(user_id=313026957044350977, amount=2000.0, source="dev_seed", source_id=1),
                Transaction(user_id=175652881456693249, amount=2000.0, source="dev_seed", source_id=2),
                Transaction(user_id=3, amount=-45.0, source="dev_seed", source_id=3),
            ]
        )
        session.commit()
