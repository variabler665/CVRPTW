import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session, declarative_base

DB_PATH = os.environ.get("APP_DB_PATH", os.path.join(os.path.dirname(__file__), "..", "data", "app.db"))
os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
engine = create_engine(f"sqlite:///{os.path.abspath(DB_PATH)}", connect_args={"check_same_thread": False})
SessionLocal = scoped_session(sessionmaker(bind=engine))
Base = declarative_base()

def get_session():
    return SessionLocal()
