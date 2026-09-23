from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
from backend.config import settings

def get_main_keyboard(is_admin: bool = False, user_id: int | None = None, is_tester: bool = False) -> ReplyKeyboardMarkup:
    kb = []
    
    # Buttons to open Telegram Mini App with explicit user ID attachment (Telegram requires HTTPS for WebAppInfo)
    url = settings.WEBAPP_URL
    app_buttons = []
    if url and url.startswith("https://"):
        if user_id:
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}tg_user_id={user_id}"

        webapp_btn = KeyboardButton(
            text="📱 Mini App 11 «Б»",
            web_app=WebAppInfo(url=url)
        )
        app_buttons.append(webapp_btn)

    # Natbirzha is in closed beta testing (only available to testers and admins)
    if is_admin or is_tester:
        nat_url = f"{settings.BASE_URL.rstrip('/')}/app/natbirzha"
        if user_id:
            separator = "&" if "?" in nat_url else "?"
            nat_url = f"{nat_url}{separator}tg_user_id={user_id}"
        if nat_url.startswith("https://"):
            nat_btn = KeyboardButton(
                text="📈 НАТБИРЖА (Beta)",
                web_app=WebAppInfo(url=nat_url)
            )
            app_buttons.append(nat_btn)
        else:
            app_buttons.append(KeyboardButton(text="📈 НАТБИРЖА (Beta)"))

    if app_buttons:
        kb.append(app_buttons)

    kb.extend([
        [
            KeyboardButton(text="📅 Расписание"),
            KeyboardButton(text="📚 Домашка")
        ],
        [
            KeyboardButton(text="🔔 Звонки"),
            KeyboardButton(text="🧹 График дежурств")
        ],
        [
            KeyboardButton(text="🎂 Дни рождения"),
            KeyboardButton(text="💡 Интересный факт")
        ],
        [
            KeyboardButton(text="⏳ Сейчас"),
            KeyboardButton(text="☀️ До лета осталось")
        ]
    ])

    bottom_row = []
    if is_admin:
        bottom_row.append(KeyboardButton(text="👑 Панель управления"))
    bottom_row.append(KeyboardButton(text="⚙️ Настройки"))
    kb.append(bottom_row)

    return ReplyKeyboardMarkup(
        keyboard=kb,
        resize_keyboard=True,
        input_field_placeholder="11 «Б» Класс • Выберите раздел..."
    )


def get_arena_keyboard(user_id: int | None = None) -> ReplyKeyboardMarkup:
    """Minimal public keyboard: only EGE Arena, stats and nickname."""
    rows = []
    url = settings.WEBAPP_URL
    if url and url.startswith("https://"):
        sep = "&" if "?" in url else "?"
        params = ["tab=ege"]
        if user_id:
            params.append(f"tg_user_id={user_id}")
        arena_url = url + sep + "&".join(params)
        rows.append([KeyboardButton(text="🎓 ЕГЭ Арена", web_app=WebAppInfo(url=arena_url))])
    else:
        rows.append([KeyboardButton(text="🎓 ЕГЭ Арена")])
    rows.append([KeyboardButton(text="📊 Моя статистика"), KeyboardButton(text="✏️ Сменить ник")])
    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        input_field_placeholder="ЕГЭ Арена • Дуэли и рейтинг",
    )
