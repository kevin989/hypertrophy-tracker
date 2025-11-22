from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Integer, Float, Text, JSON, UniqueConstraint, Date, TIMESTAMP, BigInteger, DateTime, Column
from datetime import datetime, timezone

class Base(DeclarativeBase):
    pass

class State(Base):
    __tablename__ = "state"
    id = Column(Integer, primary_key=True)

    units = Column(String, default="kg")

    # Store 1RMs in kg (NULL = not set)
    bench = Column(Float, nullable=True)
    squat = Column(Float, nullable=True)
    deadlift = Column(Float, nullable=True)
    ohp = Column(Float, nullable=True)

class Log(Base):
    __tablename__ = "log"
    id: Mapped[int] = mapped_column(primary_key=True)
    week: Mapped[int] = mapped_column(Integer, index=True)
    day: Mapped[int] = mapped_column(Integer, index=True)
    day_title: Mapped[str] = mapped_column(String(100))
    exercise: Mapped[str] = mapped_column(String(80), index=True)
    sets: Mapped[int] = mapped_column(Integer)
    rep_low: Mapped[int] = mapped_column(Integer)
    rep_high: Mapped[int] = mapped_column(Integer)
    category: Mapped[str] = mapped_column(String(20))   # compound/accessory
    increment: Mapped[float] = mapped_column(Float)

    load_last: Mapped[float | None] = mapped_column(Float, nullable=True)
    s1: Mapped[int | None] = mapped_column(Integer, nullable=True)
    s2: Mapped[int | None] = mapped_column(Integer, nullable=True)
    s3: Mapped[int | None] = mapped_column(Integer, nullable=True)
    amrap: Mapped[int | None] = mapped_column(Integer, nullable=True)
    new_load: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (UniqueConstraint("week","day","exercise", name="uq_week_day_exercise"),)

class Progress(Base):
    __tablename__ = "progress"
    id: Mapped[int] = mapped_column(primary_key=True)
    week: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    bodyweight: Mapped[float] = mapped_column(Float)

class WorkoutSession(Base):
    __tablename__ = "workout_session"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    week: Mapped[int] = mapped_column(Integer, nullable=False)
    day: Mapped[int] = mapped_column(Integer, nullable=False)
    session_date = mapped_column(Date, nullable=False)  # e.g., 2025-09-22 (local date is fine)
    started_at = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    ended_at   = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=True)

class PRHistory(Base):
    __tablename__ = "pr_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # 'bench', 'squat', 'deadlift', 'ohp'
    lift_key: Mapped[str] = mapped_column(String(20))

    # 1RM estimate in kg at time of PR (Epley)
    pr_kg: Mapped[float] = mapped_column(Float)

    # Context
    week: Mapped[int] = mapped_column(Integer)
    day: Mapped[int] = mapped_column(Integer)
    session_date: Mapped[Date] = mapped_column(Date)

    # Timestamp of when PR was recorded
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )