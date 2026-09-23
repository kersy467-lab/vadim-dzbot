"""API recovery when a concurrent state-share mutation wins the same key."""

from types import SimpleNamespace

import pytest
from sqlalchemy.exc import IntegrityError

from backend.natbirzha.api import state_share_routes as routes
from backend.natbirzha.services.idempotency_service import IdempotencyService
from backend.natbirzha.services.state_share_service import StateShareService


@pytest.mark.parametrize("operation", ["issue", "buy", "sell"])
def test_duplicate_state_share_request_replays_after_integrity_error(
    operation: str, monkeypatch
) -> None:
    async def run() -> None:
        winner = {"success": True, "winner": operation}
        company = SimpleNamespace(id=10, user_id=20, cash=100)

        class FakeSession:
            rollbacks = 0

            async def rollback(self):
                self.rollbacks += 1
                company.cash = 100

        session = FakeSession()
        replay_checks = 0

        async def check_or_conflict(_cls, _session, _user, _endpoint, _key, _payload):
            nonlocal replay_checks
            replay_checks += 1
            return None if replay_checks == 1 else (200, winner)

        async def fail_after_losing_cash(_cls, *args, **kwargs):
            company.cash -= 25
            raise IntegrityError("state share operation", {}, RuntimeError("duplicate key"))

        monkeypatch.setattr(
            IdempotencyService, "check_or_conflict", classmethod(check_or_conflict)
        )
        monkeypatch.setattr(StateShareService, "issue", classmethod(fail_after_losing_cash))
        monkeypatch.setattr(StateShareService, "buy", classmethod(fail_after_losing_cash))
        monkeypatch.setattr(StateShareService, "sell", classmethod(fail_after_losing_cash))

        if operation == "issue":
            result = await routes.issue_state_shares(
                routes.IssueStateShareRequest(
                    title="Race issue",
                    purpose="duplicate request recovery",
                    volume=10,
                    issue_price=5,
                    projected_annual_profit=100,
                    dividend_rate_pct=10,
                ),
                idempotency_key="same-key",
                creator=SimpleNamespace(id=3, tg_id=30),
                session=session,
            )
        else:
            endpoint = routes.buy_state_shares if operation == "buy" else routes.sell_state_shares
            result = await endpoint(
                share_id=4,
                request=routes.StateShareTradeRequest(quantity=5),
                idempotency_key="same-key",
                company=company,
                session=session,
            )

        assert result == winner
        assert replay_checks == 2
        assert session.rollbacks == 1
        assert company.cash == 100

    import asyncio

    asyncio.run(run())


if __name__ == "__main__":
    pytest.main([__file__, "-q"])
