from sqlalchemy import Column, Integer, String, Float, Date, DateTime
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class State(Base):
    __tablename__ = "state"

    id = Column(Integer, primary_key=True)
    units = Column(String, default="kg")  # "kg" or "lb"

    # 1RMs stored in kg
    bench = Column(Float, nullable=True)
    squat = Column(Float, nullable=True)
    deadlift = Column(Float, nullable=True)
    ohp = Column(Float, nullable=True)


class Log(Base):
    __tablename__ = "log"

    id = Column(Integer, primary_key=True)
    week = Column(Integer)
    day = Column(Integer)
    day_title = Column(String)

    exercise = Column(String)
    sets = Column(Integer)
    rep_low = Column(Integer)
    rep_high = Column(Integer)
    category = Column(String)        # "compound" or "accessory"
    increment = Column(Float)        # weight increment for progression

    load_last = Column(Float, nullable=True)   # weight used THIS week (kg)
    new_load = Column(Float, nullable=True)    # suggested for next week (kg)

    s1 = Column(Integer, nullable=True)
    s2 = Column(Integer, nullable=True)
    s3 = Column(Integer, nullable=True)

    notes = Column(String, nullable=True)

    # AMRAP is now UNUSED but remains for compatibility (ignore it)
    amrap = Column(Integer, nullable=True)


class Progress(Base):
    __tablename__ = "progress"

    id = Column(Integer, primary_key=True)
    week = Column(Integer)
    bodyweight = Column(Float)  # stored in kg


class WorkoutSession(Base):
    __tablename__ = "workout_sessions"

    id = Column(Integer, primary_key=True)

    week = Column(Integer)
    day = Column(Integer)
    session_date = Column(Date)

    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)


class PRHistory(Base):
    __tablename__ = "pr_history"

    id = Column(Integer, primary_key=True)
    session_date = Column(Date)
    week = Column(Integer)
    day = Column(Integer)

    lift_key = Column(String)   # "bench", "squat", "deadlift", "ohp"
    pr_kg = Column(Float)       # PR always stored in kg