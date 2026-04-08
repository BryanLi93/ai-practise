from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from collections.abc import Generator 
import os
from dotenv import load_dotenv

load_dotenv()  # 读取 .env 文件
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://dev:devpass@localhost:5432/ai_registry")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    Base.metadata.create_all(bind=engine)