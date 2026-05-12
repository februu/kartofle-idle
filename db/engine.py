import os

from sqlalchemy import create_engine

_db_path = os.getenv("SQLITE_PATH", ":memory:")
engine = create_engine(f"sqlite:///{_db_path}")
