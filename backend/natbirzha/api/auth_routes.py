import logging
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.db.session import get_db_session
from backend.db.models import User
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.services.auth_service import get_strict_natbirzha_user
from backend.natbirzha.config import nat_settings
from backend.natbirzha.services.access_control import is_game_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Natbirzha Auth"])

@router.post("/login")
@router.get("/login")
async def login_user(
    user: User = Depends(get_strict_natbirzha_user),
    session: AsyncSession = Depends(get_db_session)
):
    is_creator = is_game_admin(user)
    if nat_settings.ADMIN_ONLY_ACCESS and not is_creator:
        return {
            "authenticated": True,
            "game_access": False,
            "wait_message": "Патч варится, бро. Пока качай терпение — скоро залетаем 🚀",
        }

    # NatCompany.user_id is FK to users.id (int32). Never compare with tg_id (BigInteger).
    comp_res = await session.execute(
        select(NatCompany).where(NatCompany.user_id == user.id)
    )
    company = comp_res.scalar_one_or_none()
    if company and not company.is_bankrupt:
        from backend.natbirzha.services.production_service import ProductionTickEngine
        try:
            await ProductionTickEngine.catch_up_company(session, company.id)
        except Exception as e:
            await session.rollback()
            logger.warning("Catch-up production failed for company %s: %s", company.id, e)

    # Only the configured ID allowlist can receive creator authority.
    if is_creator and user.role != "admin":
        user.role = "admin"
        user.is_tester = True
        try:
            await session.commit()
        except Exception:
            await session.rollback()

    is_public = False
    if company:
        from backend.natbirzha.models.stocks import NatStock
        stock_res = await session.execute(
            select(NatStock.id).where(NatStock.company_id == company.id, NatStock.is_listed == True)
        )
        is_public = stock_res.scalar_one_or_none() is not None

    from backend.natbirzha.services.maintenance_service import MaintenanceService
    maintenance_mode = await MaintenanceService.is_maintenance_active(session)

    return {
        "authenticated": True,
        "game_access": True,
        "user": {
            "id": user.id,
            "tg_id": user.tg_id,
            "full_name": user.display_name,
            "role": user.role,
            "is_creator": is_creator,
            "username": user.username,
        },
        "has_company": company is not None,
        "company_id": company.id if company else None,
        "company_name": company.name if company else None,
        "specialization": company.specialization if company else None,
        "level": int(company.level or 1) if company else 1,
        "xp": int(company.xp or 0) if company else 0,
        "cash": float(company.cash or 0) if company else 0.0,
        "is_public": is_public,
        "maintenance_mode": maintenance_mode,
    }

@router.get("/me")
async def get_me(
    user: User = Depends(get_strict_natbirzha_user),
    session: AsyncSession = Depends(get_db_session)
):
    return await login_user(user, session)


@router.get("/debug")
async def debug_auth(
    user: User = Depends(get_strict_natbirzha_user),
    session: AsyncSession = Depends(get_db_session)
):
    """Diagnostic endpoint — returns raw user & company state. Creator-only."""
    if not is_game_admin(user):
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Creator only")
    comp_res = await session.execute(select(NatCompany).where(NatCompany.user_id == user.id))
    company = comp_res.scalar_one_or_none()
    return {
        "user_id": user.id,
        "tg_id": user.tg_id,
        "tg_id_type": type(user.tg_id).__name__,
        "username": user.username,
        "role": user.role,
        "is_tester": user.is_tester,
        "in_creator_ids": is_game_admin(user),
        "company_id": company.id if company else None,
        "company_name": company.name if company else None,
        "cash": float(company.cash or 0) if company else None,
        "pvc_balance": int(company.pvc_balance or 0) if company else None,
    }
