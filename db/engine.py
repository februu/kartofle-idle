from sqlalchemy import create_engine
from config import config

engine = create_engine(config.db_path)
