"""SQLite persistence via SQLAlchemy 2.x."""
from datetime import datetime, date

from sqlalchemy import (Boolean, Column, Date, DateTime, Float, Integer, String,
                        create_engine)
from sqlalchemy.orm import declarative_base, sessionmaker

import config

_connect_args = {"check_same_thread": False} if config.DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(config.DATABASE_URL, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


class Farmer(Base):
    __tablename__ = "farmers"
    id = Column(String, primary_key=True)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    crop_type = Column(String, nullable=False)
    planting_date = Column(Date, nullable=False)
    crop_height_cm = Column(Float, default=0)
    watering_days_per_week = Column(Float, default=0)
    irrigation_type = Column(String, default="")
    avg_watering_minutes = Column(Float, default=0)
    fertilizer_used = Column(Boolean, default=False)
    fertilizer_amount = Column(String, default="")
    phone = Column(String, default="")  # optional extra, used only for SMS
    created_at = Column(DateTime, default=datetime.utcnow)


class CropCondition(Base):
    """Latest pest/disease input. source = 'photo' (endpoint 2) or 'manual' (endpoint 3)."""
    __tablename__ = "crop_conditions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    farmer_id = Column(String, index=True, nullable=False)
    source = Column(String, nullable=False)
    condition = Column(String, nullable=False)
    confidence = Column(Float, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class RecommendationLog(Base):
    """One row per farmer per day (today's row is updated on every call)."""
    __tablename__ = "recommendation_log"
    id = Column(Integer, primary_key=True, autoincrement=True)
    farmer_id = Column(String, index=True, nullable=False)
    day = Column(Date, nullable=False, default=date.today)
    action = Column(String, nullable=False)
    confidence_pct = Column(Integer, default=0)
    is_seed = Column(Boolean, default=False)  # True = demo filler, not a real past decision
    created_at = Column(DateTime, default=datetime.utcnow)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
