import re
from typing import Optional, List, Tuple
from backend.config import settings
from backend.db.models import User


def is_admin(user: User | None, tg_id: int) -> bool:
    if settings.ADMIN_ID and tg_id == settings.ADMIN_ID:
        return True
    return user is not None and user.role == "admin"


def parse_schedule_text(text: str) -> List[Tuple[int, str]]:
    """
    Универсальный и максимально толерантный парсер расписания.
    Не привязан к оформлению:
    - списком с новой строки (с номерами или без)
    - через запятую: Алгебра, Физика, Литература
    - через точку с запятой: Алгебра; Физика; Химия
    - с дефисами/маркерами: - Алгебра \n - Физика
    - в одну строку с номерами: 1. Алгебра 2. Физика 3. Химия
    - автоматически капитализирует первую букву (алгебра -> Алгебра)
    - автоматически присваивает номера 1, 2, 3... если они не указаны
    """
    if not text:
        return []

    # 1. Если текст написан в одну строку с номерами уроков: "1. Алг 2. Физ 3. Хим"
    text = re.sub(r"(?<=\S)\s+(\d{1,2}[\.\)\-\s])", r"\n\1", text.strip())

    # 2. Разбиваем на элементы: по переносам строк, либо по точке с запятой, либо по запятой
    if "\n" in text:
        raw_items = text.split("\n")
    elif ";" in text:
        raw_items = text.split(";")
    elif "," in text:
        raw_items = text.split(",")
    else:
        raw_items = [text]

    result = []
    current_num = 1

    for raw in raw_items:
        item = raw.strip()
        if not item:
            continue

        # Убираем ведущие маркеры списков (-, *, •, —, –, ▪, >)
        item = re.sub(r"^[\-\*\•\—\–\▪\>\+]+\s*", "", item).strip()

        # Ищем номер урока в начале строки: "1.", "1)", "1 -", "1:", "1 " или просто "1"
        match = re.match(r"^(\d{1,2})[\.\)\-\:\s]+\s*(.+)$", item)
        if match:
            num = int(match.group(1))
            subj_name = match.group(2).strip()
        else:
            num = current_num
            subj_name = item

        # Очищаем название предмета от пунктуации на концах
        subj_name = re.sub(r"^[\.\,\;\:\-\s]+|[\.\,\;\:\-\s]+$", "", subj_name).strip()

        if subj_name:
            # Делаем первую букву заглавной, если ввели со строчной (алгебра -> Алгебра)
            subj_name = subj_name[0].upper() + subj_name[1:]
            result.append((num, subj_name))
            current_num = num + 1

    return result


def parse_bells_text(text: str) -> List[Tuple[int, str, str, int]]:
    """
    Универсальный парсер звонков из текста.
    Принимает форматы:
    1. 08:30 - 09:10
    2. 09:20 - 10:00
    или через запятую / построчно: 08:30-09:10, 09:20-10:00
    Возвращает: list of (lesson_number, start_time, end_time, break_duration)
    """
    if not text:
        return []

    lines = [line.strip() for line in re.split(r"[\n,;]", text) if line.strip()]
    result = []
    current_num = 1
    prev_end_dt = None

    for line in lines:
        time_matches = re.findall(r"(\d{1,2}:\d{2})", line)
        if len(time_matches) >= 2:
            start_t = time_matches[0].zfill(5)
            end_t = time_matches[1].zfill(5)

            m_num = re.match(r"^(\d{1,2})[\.\)\-\:\s]+", line)
            l_num = int(m_num.group(1)) if m_num else current_num

            break_min = 10
            try:
                sh, sm = map(int, start_t.split(":"))
                eh, em = map(int, end_t.split(":"))
                start_min = sh * 60 + sm
                if prev_end_dt is not None and start_min >= prev_end_dt:
                    break_min = start_min - prev_end_dt
                prev_end_dt = eh * 60 + em
            except Exception:
                pass

            result.append((l_num, start_t, end_t, break_min))
            current_num = l_num + 1

    return result
