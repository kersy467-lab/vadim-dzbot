from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from backend.natbirzha.config import nat_settings, get_game_now
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.military import NatArmy, NatTournament, NatTournamentParticipant
from backend.natbirzha.models.alliances import NatAlliance, NatAllianceMember
from backend.natbirzha.services.army_service import ArmyService
from backend.natbirzha.services.tournament_service import TournamentService

class MilitaryService:
    @staticmethod
    async def recruit_units(
        session: AsyncSession,
        company: NatCompany,
        unit_type: str,
        count: int,
        commit: bool = True,
    ) -> Dict[str, Any]:
        result = await ArmyService.recruit(session, company, unit_type, count)
        if commit:
            await session.commit()
        return result

    @staticmethod
    async def create_alliance(
        session: AsyncSession,
        company: NatCompany,
        name: str
    ) -> Dict[str, Any]:
        """Creates a new alliance with strict max 3 members and creator as LEADER."""
        if company.is_bankrupt:
            raise ValueError("Bankrupt companies cannot create an alliance.")

        clean_name = name.strip()
        if len(clean_name) < 3 or len(clean_name) > 64:
            raise ValueError("Alliance name must be between 3 and 64 characters.")

        existing_name = await session.execute(select(NatAlliance).where(NatAlliance.name == clean_name))
        if existing_name.scalar_one_or_none():
            raise ValueError("Alliance with this name already exists.")

        existing_mem = await session.execute(
            select(NatAllianceMember).where(NatAllianceMember.company_id == company.id)
        )
        if existing_mem.scalar_one_or_none():
            raise ValueError("Company is already in an alliance.")

        now = get_game_now()
        alliance = NatAlliance(
            name=clean_name,
            leader_company_id=company.id,
            member_count=1,
            max_members=nat_settings.ALLIANCE_MAX_MEMBERS,
            total_army_strength=0,
            created_at=now
        )
        session.add(alliance)
        await session.flush()

        member = NatAllianceMember(
            alliance_id=alliance.id,
            company_id=company.id,
            role="LEADER",
            joined_at=now
        )
        session.add(member)
        await session.commit()
        await session.refresh(alliance)
        return {
            "success": True,
            "alliance_id": alliance.id,
            "name": alliance.name,
            "member_count": alliance.member_count,
            "role": "LEADER"
        }

    @staticmethod
    async def leave_alliance(session: AsyncSession, company: NatCompany) -> Dict[str, Any]:
        """Leaves the current alliance. If leader leaves, transfers leadership or disbands."""
        mem_res = await session.execute(
            select(NatAllianceMember).where(NatAllianceMember.company_id == company.id)
        )
        member = mem_res.scalar_one_or_none()
        if not member:
            raise ValueError("Company is not in any alliance.")

        alliance_id = member.alliance_id
        alliance = await session.get(NatAlliance, alliance_id)
        await session.delete(member)
        await session.flush()

        if alliance:
            alliance.member_count = max(0, alliance.member_count - 1)
            next_mem_res = await session.execute(
                select(NatAllianceMember).where(NatAllianceMember.alliance_id == alliance_id)
            )
            remaining_members = next_mem_res.scalars().all()
            if not remaining_members:
                await session.delete(alliance)
            elif alliance.leader_company_id == company.id:
                new_leader = remaining_members[0]
                new_leader.role = "LEADER"
                alliance.leader_company_id = new_leader.company_id

        await session.commit()
        return {"success": True, "left_alliance_id": alliance_id}

    @staticmethod
    async def get_company_alliance(session: AsyncSession, company_id: int) -> Optional[Dict[str, Any]]:
        """Retrieves alliance and member roster for a given company."""
        mem_res = await session.execute(
            select(NatAllianceMember).where(NatAllianceMember.company_id == company_id)
        )
        member = mem_res.scalar_one_or_none()
        if not member:
            return None

        alliance = await session.get(NatAlliance, member.alliance_id)
        if not alliance:
            return None

        members_res = await session.execute(
            select(NatAllianceMember, NatCompany)
            .join(NatCompany, NatAllianceMember.company_id == NatCompany.id)
            .where(NatAllianceMember.alliance_id == alliance.id)
        )
        members_list = [
            {
                "company_id": c.id,
                "company_name": c.name,
                "role": m.role,
                "joined_at": str(m.joined_at)
            }
            for m, c in members_res.all()
        ]
        return {
            "id": alliance.id,
            "name": alliance.name,
            "leader_company_id": alliance.leader_company_id,
            "member_count": alliance.member_count,
            "max_members": alliance.max_members,
            "my_role": member.role,
            "members": members_list
        }

    @staticmethod
    async def join_alliance(
        session: AsyncSession,
        alliance_id: int,
        company: NatCompany
    ) -> Dict[str, Any]:
        """Strictly enforces maximum 3 members. Rejects 4th candidate."""
        if company.is_bankrupt:
            raise ValueError("Bankrupt companies cannot join an alliance.")

        alliance_res = await session.execute(select(NatAlliance).where(NatAlliance.id == alliance_id))
        alliance = alliance_res.scalar_one_or_none()
        if not alliance:
            raise ValueError("Alliance not found.")

        # Atomic check on member limit
        members_count_res = await session.execute(
            select(func.count(NatAllianceMember.id)).where(NatAllianceMember.alliance_id == alliance.id)
        )
        current_members = members_count_res.scalar() or 0
        if current_members >= nat_settings.ALLIANCE_MAX_MEMBERS:
            raise ValueError(f"Alliance is full. Maximum {nat_settings.ALLIANCE_MAX_MEMBERS} members allowed.")

        # Check if already in an alliance
        existing_mem = await session.execute(
            select(NatAllianceMember).where(NatAllianceMember.company_id == company.id)
        )
        if existing_mem.scalar_one_or_none():
            raise ValueError("Company is already in an alliance.")

        member = NatAllianceMember(
            alliance_id=alliance.id,
            company_id=company.id,
            role="MEMBER",
            joined_at=get_game_now()
        )
        session.add(member)
        alliance.member_count = current_members + 1
        await session.commit()
        return {"success": True, "alliance_id": alliance.id, "member_count": alliance.member_count}

    @staticmethod
    async def resolve_tournament(
        session: AsyncSession, tournament_id: int, commit: bool = True
    ) -> Dict[str, Any]:
        result = await TournamentService.resolve(
            session, tournament_id, now=get_game_now(), force=True
        )
        if commit:
            await session.commit()
        return result
