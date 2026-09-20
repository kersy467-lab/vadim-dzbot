from datetime import datetime, date
from typing import List, Optional
from sqlalchemy import (
    BigInteger, Integer, String, Boolean, DateTime, Date,
    ForeignKey, Text, JSON, UniqueConstraint
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    custom_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # Реальное имя, назначенное админом
    role: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)  # admin, student, pending, rejected
    is_tester: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="0")
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    canteen_reminder_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="0")
    currency_ecosystem_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="0")
    coins: Mapped[int] = mapped_column(BigInteger, default=100, nullable=False, server_default="100")
    last_work_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    homework_statuses: Mapped[List["UserHomeworkStatus"]] = relationship("UserHomeworkStatus", back_populates="user", cascade="all, delete-orphan")

    @property
    def display_name(self) -> str:
        return self.custom_name or self.full_name


class Subject(Base):
    __tablename__ = "subjects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    teacher_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    schedules: Mapped[List["Schedule"]] = relationship("Schedule", back_populates="subject")
    homeworks: Mapped[List["Homework"]] = relationship("Homework", back_populates="subject")
    deadlines: Mapped[List["Deadline"]] = relationship("Deadline", back_populates="subject")


class BellSchedule(Base):
    __tablename__ = "bell_schedule"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    specific_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True) # None = постоянное расписание звонков
    lesson_number: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[str] = mapped_column(String(10), nullable=False)  # "08:30"
    end_time: Mapped[str] = mapped_column(String(10), nullable=False)    # "09:10"
    break_duration: Mapped[Optional[int]] = mapped_column(Integer, default=10) # 10 mins



class Schedule(Base):
    __tablename__ = "schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    specific_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)  # None = постоянное расписание
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)  # 1 = Monday, 7 = Sunday
    lesson_number: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    end_time: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    subject_id: Mapped[int] = mapped_column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)

    subject: Mapped["Subject"] = relationship("Subject", back_populates="schedules")



class Substitution(Base):
    __tablename__ = "substitutions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    lesson_number: Mapped[int] = mapped_column(Integer, nullable=False)
    old_subject_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True)
    new_subject_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_cancelled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    old_subject: Mapped[Optional["Subject"]] = relationship("Subject", foreign_keys=[old_subject_id])
    new_subject: Mapped[Optional["Subject"]] = relationship("Subject", foreign_keys=[new_subject_id])


class Homework(Base):
    __tablename__ = "homeworks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subject_id: Mapped[int] = mapped_column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    due_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    assigned_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, default=date.today)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    attachments: Mapped[Optional[list]] = mapped_column(JSON, default=list, nullable=True)  # [{"type": "photo"/"doc", "file_id": "...", "file_name": "..."}]
    created_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    subject: Mapped["Subject"] = relationship("Subject", back_populates="homeworks")
    user_statuses: Mapped[List["UserHomeworkStatus"]] = relationship("UserHomeworkStatus", back_populates="homework", cascade="all, delete-orphan")


class Deadline(Base):
    __tablename__ = "deadlines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subject_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    due_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    created_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    subject: Mapped[Optional["Subject"]] = relationship("Subject", back_populates="deadlines")


class UserHomeworkStatus(Base):
    __tablename__ = "user_homework_statuses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    homework_id: Mapped[int] = mapped_column(Integer, ForeignKey("homeworks.id", ondelete="CASCADE"), nullable=False)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="homework_statuses")
    homework: Mapped["Homework"] = relationship("Homework", back_populates="user_statuses")


class Announcement(Base):
    __tablename__ = "announcements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    attachments: Mapped[Optional[list]] = mapped_column(JSON, default=list, nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class GroupChat(Base):
    __tablename__ = "group_chats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    chat_type: Mapped[str] = mapped_column(String(50), default="group", nullable=False)  # group, supergroup
    role: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)      # pending, approved, rejected
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    added_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    topic_hw_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    topic_schedule_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    topic_duty_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    topic_announcements_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


class DutyGroup(Base):
    __tablename__ = "duty_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_number: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)  # 1..N
    name: Mapped[str] = mapped_column(String(100), nullable=False)                  # "Группа 1"
    members: Mapped[str] = mapped_column(Text, nullable=False)                      # "Иванов И., Петров П."
    member_ids: Mapped[Optional[list]] = mapped_column(JSON, default=list, nullable=True)  # [tg_id1, tg_id2]
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class ClassSetting(Base):
    __tablename__ = "class_settings"

    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)


class DailyFact(Base):
    __tablename__ = "daily_facts"
    __table_args__ = (UniqueConstraint("date", "hour", "minute", name="uq_daily_facts_date_hour_min"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    hour: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    minute: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # 0 or 30
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    fact_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class RPGCharacter(Base):
    __tablename__ = "rpg_characters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    hero_class: Mapped[str] = mapped_column(String(50), default="knight", nullable=False)  # knight, mage, ranger, etc.
    level: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    xp: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    gold: Mapped[int] = mapped_column(BigInteger, default=150, nullable=False)
    gems: Mapped[int] = mapped_column(Integer, default=10, nullable=False)

    # Base attributes
    strength: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    agility: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    intelligence: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    vitality: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    stat_points: Mapped[int] = mapped_column(Integer, default=2, server_default="2", nullable=False)

    # Equipment slots: {"weapon": {...}, "armor": {...}, "relic": {...}}
    equipment: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    # Inventory list of item dicts
    inventory: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    # Endgame RPG Progression
    rebirths: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    talent_points: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    talents: Mapped[dict] = mapped_column(JSON, default=dict, server_default="{}", nullable=False)

    # Progress stats
    dungeon_floor: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    dungeon_cleared: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pvp_rating: Mapped[int] = mapped_column(Integer, default=1000, nullable=False)
    pvp_wins: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pvp_losses: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    boss_kills: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pets: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    user: Mapped["User"] = relationship("User")


class StudentBirthday(Base):
    __tablename__ = "student_birthdays"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    birth_day: Mapped[int] = mapped_column(Integer, nullable=False)    # 1..31
    birth_month: Mapped[int] = mapped_column(Integer, nullable=False)  # 1..12


class ClassPoll(Base):
    __tablename__ = "class_polls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    question: Mapped[str] = mapped_column(String(500), nullable=False)
    is_anonymous: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    allow_revote: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_closed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    creator_tg_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Список отправленных сообщений: [{"chat_id": ..., "message_id": ...}]
    dispatched_messages: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    options: Mapped[List["ClassPollOption"]] = relationship("ClassPollOption", back_populates="poll", cascade="all, delete-orphan", order_by="ClassPollOption.order_index")
    votes: Mapped[List["ClassPollVote"]] = relationship("ClassPollVote", back_populates="poll", cascade="all, delete-orphan")


class ClassPollOption(Base):
    __tablename__ = "class_poll_options"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    poll_id: Mapped[int] = mapped_column(Integer, ForeignKey("class_polls.id", ondelete="CASCADE"), nullable=False, index=True)
    option_text: Mapped[str] = mapped_column(String(200), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    poll: Mapped["ClassPoll"] = relationship("ClassPoll", back_populates="options")
    votes: Mapped[List["ClassPollVote"]] = relationship("ClassPollVote", back_populates="option", cascade="all, delete-orphan")


class ClassPollVote(Base):
    __tablename__ = "class_poll_votes"
    __table_args__ = (
        UniqueConstraint("poll_id", "user_tg_id", name="uq_poll_user_vote"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    poll_id: Mapped[int] = mapped_column(Integer, ForeignKey("class_polls.id", ondelete="CASCADE"), nullable=False, index=True)
    option_id: Mapped[int] = mapped_column(Integer, ForeignKey("class_poll_options.id", ondelete="CASCADE"), nullable=False, index=True)
    user_tg_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    voted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    poll: Mapped["ClassPoll"] = relationship("ClassPoll", back_populates="votes")
    option: Mapped["ClassPollOption"] = relationship("ClassPollOption", back_populates="votes")
