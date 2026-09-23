import logging
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_natbirzha_webapp_url, settings
from backend.db.models import User
from backend.natbirzha.services.access_control import is_creator_identity
from backend.natbirzha.services.company_service import CompanyService

logger = logging.getLogger(__name__)

router = Router(name="natbirzha_router")


def get_natbirzha_app_url(tg_user_id: int | None = None) -> str:
    url = get_natbirzha_webapp_url(settings.BASE_URL)
    if tg_user_id:
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}tg_user_id={tg_user_id}"
    return url


@router.message(Command("natbirzha"))
@router.message(F.text == "📈 НАТБИРЖА (Beta)")
async def cmd_natbirzha(message: Message, db_session: AsyncSession, current_user: User | None = None):
    if not message.from_user:
        return
    user_id = message.from_user.id
    username = message.from_user.username

    is_tester_or_admin = bool(
        (current_user and (getattr(current_user, "is_tester", False) or current_user.role == "admin"))
        or (settings.ADMIN_ID and user_id == settings.ADMIN_ID)
        or is_creator_identity(user_id, username)
    )

    if not is_tester_or_admin:
        await message.answer(
            "🔒 <b>Игра «НАТБИРЖА» находится в закрытом бета-тестировании</b>\n\n"
            "Доступ открыт только для утверждённых бета-тестеров 11 «Б». Ожидайте официального релиза!",
            parse_mode="HTML"
        )
        return

    app_url = get_natbirzha_app_url(user_id)

    # Check if user already has a company
    company = await CompanyService.get_by_owner_id(db_session, user_id)

    kb_rows = []

    # WebApp button if HTTPS or Base URL is available
    if app_url.startswith("https://"):
        kb_rows.append([
            InlineKeyboardButton(
                text="🚀 Открыть НАТБИРЖУ (Mini App)",
                web_app=WebAppInfo(url=app_url)
            )
        ])
    else:
        kb_rows.append([
            InlineKeyboardButton(
                text="🌐 Открыть НАТБИРЖУ в браузере",
                url=app_url
            )
        ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=kb_rows)

    if company:
        nav = await CompanyService.calculate_nav(db_session, company)
        text = (
            f"📈 <b>НАТБИРЖА • 11 «Б»</b>\n\n"
            f"🏢 <b>Ваша корпорация:</b> <code>[{company.ticker}]</code> {company.name}\n"
            f"🎯 <b>Специализация:</b> {company.specialization}\n"
            f"💵 <b>Счёт компании:</b> <code>{company.cash:,.2f}</code> cash\n"
            f"💎 <b>Оценка (NAV):</b> <code>{nav:,.2f}</code> cash\n"
            f"⭐ <b>Уровень / XP:</b> Lvl {company.level} ({company.xp} XP)\n\n"
            f"<i>Управляйте заводами, торгуйте ресурсами, выпускайте акции и побеждайте в турнирах!</i>"
        )
    else:
        text = (
            f"📈 <b>НАТБИРЖА • 11 «Б»</b>\n\n"
            f"Добро пожаловать в масштабную экономическую мультиплеерную стратегию класса!\n\n"
            f"✨ <b>Что вас ждёт:</b>\n"
            f"• Основание собственной корпорации и выбор отрасли (металлургия, энергетика, нефтегаз, агро, IT...)\n"
            f"• Заводы, технологические цепочки и рецепты производства\n"
            f"• Биржа ресурсов: лимитные ордера, стакан цен и NPC-скупка\n"
            f"• Выход на IPO, торговля акциями и выплата дивидендов\n"
            f"• Армия, альянсы и 72-часовые турниры за NAT-фонд!\n\n"
            f"Нажмите кнопку ниже, чтобы основать свою корпорацию:"
        )

    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
