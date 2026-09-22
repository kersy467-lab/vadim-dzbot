import os
import sys
import asyncio
from datetime import date, datetime, timedelta
import pytest

sys.path.insert(0, os.path.abspath("."))
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./data/test_custom_sched.db"
os.environ["BOT_TOKEN"] = "1234567890:ABCdefFakeTestToken"

from backend.config import settings
settings.DATABASE_URL = "sqlite+aiosqlite:///./data/test_custom_sched.db"

from backend.db.session import engine, async_session_factory
from backend.db.models import Base
from backend.db.crud import (
    create_user,
    get_user_custom_schedules,
    save_user_custom_schedules,
    get_due_custom_schedules,
    mark_schedule_sent,
)
from backend.bot.handlers.custom_schedule import TIME_REGEX, format_summary_text
from backend.bot.services.custom_schedule import send_due_custom_schedules
from aiogram.exceptions import TelegramForbiddenError, TelegramAPIError


class MockBot:
    def __init__(self):
        self.sent_photos = []
        self.sent_messages = []
        self.fail_user_id = None
        self.forbidden_user_id = None

    async def send_photo(self, chat_id, photo, caption=None, parse_mode=None):
        if self.forbidden_user_id and chat_id == self.forbidden_user_id:
            raise TelegramForbiddenError(method="sendPhoto", message="Forbidden: bot was blocked by the user")
        if self.fail_user_id and chat_id == self.fail_user_id:
            raise TelegramAPIError(method="sendPhoto", message="Network timeout")
        self.sent_photos.append({"chat_id": chat_id, "photo": photo, "caption": caption})
        return True

    async def send_message(self, chat_id, text, parse_mode=None):
        if self.forbidden_user_id and chat_id == self.forbidden_user_id:
            raise TelegramForbiddenError(method="sendMessage", message="Forbidden: bot was blocked by the user")
        if self.fail_user_id and chat_id == self.fail_user_id:
            raise TelegramAPIError(method="sendMessage", message="Network timeout")
        self.sent_messages.append({"chat_id": chat_id, "text": text})
        return True


def test_time_validation_regex():
    """Проверка валидации формата времени HH:MM."""
    # Корректные времена
    assert TIME_REGEX.match("00:00") is not None
    assert TIME_REGEX.match("08:00") is not None
    assert TIME_REGEX.match("15:30") is not None
    assert TIME_REGEX.match("21:45") is not None
    assert TIME_REGEX.match("23:59") is not None

    # Некорректные времена
    assert TIME_REGEX.match("24:00") is None
    assert TIME_REGEX.match("25:90") is None
    assert TIME_REGEX.match("15.30") is None
    assert TIME_REGEX.match("abc") is None
    assert TIME_REGEX.match("8:30") is None  # Должен быть двузначный час (08:30)
    assert TIME_REGEX.match("12:60") is None
    assert TIME_REGEX.match("") is None


def test_custom_schedule_crud_and_overwriting():
    """Проверка сохранения, перезаписи и чтения персонального расписания."""
    async def _run():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

        test_tg_id = 11223344
        async with async_session_factory() as session:
            user = await create_user(session, tg_id=test_tg_id, full_name="Иван Тестовый")

            # Первичное сохранение расписания
            days_data_v1 = {
                1: {"is_active": True, "content_type": "photo", "file_id": "photo_id_mon", "notification_time": "15:30"},
                2: {"is_active": False},
                3: {"is_active": True, "content_type": "text", "text_content": "1. Алгебра\n2. Физика", "notification_time": "16:00"},
                4: {"is_active": True, "content_type": "photo", "file_id": "photo_id_thu", "notification_time": "15:30"},
                5: {"is_active": True, "content_type": "text", "text_content": "1. Химия\n2. Биология", "notification_time": "14:30"},
                6: {"is_active": False},
                7: {"is_active": False},
            }

            saved_v1 = await save_user_custom_schedules(session, test_tg_id, user.id, days_data_v1)
            assert len(saved_v1) == 7

            # Проверяем чтение из БД
            loaded = await get_user_custom_schedules(session, test_tg_id)
            assert len(loaded) == 7
            mon = loaded[0]
            assert mon.day_of_week == 1
            assert mon.is_active is True
            assert mon.content_type == "photo"
            assert mon.file_id == "photo_id_mon"
            assert mon.notification_time == "15:30"

            tue = loaded[1]
            assert tue.day_of_week == 2
            assert tue.is_active is False

            wed = loaded[2]
            assert wed.day_of_week == 3
            assert wed.is_active is True
            assert wed.content_type == "text"
            assert "Алгебра" in wed.text_content
            assert wed.notification_time == "16:00"

            # Проверяем формат сводки
            summary = format_summary_text(loaded)
            assert "Понедельник" in summary and "15:30" in summary and "фото" in summary
            assert "Вторник" in summary and "отключено" in summary
            assert "Среда" in summary and "16:00" in summary and "текст" in summary

            # Повторная настройка: перезапись расписания новым
            days_data_v2 = {
                1: {"is_active": False},
                2: {"is_active": True, "content_type": "text", "text_content": "Новое расписание вторника", "notification_time": "08:15"},
                3: {"is_active": False},
                4: {"is_active": False},
                5: {"is_active": False},
                6: {"is_active": False},
                7: {"is_active": False},
            }

            saved_v2 = await save_user_custom_schedules(session, test_tg_id, user.id, days_data_v2)
            assert len(saved_v2) == 7

            # Проверяем, что нет дублирующихся записей (ровно 7 строк)
            reloaded = await get_user_custom_schedules(session, test_tg_id)
            assert len(reloaded) == 7
            assert reloaded[0].is_active is False
            assert reloaded[1].is_active is True
            assert reloaded[1].notification_time == "08:15"

    asyncio.run(_run())


def test_due_schedules_query_and_anti_duplicate():
    """Проверка выборки расписаний по времени и защита от дубликатов через last_sent_date."""
    async def _run():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

        test_tg_id = 99887766
        today = date(2026, 9, 21)  # Понедельник (day 1)

        async with async_session_factory() as session:
            user = await create_user(session, tg_id=test_tg_id, full_name="Тест Расписания")

            days_data = {
                1: {"is_active": True, "content_type": "photo", "file_id": "mon_pic", "notification_time": "15:30"},
                2: {"is_active": True, "content_type": "text", "text_content": "Tue text", "notification_time": "15:30"},
            }
            await save_user_custom_schedules(session, test_tg_id, user.id, days_data)

            # 1. Понедельник 15:30 -> должен найтись
            due = await get_due_custom_schedules(session, day_of_week=1, current_time="15:30", current_date=today)
            assert len(due) == 1
            assert due[0].user_tg_id == test_tg_id

            # 2. Неверное время 15:31 -> не должен найтись
            due_diff_time = await get_due_custom_schedules(session, day_of_week=1, current_time="15:31", current_date=today)
            assert len(due_diff_time) == 0

            # 3. Неверный день недели (вторник вместо понедельника в 15:30)
            due_diff_day = await get_due_custom_schedules(session, day_of_week=2, current_time="15:30", current_date=today)
            assert len(due_diff_day) == 1
            assert due_diff_day[0].day_of_week == 2

            # 4. Отмечаем отправленным сегодня
            await mark_schedule_sent(session, due[0].id, today)

            # 5. Повторный опрос в ту же минуту -> пусто (защита от дубликатов)
            due_after_sent = await get_due_custom_schedules(session, day_of_week=1, current_time="15:30", current_date=today)
            assert len(due_after_sent) == 0

            # 6. На следующий понедельник (через 7 дней) -> снова готов к отправке
            next_monday = today + timedelta(days=7)
            due_next_week = await get_due_custom_schedules(session, day_of_week=1, current_time="15:30", current_date=next_monday)
            assert len(due_next_week) == 1

    asyncio.run(_run())


def test_send_due_custom_schedules_service():
    """Проверка сервиса отправки персонального расписания с моком бота."""
    async def _run():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

        from backend.config import settings
        import zoneinfo
        tz = zoneinfo.ZoneInfo(settings.TIMEZONE)
        now = datetime.now(tz)
        cur_time = f"{now.hour:02d}:{now.minute:02d}"
        cur_dow = now.date().isoweekday()

        async with async_session_factory() as session:
            # Создаем трех пользователей с расписанием на текущую минуту
            u1 = await create_user(session, tg_id=5001, full_name="User Photo")
            u2 = await create_user(session, tg_id=5002, full_name="User Text")
            u3 = await create_user(session, tg_id=5003, full_name="User Blocked")

            days_u1 = {cur_dow: {"is_active": True, "content_type": "photo", "file_id": "file_123", "notification_time": cur_time}}
            days_u2 = {cur_dow: {"is_active": True, "content_type": "text", "text_content": "Уроки: 1, 2, 3", "notification_time": cur_time}}
            days_u3 = {cur_dow: {"is_active": True, "content_type": "photo", "file_id": "file_blocked", "notification_time": cur_time}}

            await save_user_custom_schedules(session, 5001, u1.id, days_u1)
            await save_user_custom_schedules(session, 5002, u2.id, days_u2)
            await save_user_custom_schedules(session, 5003, u3.id, days_u3)

        mock_bot = MockBot()
        mock_bot.forbidden_user_id = 5003  # Имитируем блокировку бота пользователем 5003

        sent_count = await send_due_custom_schedules(mock_bot)
        assert sent_count == 3  # 2 доставлено, 1 помечен отправленным из-за блокировки

        assert len(mock_bot.sent_photos) == 1
        assert mock_bot.sent_photos[0]["chat_id"] == 5001
        assert mock_bot.sent_photos[0]["photo"] == "file_123"

        assert len(mock_bot.sent_messages) == 1
        assert mock_bot.sent_messages[0]["chat_id"] == 5002
        assert "Уроки: 1, 2, 3" in mock_bot.sent_messages[0]["text"]

        # Повторный вызов в ту же минуту -> 0 (защита от повторной отправки)
        sent_second_time = await send_due_custom_schedules(mock_bot)
        assert sent_second_time == 0

    asyncio.run(_run())


def test_fsm_wizard_scenario():
    """Тестирование полного FSM сценария: понедельник..воскресенье, фото, текст, тире, неверное время, сохранение."""
    async def _run():
        from aiogram.fsm.storage.memory import MemoryStorage
        from aiogram.fsm.storage.base import StorageKey
        from aiogram.fsm.context import FSMContext
        from aiogram.types import User as TgUser, Chat, PhotoSize
        from backend.bot.handlers.custom_schedule import (
            CustomScheduleStates,
            handle_schedule_content,
            handle_schedule_time,
            cancel_custom_schedule,
        )

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

        storage = MemoryStorage()
        tg_user_id = 77889900
        storage_key = StorageKey(bot_id=1, chat_id=tg_user_id, user_id=tg_user_id)
        fsm_ctx = FSMContext(storage=storage, key=storage_key)

        async with async_session_factory() as session:
            user = await create_user(session, tg_id=tg_user_id, full_name="FSM Tester")

            class MockTgMessage:
                def __init__(self, text=None, photo=None):
                    self.text = text
                    self.photo = photo
                    self.from_user = TgUser(id=tg_user_id, is_bot=False, first_name="FSM")
                    self.chat = Chat(id=tg_user_id, type="private")
                    self.answers = []

                async def answer(self, text, reply_markup=None, parse_mode=None):
                    self.answers.append(text)
                    return self

            # Старт визарда: день 1 (Понедельник), ожидаем контент
            await fsm_ctx.set_state(CustomScheduleStates.waiting_for_content)
            await fsm_ctx.update_data(current_day=1, schedule_data={})

            # Шаг 1: День 1 (Понедельник) -> Отправка фото
            photo_obj = [PhotoSize(file_id="p_mon_file_id", file_unique_id="u1", width=100, height=100)]
            m1 = MockTgMessage(photo=photo_obj)
            await handle_schedule_content(m1, fsm_ctx, session, user)
            assert await fsm_ctx.get_state() == CustomScheduleStates.waiting_for_time.state
            assert "Во сколько отправлять" in m1.answers[-1]

            # Некорректное время: "25:90"
            m1_invalid = MockTgMessage(text="25:90")
            await handle_schedule_time(m1_invalid, fsm_ctx, session, user)
            assert await fsm_ctx.get_state() == CustomScheduleStates.waiting_for_time.state
            assert "Некорректное время" in m1_invalid.answers[-1]

            # Корректное время: "15:30"
            m1_valid = MockTgMessage(text="15:30")
            await handle_schedule_time(m1_valid, fsm_ctx, session, user)
            assert await fsm_ctx.get_state() == CustomScheduleStates.waiting_for_content.state
            data = await fsm_ctx.get_data()
            assert data["current_day"] == 2
            assert data["schedule_data"][1]["is_active"] is True
            assert data["schedule_data"][1]["content_type"] == "photo"

            # Шаг 2: День 2 (Вторник) -> Отправка текста
            m2 = MockTgMessage(text="1. Геометрия\n2. Русский")
            await handle_schedule_content(m2, fsm_ctx, session, user)
            assert await fsm_ctx.get_state() == CustomScheduleStates.waiting_for_time.state

            # Ввод времени для вторника: "08:45"
            m2_time = MockTgMessage(text="08:45")
            await handle_schedule_time(m2_time, fsm_ctx, session, user)
            assert (await fsm_ctx.get_data())["current_day"] == 3

            # Шаг 3: День 3 (Среда) -> Отправка "-" (пропуск)
            m3 = MockTgMessage(text="-")
            await handle_schedule_content(m3, fsm_ctx, session, user)
            data = await fsm_ctx.get_data()
            assert data["current_day"] == 4
            assert data["schedule_data"][3]["is_active"] is False

            # Шаг 4: День 4 (Четверг) -> Фото и время 14:00
            photo_thu = [PhotoSize(file_id="p_thu_file_id", file_unique_id="u2", width=100, height=100)]
            m4 = MockTgMessage(photo=photo_thu)
            await handle_schedule_content(m4, fsm_ctx, session, user)
            m4_time = MockTgMessage(text="14:00")
            await handle_schedule_time(m4_time, fsm_ctx, session, user)
            assert (await fsm_ctx.get_data())["current_day"] == 5

            # Шаг 5: День 5 (Пятница) -> "-"
            m5 = MockTgMessage(text="-")
            await handle_schedule_content(m5, fsm_ctx, session, user)
            assert (await fsm_ctx.get_data())["current_day"] == 6

            # Шаг 6: День 6 (Суббота) -> "-"
            m6 = MockTgMessage(text="-")
            await handle_schedule_content(m6, fsm_ctx, session, user)
            assert (await fsm_ctx.get_data())["current_day"] == 7

            # Шаг 7: День 7 (Воскресенье) -> "-" -> Завершение!
            m7 = MockTgMessage(text="-")
            await handle_schedule_content(m7, fsm_ctx, session, user)

            # Проверяем, что FSM состояние сброшено (завершено)
            assert await fsm_ctx.get_state() is None
            assert "Расписание сохранено" in m7.answers[-1]

            # Проверяем записи в базе данных
            db_schedules = await get_user_custom_schedules(session, tg_user_id)
            assert len(db_schedules) == 7

            # Понедельник: фото 15:30
            assert db_schedules[0].is_active is True
            assert db_schedules[0].content_type == "photo"
            assert db_schedules[0].file_id == "p_mon_file_id"
            assert db_schedules[0].notification_time == "15:30"

            # Вторник: текст 08:45
            assert db_schedules[1].is_active is True
            assert db_schedules[1].content_type == "text"
            assert "Геометрия" in db_schedules[1].text_content
            assert db_schedules[1].notification_time == "08:45"

            # Среда: отключено
            assert db_schedules[2].is_active is False

            # Четверг: фото 14:00
            assert db_schedules[3].is_active is True
            assert db_schedules[3].file_id == "p_thu_file_id"
            assert db_schedules[3].notification_time == "14:00"

            # Пт, Сб, Вс: отключены
            assert db_schedules[4].is_active is False
            assert db_schedules[5].is_active is False
            assert db_schedules[6].is_active is False

            # Проверка отмены
            await fsm_ctx.set_state(CustomScheduleStates.waiting_for_content)
            class MockCallback:
                def __init__(self):
                    self.message = MockTgMessage()
                    self.answered = False
                async def answer(self, text=None):
                    self.answered = True
            cb = MockCallback()
            await cancel_custom_schedule(cb, fsm_ctx)
            assert await fsm_ctx.get_state() is None
            assert "отменена" in cb.message.answers[-1]

    asyncio.run(_run())


if __name__ == "__main__":
    test_time_validation_regex()
    test_custom_schedule_crud_and_overwriting()
    test_due_schedules_query_and_anti_duplicate()
    test_send_due_custom_schedules_service()
    test_fsm_wizard_scenario()
    print("=== ALL CUSTOM SCHEDULE UNIT TESTS PASSED SUCCESSFULLY! ===")
