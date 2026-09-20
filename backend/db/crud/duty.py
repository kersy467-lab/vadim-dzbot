from datetime import date
from typing import List, Optional, Tuple
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import DutyGroup, ClassSetting


async def get_all_duty_groups(session: AsyncSession) -> List[DutyGroup]:
    from backend.config import get_today
    today = get_today()
    if today > date(2026, 9, 30):
        # После конца сентября группа 0 удаляется из списка (не люди в ней, а сама группа)
        await session.execute(delete(DutyGroup).where(DutyGroup.group_number == 0))
        await session.commit()
    else:
        # В сентябре проверяем наличие группы 0
        res0 = await session.execute(select(DutyGroup).where(DutyGroup.group_number == 0))
        if not res0.scalar_one_or_none():
            g0 = DutyGroup(group_number=0, name="Группа 0", members="Состав не назначен")
            session.add(g0)
            await session.commit()

    result = await session.execute(select(DutyGroup).order_by(DutyGroup.group_number))
    return list(result.scalars().all())


async def get_duty_group_by_number(session: AsyncSession, group_number: int) -> Optional[DutyGroup]:
    result = await session.execute(select(DutyGroup).where(DutyGroup.group_number == group_number))
    return result.scalar_one_or_none()


async def create_or_update_duty_group(
    session: AsyncSession,
    group_number: int,
    name: str,
    members: str,
    member_ids: Optional[list] = None
) -> DutyGroup:
    group = await get_duty_group_by_number(session, group_number)
    if group:
        group.name = name
        group.members = members
        if member_ids is not None:
            group.member_ids = member_ids
    else:
        group = DutyGroup(
            group_number=group_number,
            name=name,
            members=members,
            member_ids=member_ids or []
        )
        session.add(group)
    await session.commit()
    await session.refresh(group)
    return group



async def get_class_setting(session: AsyncSession, key: str) -> Optional[str]:
    result = await session.execute(select(ClassSetting).where(ClassSetting.key == key))
    setting = result.scalar_one_or_none()
    return setting.value if setting else None


async def set_class_setting(session: AsyncSession, key: str, value: str):
    result = await session.execute(select(ClassSetting).where(ClassSetting.key == key))
    setting = result.scalar_one_or_none()
    if setting:
        setting.value = value
    else:
        setting = ClassSetting(key=key, value=value)
        session.add(setting)
    await session.commit()


async def get_current_duty_info(session: AsyncSession) -> Tuple[Optional[DutyGroup], List[DutyGroup]]:
    all_groups = await get_all_duty_groups(session)
    if not all_groups:
        return None, []

    manual_val = await get_class_setting(session, "current_duty_group")
    if manual_val and manual_val.isdigit():
        target_num = int(manual_val)
        for g in all_groups:
            if g.group_number == target_num:
                return g, all_groups

    from backend.config import get_today
    today = get_today()

    # Сентябрь 2026: весь месяц дежурит группа 0
    if today.year == 2026 and today.month == 9:
        for g in all_groups:
            if g.group_number == 0:
                return g, all_groups
        return all_groups[0], all_groups

    # Ротация 1-5 начинается с октября (2026-10-01)
    rotating_groups = [g for g in all_groups if g.group_number != 0]
    if not rotating_groups:
        return all_groups[0], all_groups

    rotating_groups.sort(key=lambda x: x.group_number)

    oct_start = date(2026, 10, 1)
    if today < oct_start:
        return rotating_groups[0], all_groups

    # 1-4 октября 2026: первая неделя (Группа 1)
    # Начиная с 5 октября 2026 (понедельник) — еженедельная ротация (каждый понедельник смена)
    if today < date(2026, 10, 5):
        week_idx = 0
    else:
        diff_days = (today - date(2026, 10, 5)).days
        week_idx = (diff_days // 7) + 1

    active_group = rotating_groups[week_idx % len(rotating_groups)]
    return active_group, all_groups


async def clear_all_duty_members(session: AsyncSession):
    """Очищает списки дежурных во всех группах"""
    groups = await get_all_duty_groups(session)
    for g in groups:
        g.members = "Состав не назначен"
        g.member_ids = []
    await session.commit()


async def get_users_in_duty_group(session: AsyncSession, group: DutyGroup) -> List["User"]:
    """
    Находит зарегистрированных пользователей, входящих в состав дежурной группы
    (по member_ids или по сопоставлению имени/фамилии).
    """
    from backend.db.crud.users import get_active_users
    from backend.db.models import User

    all_active = await get_active_users(session)
    result = []
    found_ids = set()

    # 1. По точному списку member_ids (tg_id или id)
    member_ids = group.member_ids or []
    if member_ids:
        for u in all_active:
            if u.tg_id in member_ids or u.id in member_ids:
                if u.id not in found_ids:
                    result.append(u)
                    found_ids.add(u.id)
        if result:
            return result

    # 2. Фоллбэк: сопоставление по имени/фамилии в строке members
    members_text = (group.members or "").lower()
    if members_text and members_text != "состав не назначен":
        for u in all_active:
            name1 = (u.custom_name or "").lower()
            name2 = (u.full_name or "").lower()
            parts1 = [p.strip() for p in name1.split() if len(p.strip()) > 2]
            parts2 = [p.strip() for p in name2.split() if len(p.strip()) > 2]

            matched = False
            if name1 and (name1 in members_text or any(p in members_text for p in parts1)):
                matched = True
            elif name2 and (name2 in members_text or any(p in members_text for p in parts2)):
                matched = True

            if matched and u.id not in found_ids:
                result.append(u)
                found_ids.add(u.id)

    return result

