import logging
import json
from datetime import date, datetime
from typing import Optional, Dict, Any
import httpx
from sqlalchemy import select, delete, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from backend.config import settings, get_today, get_current_date_and_hour, get_current_date_hour_minute
from backend.db.models import DailyFact

logger = logging.getLogger(__name__)

from backend.bot.services.facts_data import (
    ROTATING_TOPICS,
    CURATED_FACTS,
    get_curated_fact_for_slot,
    get_curated_fact_for_hour,
    get_curated_fact_for_date,
)


async def fetch_fact_from_gemini(
    api_key: str,
    target_date: Optional[date] = None,
    target_hour: Optional[int] = None,
    target_minute: Optional[int] = None
) -> Optional[Dict[str, str]]:
    if not api_key or not api_key.strip():
        logger.warning("No Gemini API key provided. Using offline curated facts.")
        return None

    if target_date is None or target_hour is None or target_minute is None:
        today_date, current_hour, current_min_slot = get_current_date_hour_minute()
        if target_date is None:
            target_date = today_date
        if target_hour is None:
            target_hour = current_hour
        if target_minute is None:
            target_minute = current_min_slot
    else:
        target_minute = 30 if target_minute >= 30 else 0

    min_slot = 1 if target_minute >= 30 else 0
    slot = target_hour * 2 + min_slot
    topic = ROTATING_TOPICS[slot % len(ROTATING_TOPICS)]

    # High RPM and daily request limits (Flash-Lite models)
    models_to_try = [
        "gemini-flash-lite-latest",
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite",
        "gemini-3.6-flash",
    ]

    prompt = (
        "Ты рассказываешь простые и удивительные научные факты школьникам. "
        f"Тема: «{topic}». "
        "Сформулируй ОДИН очень короткий, простой и цепляющий факт (строго 1-2 коротких предложения, максимум 25-35 слов). "
        "Пиши максимально понятно, живым языком, без сложных академических терминов и громоздких фраз. "
        "Факт должен легко читаться за несколько секунд и вызывать интерес («Вау, ничего себе!»). "
        "Строго верни валидный JSON без markdown блоков следующего формата: "
        "{\"category\": \"Категория (1-2 слова)\", "
        "\"title\": \"Короткий заголовок (до 4-5 слов)\", "
        "\"fact\": \"Простой и лаконичный текст факта (строго 1-2 предложения).\"} "
    )

    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.85
        }
    }

    async with httpx.AsyncClient(timeout=40.0) as client:
        for model in models_to_try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            try:
                response = await client.post(url, json=payload)
                if response.status_code == 200:
                    data = response.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            raw_text = parts[0].get("text", "").strip()
                            if raw_text.startswith("```json"):
                                raw_text = raw_text[7:]
                            if raw_text.startswith("```"):
                                raw_text = raw_text[3:]
                            if raw_text.endswith("```"):
                                raw_text = raw_text[:-3]
                            parsed = json.loads(raw_text.strip())

                            category = parsed.get("category", "Наука").strip()
                            title = parsed.get("title", "Интересный факт").strip()
                            fact_text = parsed.get("fact", "").strip()

                            if fact_text:
                                logger.info(f"Successfully generated fact via Gemini ({model}) for topic '{topic}': '{title}'")
                                return {
                                    "category": category,
                                    "title": title,
                                    "fact": fact_text
                                }
                else:
                    logger.warning(f"Gemini model {model} returned HTTP {response.status_code}: {response.text[:200]}")
            except Exception as e:
                logger.warning(f"Failed to query Gemini model {model}: {e}")

    return None

async def cleanup_past_facts(
    session: AsyncSession,
    target_date: Optional[date] = None,
    target_hour: Optional[int] = None,
    target_minute: Optional[int] = None,
    keep_fact_id: Optional[int] = None
) -> int:
    """
    Deletes past interesting facts from the database so that only the currently active
    fact is retained in storage. If keep_fact_id is provided, deletes all facts other than keep_fact_id.
    Otherwise, deletes all facts strictly prior to (target_date, target_hour, target_minute).
    """
    try:
        if keep_fact_id is not None:
            stmt = delete(DailyFact).where(DailyFact.id != keep_fact_id)
        else:
            if target_date is None or target_hour is None or target_minute is None:
                c_date, c_hour, c_min = get_current_date_hour_minute()
                target_date = target_date if target_date is not None else c_date
                target_hour = target_hour if target_hour is not None else c_hour
                target_minute = target_minute if target_minute is not None else c_min
            else:
                target_minute = 30 if target_minute >= 30 else 0

            conditions = [
                DailyFact.date < target_date,
                and_(DailyFact.date == target_date, DailyFact.hour < target_hour),
                and_(DailyFact.date == target_date, DailyFact.hour == target_hour, DailyFact.minute < target_minute)
            ]
            stmt = delete(DailyFact).where(or_(*conditions))

        result = await session.execute(stmt)
        await session.commit()
        deleted_count = result.rowcount or 0
        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} past fact(s) from database.")
        return deleted_count
    except Exception as e:
        logger.warning(f"Note on cleanup_past_facts: {e}")
        return 0


async def get_or_generate_slot_fact(
    session: AsyncSession,
    target_date: Optional[date] = None,
    target_hour: Optional[int] = None,
    target_minute: Optional[int] = None
) -> DailyFact:
    """
    Retrieves the interesting fact for the given (date, hour, minute_slot 0/30) from DB,
    or generates a new one via Gemini (with offline fallback) and caches it.
    Guarantees that all students receive the exact same fact during each 30-minute interval,
    while automatically deleting all past facts from storage so only the current fact is kept.
    """
    if target_date is None or target_hour is None or target_minute is None:
        today_date, current_hour, current_min_slot = get_current_date_hour_minute()
        if target_date is None:
            target_date = today_date
        if target_hour is None:
            target_hour = current_hour
        if target_minute is None:
            target_minute = current_min_slot
    else:
        target_minute = 30 if target_minute >= 30 else 0

    # 1. Check if fact already exists for this (date, hour, minute)
    stmt = select(DailyFact).where(
        DailyFact.date == target_date,
        DailyFact.hour == target_hour,
        DailyFact.minute == target_minute
    )
    result = await session.execute(stmt)
    fact = result.scalars().first()
    if fact:
        # Keep only this active fact, clean up any lingering past records
        await cleanup_past_facts(session, target_date, target_hour, target_minute, keep_fact_id=fact.id)
        return fact

    # 2. Try to generate via Gemini API
    fact_data = await fetch_fact_from_gemini(settings.GEMINI_API_KEY, target_date, target_hour, target_minute)

    # 3. Fallback to curated catalog if Gemini failed or is unavailable
    if not fact_data:
        fact_data = get_curated_fact_for_slot(target_date, target_hour, target_minute)

    # 4. Save to DB with collision protection
    new_fact = DailyFact(
        date=target_date,
        hour=target_hour,
        minute=target_minute,
        category=fact_data.get("category", "Наука"),
        title=fact_data.get("title", "Интересный факт"),
        fact_text=fact_data.get("fact", ""),
        created_at=datetime.utcnow()
    )

    try:
        session.add(new_fact)
        await session.commit()
        await session.refresh(new_fact)
        # Automatic cleanup: delete all past facts so only the current fact remains stored in memory/DB
        await cleanup_past_facts(session, target_date, target_hour, target_minute, keep_fact_id=new_fact.id)
        return new_fact
    except IntegrityError:
        # Another process generated and saved the fact concurrently
        await session.rollback()
        stmt = select(DailyFact).where(
            DailyFact.date == target_date,
            DailyFact.hour == target_hour,
            DailyFact.minute == target_minute
        )
        res = await session.execute(stmt)
        existing = res.scalars().first()
        if existing:
            await cleanup_past_facts(session, target_date, target_hour, target_minute, keep_fact_id=existing.id)
            return existing
        return new_fact


async def get_or_generate_hourly_fact(
    session: AsyncSession,
    target_date: Optional[date] = None,
    target_hour: Optional[int] = None
) -> DailyFact:
    """Backward-compatible wrapper."""
    return await get_or_generate_slot_fact(session, target_date=target_date, target_hour=target_hour)


async def get_or_generate_daily_fact(session: AsyncSession, target_date: Optional[date] = None) -> DailyFact:
    """Backward-compatible wrapper."""
    return await get_or_generate_slot_fact(session, target_date=target_date)


import html

def format_fact_telegram_message(fact: DailyFact) -> str:
    """Formats an interesting fact into a clean, safe HTML message for Telegram."""
    cat = html.escape(fact.category)
    title = html.escape(fact.title)
    text = html.escape(fact.fact_text)
    return (
        "💡 <b>Интересный факт</b>\n"
        f"🏷 <b>{cat}</b> | <i>{title}</i>\n\n"
        f"{text}\n\n"
        "✨ <i>Каждый день — новое открытие!</i>"
    )



