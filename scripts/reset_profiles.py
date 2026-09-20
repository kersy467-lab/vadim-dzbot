"""Full profile and season reset script for Natbirzha.

Policy:
- Creator (tg_id 1053722876 / ADMIN_ID / admin): 500,000 cash, 200 PVC, 200 NAT
- Testers (is_tester == True): 50,000 cash, 200 PVC, 200 NAT
- Regular players: 50,000 cash, 0 PVC, 0 NAT

Usage:
  python scripts/reset_profiles.py
"""

from __future__ import annotations

import asyncio
import os
import sys

# Ensure repository root is in sys.path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from sqlalchemy import delete, select
from backend.config import settings
from backend.db.models import Base, User
from backend.db.session import async_session_factory, init_db
from backend.natbirzha.config import nat_settings
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.creator import NatCreatorAuditLog, NatStateBond
from backend.natbirzha.models.military import NatTournament
from backend.natbirzha.models.season import NatSeasonResetOperation
from backend.natbirzha.services.access_control import is_creator_user, get_creator_tg_ids
from backend.natbirzha.services.company_service import CompanyService


async def reset_all_profiles() -> dict:
    await init_db()

    creator_tg_id = int(settings.ADMIN_ID) if settings.ADMIN_ID else 1053722876
    stats = {
        "cleared_companies": 0,
        "creator_configured": False,
        "users_updated": 0,
    }

    async with async_session_factory() as session:
        # 1. Ensure creator user exists in User table
        creator_user = await session.scalar(select(User).where(User.tg_id == creator_tg_id))
        if not creator_user:
            creator_user = User(
                tg_id=creator_tg_id,
                username="creator",
                full_name="Создатель",
                role="admin",
                is_tester=True,
            )
            session.add(creator_user)
            await session.flush()
            stats["creator_configured"] = True
            print(f"[OK] Created creator user: id={creator_user.id}, tg_id={creator_tg_id}")
        else:
            creator_user.role = "admin"
            creator_user.is_tester = True
            stats["creator_configured"] = True
            print(f"[OK] Elevated creator user: id={creator_user.id}, tg_id={creator_tg_id}")

        # 2. Get all existing companies
        companies = (await session.scalars(select(NatCompany))).all()
        stats["cleared_companies"] = len(companies)

        # 3. Cleanly reset each company and its assets
        for comp in companies:
            print(f"  Resetting company id={comp.id}, user_id={comp.user_id}, name='{comp.name}'")
            await CompanyService.reset_company_for_user(session, comp.user_id, commit=False)

        # 4. Clear global season events and bonds
        await session.execute(delete(NatTournament))
        await session.execute(delete(NatStateBond))

        # 5. Record reset audit log
        session.add(NatCreatorAuditLog(
            actor_id=creator_tg_id,
            action="SEASON_RESET",
            target_type="natbirzha_season",
            target_id="cli-profile-reset",
            details=f"CLI reset: cleared {len(companies)} companies; starting grants: creator 500k+200pvc, testers 50k+200pvc, players 50k",
        ))

        await session.commit()

    print(f"\n[SUCCESS] Profile reset complete! {stats['cleared_companies']} companies reset.")
    print("When players register or open the Mini App:")
    print(f"  - Creator (tg_id={creator_tg_id}): 500,000 cash, 200 PVC, 200 NAT")
    print("  - Testers: 50,000 cash, 200 PVC, 200 NAT")
    print("  - Regular players: 50,000 cash, 0 PVC, 0 NAT")
    return stats


if __name__ == "__main__":
    asyncio.run(reset_all_profiles())
