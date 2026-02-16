from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, BigInteger
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    username = Column(String, nullable=True)
    google_token = Column(String, nullable=True)


class Deadline(Base):
    __tablename__ = "deadlines"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    course_name = Column(String, nullable=False)
    title = Column(String, nullable=False)
    due_date = Column(DateTime, nullable=False)
    link = Column(String, nullable=True)
    external_id = Column(String, unique=True, nullable=False)
    notified = Column(Boolean, default=False)
    # New fields for enhancements
    completed = Column(Boolean, default=False)
    priority = Column(String, default='medium')  # 'low', 'medium', 'high'
    reminder_1day = Column(Boolean, default=False)  # Reminder sent 1 day before
    reminder_3hours = Column(Boolean, default=False)  # Reminder sent 3 hours before
    reminder_1hour = Column(Boolean, default=False)  # Reminder sent 1 hour before


class Coursework(Base):
    __tablename__ = "coursework"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    course_name = Column(String, nullable=False)
    title = Column(String, nullable=False)
    link = Column(String, nullable=True)
    external_id = Column(String, unique=True, nullable=False)


class UserSettings(Base):
    __tablename__ = "user_settings"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, unique=True, nullable=False)
    auto_sync_enabled = Column(Boolean, default=True)
    auto_sync_interval = Column(Integer, default=6)  # hours
    remind_1day = Column(Boolean, default=True)
    remind_3hours = Column(Boolean, default=True)
    remind_1hour = Column(Boolean, default=True)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    return SessionLocal()
