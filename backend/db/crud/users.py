from typing import List, Optional
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import User, GroupChat, UserHomeworkStatus


async def get_user_by_tg_id(session: AsyncSession, tg_id: int) -> Optional[User]:
    result = await session.execute(select(User).where(User.tg_id == tg_id))
    return result.scalar_one_or_none()


async def create_user(
    session: AsyncSession,
    tg_id: int,
    full_name: str,
    username: Optional[str] = None,
    role: str = "pending",
    is_tester: bool = False,
    is_classmate: bool = False
) -> User:
    user = User(
        tg_id=tg_id, full_name=full_name, username=username,
        role=role, is_tester=is_tester, is_classmate=is_classmate
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def update_user_role(session: AsyncSession, tg_id: int, role: str) -> Optional[User]:
    user = await get_user_by_tg_id(session, tg_id)
    if user:
        user.role = role
        await session.commit()
        await session.refresh(user)
    return user


async def update_user_name_and_role(
    session: AsyncSession,
    tg_id: int,
    custom_name: Optional[str] = None,
    role: str = "student"
) -> Optional[User]:
    user = await get_user_by_tg_id(session, tg_id)
    if user:
        user.role = role
        if custom_name is not None and custom_name.strip():
            user.custom_name = custom_name.strip()
        await session.commit()
        await session.refresh(user)
    return user


async def update_user_custom_name(
    session: AsyncSession,
    tg_id: int,
    custom_name: str
) -> Optional[User]:
    user = await get_user_by_tg_id(session, tg_id)
    if user:
        user.custom_name = custom_name.strip()
        await session.commit()
        await session.refresh(user)
    return user


async def update_user_tester_status(
    session: AsyncSession,
    tg_id: int,
    is_tester: bool
) -> Optional[User]:
    user = await get_user_by_tg_id(session, tg_id)
    if user:
        user.is_tester = is_tester
        await session.commit()
        await session.refresh(user)
    return user



async def get_pending_users(session: AsyncSession) -> List[User]:
    result = await session.execute(select(User).where(User.role == "pending").order_by(User.created_at))
    return list(result.scalars().all())


async def get_active_users(session: AsyncSession) -> List[User]:
    result = await session.execute(
        select(User).where(
            User.role.in_(["student", "admin"]),
            User.tg_id > 0
        ).order_by(User.full_name)
    )
    return list(result.scalars().all())


async def get_admin_users(session: AsyncSession) -> List[User]:
    """Возвращает всех пользователей с ролью администратора (admin)"""
    result = await session.execute(
        select(User).where(User.role == "admin").order_by(User.full_name)
    )
    return list(result.scalars().all())


async def get_notifiable_users(session: AsyncSession) -> List[User]:
    result = await session.execute(
        select(User).where(
            User.role.in_(["student", "admin"]),
            User.tg_id > 0,
            User.notifications_enabled == True
        )
    )
    return list(result.scalars().all())


async def toggle_user_notifications(session: AsyncSession, tg_id: int) -> Optional[bool]:
    user = await get_user_by_tg_id(session, tg_id)
    if user:
        user.notifications_enabled = not user.notifications_enabled
        await session.commit()
        return user.notifications_enabled
    return None


async def get_all_users(session: AsyncSession) -> List[User]:
    """Возвращает всех пользователей бота"""
    result = await session.execute(select(User).order_by(User.full_name))
    return list(result.scalars().all())


async def delete_user(session: AsyncSession, tg_id: int) -> bool:
    """Удаляет пользователя по tg_id и очищает его связанные данные (статусы ДЗ)"""
    user = await get_user_by_tg_id(session, tg_id)
    if not user:
        return False
    await session.execute(delete(UserHomeworkStatus).where(UserHomeworkStatus.user_id == user.id))
    await session.execute(delete(User).where(User.id == user.id))
    await session.commit()
    return True


# ----------------- GROUP CHATS -----------------

async def get_group_chat_by_id(session: AsyncSession, chat_id: int) -> Optional[GroupChat]:
    result = await session.execute(select(GroupChat).where(GroupChat.chat_id == chat_id))
    return result.scalar_one_or_none()


async def create_or_update_group_chat(
    session: AsyncSession,
    chat_id: int,
    title: str,
    chat_type: str = "group",
    added_by: Optional[int] = None,
    role: str = "pending"
) -> Optional[GroupChat]:
    if chat_type not in ["group", "supergroup"]:
        return None
    chat = await get_group_chat_by_id(session, chat_id)
    if chat:
        chat.title = title
        chat.chat_type = chat_type
        if added_by:
            chat.added_by = added_by
    else:
        chat = GroupChat(
            chat_id=chat_id,
            title=title,
            chat_type=chat_type,
            added_by=added_by,
            role=role
        )
        session.add(chat)
    await session.commit()
    await session.refresh(chat)
    return chat


async def update_group_chat_role(session: AsyncSession, chat_id: int, role: str) -> Optional[GroupChat]:
    chat = await get_group_chat_by_id(session, chat_id)
    if chat:
        chat.role = role
        await session.commit()
        await session.refresh(chat)
    return chat


async def get_approved_group_chats(session: AsyncSession) -> List[GroupChat]:
    result = await session.execute(
        select(GroupChat).where(
            GroupChat.role == "approved",
            GroupChat.chat_type.in_(["group", "supergroup"]),
            GroupChat.notifications_enabled == True
        )
    )
    return list(result.scalars().all())


async def get_pending_group_chats(session: AsyncSession) -> List[GroupChat]:
    result = await session.execute(
        select(GroupChat).where(
            GroupChat.role == "pending",
            GroupChat.chat_type.in_(["group", "supergroup"])
        ).order_by(GroupChat.created_at)
    )
    return list(result.scalars().all())


async def update_group_chat_topic(
    session: AsyncSession,
    chat_id: int,
    topic_type: str,
    thread_id: Optional[int]
) -> Optional[GroupChat]:
    chat = await get_group_chat_by_id(session, chat_id)
    if not chat:
        return None
    if topic_type == "hw":
        chat.topic_hw_id = thread_id
    elif topic_type == "schedule":
        chat.topic_schedule_id = thread_id
    elif topic_type == "duty":
        chat.topic_duty_id = thread_id
    elif topic_type == "announcements":
        chat.topic_announcements_id = thread_id
    elif topic_type == "clear":
        chat.topic_hw_id = None
        chat.topic_schedule_id = None
        chat.topic_duty_id = None
        chat.topic_announcements_id = None
    await session.commit()
    await session.refresh(chat)
    return chat


async def get_user_by_username(session: AsyncSession, username: str) -> Optional[User]:
    """Find user by username (case-insensitive, strips leading @)."""
    from sqlalchemy import func
    clean_uname = username.lstrip("@").strip().lower()
    if not clean_uname:
        return None
    result = await session.execute(
        select(User).where(func.lower(User.username) == clean_uname)
    )
    return result.scalar_one_or_none()


async def toggle_user_canteen_reminder(session: AsyncSession, tg_id: int) -> bool:
    user = await get_user_by_tg_id(session, tg_id)
    if not user:
        return False
    user.canteen_reminder_enabled = not bool(getattr(user, "canteen_reminder_enabled", False))
    await session.commit()
    await session.refresh(user)
    return user.canteen_reminder_enabled


async def toggle_user_currency_ecosystem(session: AsyncSession, tg_id: int) -> bool:
    user = await get_user_by_tg_id(session, tg_id)
    if not user:
        return False
    user.currency_ecosystem_enabled = not bool(getattr(user, "currency_ecosystem_enabled", False))
    await session.commit()
    await session.refresh(user)
    return user.currency_ecosystem_enabled


async def get_canteen_reminder_users(session: AsyncSession) -> List[User]:
    """Return all active students/admins with canteen_reminder_enabled = True and notifications_enabled = True."""
    result = await session.execute(
        select(User).where(
            User.role.in_(["student", "admin"]),
            User.tg_id > 0,
            User.notifications_enabled == True,
            User.canteen_reminder_enabled == True
        )
    )
    return list(result.scalars().all())


async def perform_user_work(session: AsyncSession, tg_id: int, reward: int = 75) -> tuple[bool, int, str]:
    """
    Execute /work command for a user.
    Returns (success, current_balance, message).
    Work can be done only once per calendar day (using get_today()).
    """
    from backend.config import get_today
    user = await get_user_by_tg_id(session, tg_id)
    if not user:
        return False, 0, "Пользователь не найден в базе данных."

    if not bool(getattr(user, "currency_ecosystem_enabled", False)):
        return False, 0, "Игровая экосистема валюты выключена в настройках."

    today = get_today()
    if user.last_work_date == today:
        return False, user.coins or 0, "Вы уже работали сегодня! Приходите завтра за следующей сменой."

    user.coins = min((user.coins or 0) + reward, MAX_COINS)
    user.last_work_date = today
    await session.commit()
    await session.refresh(user)
    return True, user.coins, f"Отличная работа! Вы заработали +{reward} 🪙 монет."


MAX_COINS = 9_000_000_000_000_000  # 9 quadrillion (safely within JS MAX_SAFE_INTEGER and SQL BIGINT)


async def add_user_coins(session: AsyncSession, tg_id: int, amount: int) -> Optional[int]:
    """Add or deduct coins for a user. Returns new balance or None if user not found/insufficient funds."""
    user = await get_user_by_tg_id(session, tg_id)
    if not user:
        return None
    current = user.coins or 0
    if current + amount < 0:
        return None  # Insufficient funds
    user.coins = min(current + amount, MAX_COINS)
    await session.commit()
    await session.refresh(user)
    return user.coins


async def get_currency_leaderboard(session: AsyncSession, limit: int = 20) -> List[dict]:
    """Get top richest students who have currency_ecosystem_enabled = True."""
    result = await session.execute(
        select(User)
        .where(
            User.role.in_(["student", "admin"]),
            User.tg_id > 0,
            User.currency_ecosystem_enabled == True
        )
        .order_by(User.coins.desc())
        .limit(limit)
    )
    users = result.scalars().all()
    leaderboard = []
    for idx, u in enumerate(users, start=1):
        leaderboard.append({
            "rank": idx,
            "tg_id": u.tg_id,
            "name": u.display_name,
            "username": u.username,
            "coins": u.coins or 0
        })
    return leaderboard


