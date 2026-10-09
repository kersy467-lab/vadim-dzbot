from fastapi import APIRouter
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from backend.db.models import User
from backend.db.session import get_db_session

from backend.natbirzha.api.auth_routes import router as auth_router
from backend.natbirzha.api.company_routes import router as company_router
from backend.natbirzha.api.production_routes import router as production_router
from backend.natbirzha.api.market_routes import router as market_router
from backend.natbirzha.api.stock_routes import router as stock_router
from backend.natbirzha.api.military_routes import router as military_router
from backend.natbirzha.api.military_infrastructure_routes import router as military_infrastructure_router
from backend.natbirzha.api.hospital_routes import router as hospital_router
from backend.natbirzha.api.alliance_routes import router as alliance_router
from backend.natbirzha.api.bankruptcy_routes import router as bankruptcy_router
from backend.natbirzha.api.building_routes import router as building_router
from backend.natbirzha.api.creator_routes import router as creator_router
from backend.natbirzha.api.bond_routes import router as bond_router
from backend.natbirzha.api.premium_routes import router as premium_router
from backend.natbirzha.api.instrument_routes import router as instrument_router
from backend.natbirzha.api.leaderboard_routes import router as leaderboard_router
from backend.natbirzha.api.portfolio_routes import router as portfolio_router
from backend.natbirzha.api.finance_routes import router as finance_router
from backend.natbirzha.api.business_routes import router as business_router, company_router as tycoon_company_router
from backend.natbirzha.api.business_asset_routes import router as business_asset_router
from backend.natbirzha.api.auto_upgrade_routes import router as auto_upgrade_router
from backend.natbirzha.api.next_game_routes import router as next_game_router
from backend.natbirzha.api.tax_routes import router as tax_router
from backend.natbirzha.api.state_share_routes import creator_router as state_share_creator_router
from backend.natbirzha.api.state_share_routes import player_router as state_share_player_router
from backend.natbirzha.api.state_credit_routes import router as state_credit_router
from backend.natbirzha.api.creator_credit_routes import router as creator_credit_router
from backend.natbirzha.api.creator_bankruptcy_routes import router as creator_bankruptcy_router
from backend.natbirzha.api.bankruptcy_market_routes import router as bankruptcy_market_router
from backend.natbirzha.api.sabotage_routes import router as sabotage_router
from backend.natbirzha.api.supply_deal_routes import router as supply_deal_router
from backend.natbirzha.api.city_order_routes import router as city_order_router
from backend.natbirzha.api.liquidity_routes import router as liquidity_router
from backend.natbirzha.api.hybrid_routes import router as hybrid_router
from backend.natbirzha.api.joint_factory_routes import router as joint_factory_router
from backend.natbirzha.api.maintenance_routes import router as maintenance_router
from backend.natbirzha.api.company_aid_routes import router as company_aid_router
from backend.natbirzha.api.rebirth_routes import router as rebirth_router
from backend.natbirzha.api.admin_access import require_game_access
from backend.natbirzha.services.auth_service import get_strict_natbirzha_user
from backend.natbirzha.config import nat_settings

def build_natbirzha_router(admin_only: bool | None = None) -> APIRouter:
    """Build the game API with a persisted, administrator-bypassable access gate."""
    default_closed = nat_settings.ADMIN_ONLY_ACCESS if admin_only is None else admin_only
    router = APIRouter(prefix="/natbirzha")
    router.include_router(auth_router)

    async def require_dynamic_game_access(
        user: User = Depends(get_strict_natbirzha_user),
        session: AsyncSession = Depends(get_db_session),
    ) -> User:
        return await require_game_access(user, session, default_closed=default_closed)

    # The gate is always installed so /ban can close the game at runtime even
    # when the launch default is open. The database value overrides the default.
    game_router = APIRouter(dependencies=[Depends(require_dynamic_game_access)])
    for child_router in (
        company_router,
        production_router,
        building_router,
        market_router,
        stock_router,
        military_router,
        military_infrastructure_router,
        hospital_router,
        alliance_router,
        bankruptcy_router,
        creator_router,
        bond_router,
        premium_router,
        instrument_router,
        leaderboard_router,
        portfolio_router,
        finance_router,
        business_router,
        business_asset_router,
        auto_upgrade_router,
        tax_router,
        state_share_creator_router,
        state_share_player_router,
        state_credit_router,
        creator_credit_router,
        creator_bankruptcy_router,
        bankruptcy_market_router,
        supply_deal_router,
        city_order_router,
        liquidity_router,
        hybrid_router,
        joint_factory_router,
        tycoon_company_router,
        sabotage_router,
        company_aid_router,
        rebirth_router,
    ):
        game_router.include_router(child_router)
    router.include_router(game_router)
    # This independent test game keeps its own administrator-only authorization.
    router.include_router(next_game_router)
    # Keep status and admin controls reachable during a tech break. The write
    # endpoints perform their own administrator checks.
    router.include_router(maintenance_router)
    return router


natbirzha_router = build_natbirzha_router(admin_only=nat_settings.ADMIN_ONLY_ACCESS)

__all__ = ["natbirzha_router", "build_natbirzha_router"]
