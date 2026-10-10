"""Minute settlement for the separate administrator preview world."""
import logging
from sqlalchemy import select
from backend.db.session import async_session_factory
from backend.natbirzha.models.next_game import NatNextGameCompany
from backend.natbirzha.models.next_game_bankruptcy import NatNextGameBankruptcy
from backend.natbirzha.services.next_game_service import NextGameService
from backend.natbirzha.services.next_game_bond_service import NextGameBondService
from backend.natbirzha.services.next_game_civic_service import NextGameCivicService
from backend.natbirzha.services.next_game_partnership_settlement import settle_all
from backend.natbirzha.services.next_game_progression_service import NextGameProgressionService

logger = logging.getLogger(__name__)


async def settle_preview_world(session_factory=async_session_factory):
    """Commit each company separately; one bad company cannot stop everyone."""
    async with session_factory() as session:
        owners = list((await session.scalars(select(NatNextGameCompany.owner_tg_id)
            .outerjoin(NatNextGameBankruptcy, NatNextGameBankruptcy.company_id == NatNextGameCompany.id)
            .where(NatNextGameCompany.owner_tg_id > 0,
                (NatNextGameBankruptcy.company_id.is_(None)) |
                (NatNextGameBankruptcy.requires_ack.is_(False)))
            .order_by(NatNextGameCompany.id))).all())
    for owner in owners:
        try:
            async with session_factory() as session:
                await NextGameService.settle_company(session, owner)
                await session.commit()
        except Exception:
            logger.exception("Preview production settlement failed for owner %s", owner)
    try:
        async with session_factory() as session:
            await NextGameBondService.settle_all(session)
            await settle_all(session)
            await NextGameCivicService.tick(session)
            await NextGameProgressionService.sweep_reserve_income(session)
            await session.commit()
    except Exception:
        logger.exception("Preview financial settlement failed")


def register_next_game_jobs(scheduler):
    scheduler.add_job(settle_preview_world, trigger="interval", seconds=60,
        id="natbirzha_next_game_settlement", replace_existing=True,
        max_instances=1, coalesce=True, misfire_grace_time=60)
