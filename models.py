from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Integer, Float, Text, JSON, UniqueConstraint

class Base(DeclarativeBase):
    pass

class State(Base):
    __tablename__ = "state"
    id: Mapped[int] = mapped_column(primary_key=True)
    units: Mapped[str] = mapped_column(String(4), default="kg")
    rms: Mapped[dict] = mapped_column(JSON, default={"squat": None, "bench": None, "deadlift": None, "ohp": None})

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
