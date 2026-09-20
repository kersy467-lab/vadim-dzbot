import logging
from datetime import datetime
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import flag_modified

from backend.db.models import ClassPoll, ClassPollOption, ClassPollVote, User
from backend.db.crud.users import get_active_users

logger = logging.getLogger(__name__)


def generate_progress_bar(percentage: float, total_blocks: int = 10) -> str:
    """Генерирует визуальную шкалу прогресса, например: ██████░░░░"""
    filled = round((percentage / 100.0) * total_blocks)
    filled = max(0, min(total_blocks, filled))
    return "█" * filled + "░" * (total_blocks - filled)


async def create_poll(
    session: AsyncSession,
    question: str,
    options_texts: List[str],
    creator_tg_id: int,
    is_anonymous: bool = False,
    allow_revote: bool = True
) -> ClassPoll:
    """Создает новый опрос класса с вариантами ответов."""
    poll = ClassPoll(
        question=question.strip(),
        is_anonymous=is_anonymous,
        allow_revote=allow_revote,
        is_closed=False,
        creator_tg_id=creator_tg_id,
        created_at=datetime.utcnow(),
        dispatched_messages=[]
    )
    session.add(poll)
    await session.flush()

    for idx, opt_text in enumerate(options_texts, start=1):
        clean_text = opt_text.strip()
        if clean_text:
            opt = ClassPollOption(
                poll_id=poll.id,
                option_text=clean_text,
                order_index=idx
            )
            session.add(opt)

    await session.commit()
    return await get_poll_by_id(session, poll.id)


async def get_poll_by_id(session: AsyncSession, poll_id: int) -> Optional[ClassPoll]:
    """Возвращает опрос со всеми вариантами и голосами."""
    res = await session.execute(
        select(ClassPoll)
        .options(
            selectinload(ClassPoll.options),
            selectinload(ClassPoll.votes)
        )
        .where(ClassPoll.id == poll_id)
    )
    return res.scalars().first()


async def get_active_polls(session: AsyncSession) -> List[ClassPoll]:
    """Возвращает список открытых активных опросов."""
    res = await session.execute(
        select(ClassPoll)
        .options(
            selectinload(ClassPoll.options),
            selectinload(ClassPoll.votes)
        )
        .where(ClassPoll.is_closed == False)
        .order_by(desc(ClassPoll.created_at))
    )
    return list(res.scalars().all())


async def close_poll(session: AsyncSession, poll_id: int) -> Optional[ClassPoll]:
    """Завершает опрос и фиксирует время закрытия."""
    poll = await get_poll_by_id(session, poll_id)
    if poll and not poll.is_closed:
        poll.is_closed = True
        poll.closed_at = datetime.utcnow()
        await session.commit()
    return poll


async def delete_poll(session: AsyncSession, poll_id: int) -> bool:
    """Удаляет опрос из базы данных."""
    poll = await get_poll_by_id(session, poll_id)
    if poll:
        await session.delete(poll)
        await session.commit()
        return True
    return False


async def record_or_update_vote(
    session: AsyncSession,
    poll_id: int,
    option_id: int,
    user_tg_id: int
) -> Tuple[bool, str, Optional[ClassPoll]]:
    """
    Фиксирует или изменяет голос пользователя.
    Возвращает (успех, статус, опрос).
    Статусы: 'closed', 'no_revote', 'already_voted_same', 'revoted', 'voted', 'not_found'
    """
    poll = await get_poll_by_id(session, poll_id)
    if not poll:
        return False, "not_found", None

    if poll.is_closed:
        return False, "closed", poll

    # Проверяем, существует ли такой вариант
    valid_option = any(opt.id == option_id for opt in poll.options)
    if not valid_option:
        return False, "invalid_option", poll

    # Ищем существующий голос
    existing_vote_res = await session.execute(
        select(ClassPollVote).where(
            ClassPollVote.poll_id == poll_id,
            ClassPollVote.user_tg_id == user_tg_id
        )
    )
    existing_vote = existing_vote_res.scalars().first()

    if existing_vote:
        if existing_vote.option_id == option_id:
            return True, "already_voted_same", poll
        if not poll.allow_revote:
            return False, "no_revote", poll

        # Изменяем голос
        existing_vote.option_id = option_id
        existing_vote.voted_at = datetime.utcnow()
        await session.commit()
        updated_poll = await get_poll_by_id(session, poll_id)
        return True, "revoted", updated_poll
    else:
        # Новый голос
        new_vote = ClassPollVote(
            poll_id=poll_id,
            option_id=option_id,
            user_tg_id=user_tg_id,
            voted_at=datetime.utcnow()
        )
        session.add(new_vote)
        await session.commit()
        updated_poll = await get_poll_by_id(session, poll_id)
        return True, "voted", updated_poll


async def get_poll_results_data(session: AsyncSession, poll_id: int) -> Optional[Dict[str, Any]]:
    """Собирает подробную статистику по опросу."""
    poll = await get_poll_by_id(session, poll_id)
    if not poll:
        return None

    # Загружаем пользователей для сопоставления имен при открытом голосовании
    all_users = await get_active_users(session)
    users_by_tg = {u.tg_id: u.display_name for u in all_users}

    votes_res = await session.execute(
        select(ClassPollVote).where(ClassPollVote.poll_id == poll_id)
    )
    votes = list(votes_res.scalars().all())
    total_votes = len(votes)
    options_data = []

    # Группируем голоса по option_id
    votes_by_option: Dict[int, List[ClassPollVote]] = {opt.id: [] for opt in poll.options}
    for v in votes:
        if v.option_id in votes_by_option:
            votes_by_option[v.option_id].append(v)

    for opt in sorted(poll.options, key=lambda x: x.order_index):
        opt_votes = votes_by_option.get(opt.id, [])
        count = len(opt_votes)
        pct = (count / total_votes * 100.0) if total_votes > 0 else 0.0
        bar = generate_progress_bar(pct, total_blocks=10)

        voter_names = []
        if not poll.is_anonymous:
            for v in opt_votes:
                name = users_by_tg.get(v.user_tg_id, f"ID {v.user_tg_id}")
                voter_names.append(name)

        options_data.append({
            "id": opt.id,
            "order_index": opt.order_index,
            "text": opt.option_text,
            "count": count,
            "percentage": pct,
            "bar": bar,
            "voters": voter_names
        })

    return {
        "poll_id": poll.id,
        "question": poll.question,
        "is_anonymous": poll.is_anonymous,
        "allow_revote": poll.allow_revote,
        "is_closed": poll.is_closed,
        "total_votes": total_votes,
        "options": options_data,
        "dispatched_messages": poll.dispatched_messages
    }


async def get_poll_non_voters(session: AsyncSession, poll_id: int) -> List[User]:
    """Возвращает список активных учеников класса, которые еще не проголосовали."""
    poll = await get_poll_by_id(session, poll_id)
    if not poll:
        return []

    votes_res = await session.execute(
        select(ClassPollVote.user_tg_id).where(ClassPollVote.poll_id == poll_id)
    )
    voter_ids = set(votes_res.scalars().all())
    active_users = await get_active_users(session)
    return [u for u in active_users if u.tg_id not in voter_ids]


def format_poll_message_text(results: Dict[str, Any]) -> str:
    """Формирует текст сообщения опроса для чата группы."""
    status_header = "🏁 **ОПРОС ЗАВЕРШЁН**" if results.get("is_closed") else "📊 **ОПРОС КЛАССА**"
    q_text = results.get("question", "")

    lines = [
        f"{status_header}\n",
        f"**«{q_text}»**\n"
    ]

    for opt in results.get("options", []):
        count = opt["count"]
        pct = opt["percentage"]
        bar = opt["bar"]
        lines.append(f"{opt['order_index']}. **{opt['text']}** — `{count} чел.` ({pct:.0f}%)")
        lines.append(f"`{bar}`")

    total = results.get("total_votes", 0)
    anon_str = "Да" if results.get("is_anonymous") else "Нет"
    revote_str = "Разрешено" if results.get("allow_revote") else "Отключено"

    lines.append(f"\n👥 Всего проголосовало: **{total}** чел.")
    lines.append(f"🔒 Анонимный: **{anon_str}** | 🔄 Смена голоса: **{revote_str}**")

    if results.get("is_closed"):
        lines.append("\n_Голосование закрыто администратором. Результаты зафиксированы._")

    return "\n".join(lines)


async def add_dispatched_message(session: AsyncSession, poll_id: int, chat_id: int, message_id: int) -> None:
    """Сохраняет связку chat_id + message_id для последующего авто-редактирования опроса."""
    poll = await get_poll_by_id(session, poll_id)
    if poll:
        msgs = list(poll.dispatched_messages) if poll.dispatched_messages else []
        msgs.append({"chat_id": chat_id, "message_id": message_id})
        poll.dispatched_messages = msgs
        flag_modified(poll, "dispatched_messages")
        await session.commit()
