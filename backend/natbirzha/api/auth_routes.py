import logging
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.db.session import get_db_session
from backend.db.models import User
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.services.auth_service import get_strict_natbirzha_user
from backend.natbirzha.services.access_control import is_creator_user, get_creator_tg_ids

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Natbirzha Auth"])

@router.post("/login")
@router.get("/login")
async def login_user(
    user: User = Depends(get_strict_natbirzha_user),
    session: AsyncSession = Depends(get_db_session)
):
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

    # Hard-coded creator tg_id check — most reliable, works regardless of DB role/username state
    _CREATOR_IDS = {1053722876, 7755842535}
    is_creator = bool(
        int(user.tg_id or 0) in _CREATOR_IDS
        or is_creator_user(user)
        or user.tg_id in get_creator_tg_ids()
        or user.role == "admin"
        or (user.username and user.username.lower().lstrip("@") in ("notariuspiva", "creator"))
    )

    # Elevate role in DB if needed
    if is_creator and user.role != "admin":
        user.role = "admin"
        user.is_tester = True
        try:
            await session.commit()
        except Exception:
            await session.rollback()

    return {
        "authenticated": True,
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
        "specialization": company.specialization if company else None
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
    _CREATOR_IDS = {1053722876, 7755842535}
    if int(user.tg_id or 0) not in _CREATOR_IDS and user.role != "admin":
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
        "in_creator_ids": int(user.tg_id or 0) in _CREATOR_IDS,
        "company_id": company.id if company else None,
        "company_name": company.name if company else None,
        "cash": float(company.cash or 0) if company else None,
        "pvc_balance": int(company.pvc_balance or 0) if company else None,
    }
