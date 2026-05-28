from dataclasses import dataclass, field
from dotenv import load_dotenv
import os

load_dotenv()


@dataclass(frozen=True)
class Config:
    token: str
    guild_id: int
    admin_ids: list[int] = field(default_factory=list)
    db_path: str = "sqlite:///:memory:"
    dev: bool = False
    unique_jobs: bool = False


def require_env(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise SystemExit(f"Missing required env variable: {key}")
    return value


try:
    config = Config(
        token=require_env("TOKEN"),
        guild_id=int(require_env("GUILD_ID")),
        admin_ids=[int(uid) for uid in require_env("ADMIN_IDS").split(",") if uid.strip().isdigit()],
        db_path=require_env("DB_PATH"),
        dev=require_env("DEV").lower() in {"1", "true", "yes", "on"},
        unique_jobs=require_env("UNIQUE_JOBS").lower() in {"1", "true", "yes", "on"},
    )
except (ValueError, TypeError) as e:
    raise SystemExit(f"Config error: {e}")
