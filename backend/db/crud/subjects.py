from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import Subject


async def get_all_subjects(session: AsyncSession) -> List[Subject]:
    result = await session.execute(select(Subject).order_by(Subject.name))
    return list(result.scalars().all())


async def get_subject_by_id(session: AsyncSession, subject_id: int) -> Optional[Subject]:
    result = await session.execute(select(Subject).where(Subject.id == subject_id))
    return result.scalar_one_or_none()


async def get_subject_by_name(session: AsyncSession, name: str) -> Optional[Subject]:
    clean_name = name.strip()
    result = await session.execute(
        select(Subject).where(Subject.name.ilike(clean_name))
    )
    return result.scalar_one_or_none()


async def create_subject(
    session: AsyncSession,
    name: str,
    teacher_name: Optional[str] = None
) -> Subject:
    subject = Subject(name=name.strip(), teacher_name=teacher_name)
    session.add(subject)
    await session.commit()
    await session.refresh(subject)
    return subject


async def get_or_create_subject(session: AsyncSession, name: str) -> Subject:
    clean_name = name.strip()
    subj = await get_subject_by_name(session, clean_name)
    if not subj:
        subj = await create_subject(session, name=clean_name)
    return subj


async def delete_subject(session: AsyncSession, subject_id: int) -> bool:
    subject = await get_subject_by_id(session, subject_id)
    if subject:
        await session.delete(subject)
        await session.commit()
        return True
    return False
