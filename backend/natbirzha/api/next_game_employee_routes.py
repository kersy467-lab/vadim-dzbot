"""NATBIRZHA 2.0 employee inventory and PVC cases."""

from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import User
from backend.db.session import get_db_session
from backend.natbirzha.api.creator_auth import get_current_creator
from backend.natbirzha.api.next_game_mutation import mutate
from backend.natbirzha.services.next_game_employee_service import NextGameEmployeeService

router = APIRouter(prefix="/next-game/employees", tags=["Next Game Employees"])


@router.get("")
async def employees(
    admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
):
    result = await NextGameEmployeeService.snapshot(session, int(admin.tg_id))
    await session.commit()
    return result


@router.post("/cases/open")
async def open_case(
    key: str | None = Header(None, alias="Idempotency-Key"),
    admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
):
    return await mutate(
        session, admin, key, "/next-game/employees/cases/open", {},
        lambda: NextGameEmployeeService.open_case(session, int(admin.tg_id)),
    )


@router.delete("/{employee_id}")
async def delete_employee(
    employee_id: int,
    key: str | None = Header(None, alias="Idempotency-Key"),
    admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
):
    payload = {"employee_id": employee_id}
    return await mutate(
        session, admin, key, "/next-game/employees/delete", payload,
        lambda: NextGameEmployeeService.delete_employee(
            session, int(admin.tg_id), employee_id,
        ),
    )


__all__ = ["router", "employees", "open_case", "delete_employee"]
