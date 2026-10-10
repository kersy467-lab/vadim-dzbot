import asyncio

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base, User
import backend.natbirzha.models  # noqa: F401
from backend.db.session import get_db_session
from backend.natbirzha.api.next_game_routes import router as next_game_router
from backend.natbirzha.api.next_game_equity_routes import router as next_game_equity_router
from backend.natbirzha.api.next_game_banking_routes import router as next_game_banking_router
from backend.natbirzha.api.next_game_finance_routes import router as next_game_finance_router
from backend.natbirzha.api.next_game_active_routes import router as next_game_active_router
from backend.natbirzha.api.next_game_competition_routes import router as next_game_competition_router
from backend.natbirzha.config import nat_settings
from backend.natbirzha.models.next_game import NatNextGameCompany
from backend.natbirzha.services.auth_service import get_strict_natbirzha_user


def test_next_game_endpoints_are_admin_only_and_save_a_separate_preview():
    async def check():
        engine = create_async_engine('sqlite+aiosqlite:///:memory:')
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        previous_ids = nat_settings.CREATOR_TG_IDS
        actor = {'user': User(id=1, tg_id=990001, username='player', full_name='Player', role='student')}

        async def db_session():
            async with sessions() as session:
                yield session

        async def current_user():
            return actor['user']

        app = FastAPI()
        app.include_router(next_game_router, prefix='/api/natbirzha')
        app.include_router(next_game_equity_router, prefix='/api/natbirzha')
        app.include_router(next_game_banking_router, prefix='/api/natbirzha')
        app.include_router(next_game_finance_router, prefix='/api/natbirzha')
        app.include_router(next_game_competition_router, prefix='/api/natbirzha')
        app.include_router(next_game_active_router, prefix='/api/natbirzha')
        app.dependency_overrides[get_db_session] = db_session
        app.dependency_overrides[get_strict_natbirzha_user] = current_user
        nat_settings.CREATOR_TG_IDS = '990001'
        try:
            with TestClient(app) as client:
                actor['user'] = User(id=2, tg_id=990002, username='guest', full_name='Guest', role='student')
                assert client.get('/api/natbirzha/next-game/map').status_code == 403
                assert client.get('/api/natbirzha/next-game/active/config').status_code == 403
                assert client.post('/api/natbirzha/next-game/active/start', json={'branch_id': 'ore_mining'}).status_code == 403
                forbidden = client.post('/api/natbirzha/next-game/company', json={'name': 'No Access'})
                assert forbidden.status_code == 403
                assert client.post('/api/natbirzha/next-game/facility/build', json={}).status_code == 403
                assert client.post(
                    '/api/natbirzha/next-game/facility/upgrade',
                    json={'branch_id': 'renewables'},
                ).status_code == 403
                assert client.put(
                    '/api/natbirzha/next-game/branch/advance', json={'branch_id': 'ferrous'}
                ).status_code == 403
                assert client.post(
                    '/api/natbirzha/next-game/market/trade',
                    json={'item_id': 'energy', 'side': 'BUY', 'quantity': 1},
                ).status_code == 403
                assert client.post(
                    '/api/natbirzha/next-game/bank/loan', json={'amount': 5_000},
                ).status_code == 403
                assert client.post('/api/natbirzha/next-game/bank/loan/repay').status_code == 403
                assert client.post(
                    '/api/natbirzha/next-game/bank/deposits',
                    json={'amount': 1_000, 'term_days': 1},
                ).status_code == 403
                assert client.post(
                    '/api/natbirzha/next-game/bank/deposits/1/withdraw',
                ).status_code == 403
                assert client.post('/api/natbirzha/next-game/capital/ipo').status_code == 403
                assert client.post(
                    '/api/natbirzha/next-game/capital/orders',
                    json={'issue_id': 1, 'side': 'BUY', 'shares': 1, 'limit_price': 1},
                ).status_code == 403
                assert client.post(
                    '/api/natbirzha/next-game/capital/dividends',
                    json={'per_share': 0.01},
                ).status_code == 403
                assert client.post(
                    '/api/natbirzha/next-game/banking/accounts',
                    json={'bank_company_id': 1},
                ).status_code == 403
                assert client.post(
                    '/api/natbirzha/next-game/banking/payments',
                    json={'bank_company_id': 1, 'payee_company_id': 1, 'amount': 100},
                ).status_code == 403
                assert client.post(
                    '/api/natbirzha/next-game/banking/loans',
                    json={'bank_company_id': 1, 'amount': 1_000, 'term_days': 7},
                ).status_code == 403
                assert client.post(
                    '/api/natbirzha/next-game/banking/loans/1/repay',
                ).status_code == 403
                assert client.post(
                    '/api/natbirzha/next-game/finance/offers',
                    json={'borrower_company_id': 1, 'principal': 1_000, 'daily_rate_bps': 25, 'term_days': 7},
                ).status_code == 403
                assert client.post('/api/natbirzha/next-game/finance/offers/1/accept').status_code == 403
                assert client.post('/api/natbirzha/next-game/finance/offers/1/cancel').status_code == 403
                assert client.post('/api/natbirzha/next-game/finance/loans/1/repay').status_code == 403
                assert client.get('/api/natbirzha/next-game/competition').status_code == 403

                actor['user'] = User(id=1, tg_id=990001, username='owner', full_name='Owner', role='student')
                created = client.post('/api/natbirzha/next-game/company', json={'name': 'Private Test Corp'})
                assert created.status_code == 200
                sector = client.put('/api/natbirzha/next-game/sector', json={'sector_id': 'bank'})
                branch = client.put('/api/natbirzha/next-game/branch', json={'branch_id': 'corporate'})
                snapshot = client.get('/api/natbirzha/next-game/map')
                assert sector.json()['company']['sector_id'] == 'bank'
                assert branch.json()['company']['branch_path'] == ['corporate']
                assert snapshot.json()['company']['name'] == 'Private Test Corp'
                competition = client.get('/api/natbirzha/next-game/competition')
                assert competition.status_code == 200, competition.text
                assert competition.json()['rankings']['cash']['my_rank']['rank'] == 1

                built = client.post(
                    '/api/natbirzha/next-game/facility/build', json={},
                    headers={'Idempotency-Key': 'next-game-build-1'},
                )
                assert built.status_code == 200
                assert built.json()['facility']['branch_id'] == 'corporate'
                async with sessions() as session:
                    company = await session.scalar(select(NatNextGameCompany).where(
                        NatNextGameCompany.owner_tg_id == 990001
                    ))
                    company.level = 2
                    await session.commit()
                upgrade_body = {'branch_id': 'corporate'}
                upgrade_headers = {'Idempotency-Key': 'next-game-facility-upgrade-1'}
                upgrade = client.post(
                    '/api/natbirzha/next-game/facility/upgrade',
                    json=upgrade_body, headers=upgrade_headers,
                )
                upgrade_replay = client.post(
                    '/api/natbirzha/next-game/facility/upgrade',
                    json=upgrade_body, headers=upgrade_headers,
                )
                assert upgrade.status_code == upgrade_replay.status_code == 200
                assert upgrade.json() == upgrade_replay.json()
                assert upgrade.json()['facility']['level'] == 2
                trade_body = {'item_id': 'energy', 'side': 'BUY', 'quantity': 10}
                headers = {'Idempotency-Key': 'next-game-energy-1'}
                bought = client.post(
                    '/api/natbirzha/next-game/market/trade', json=trade_body, headers=headers,
                )
                replay = client.post(
                    '/api/natbirzha/next-game/market/trade', json=trade_body, headers=headers,
                )
                assert bought.status_code == replay.status_code == 200
                assert bought.json() == replay.json()
                latest = client.get('/api/natbirzha/next-game/map').json()
                assert next(item for item in latest['inventory'] if item['item_id'] == 'energy')['quantity'] == 10
                loan_body = {'amount': 5_000}
                loan_headers = {'Idempotency-Key': 'next-game-bank-loan-1'}
                loan = client.post(
                    '/api/natbirzha/next-game/bank/loan', json=loan_body, headers=loan_headers,
                )
                replay_loan = client.post(
                    '/api/natbirzha/next-game/bank/loan', json=loan_body, headers=loan_headers,
                )
                assert loan.status_code == replay_loan.status_code == 200
                assert loan.json() == replay_loan.json()
                repay_headers = {'Idempotency-Key': 'next-game-bank-repay-1'}
                paid = client.post(
                    '/api/natbirzha/next-game/bank/loan/repay',
                    headers=repay_headers,
                )
                paid_replay = client.post(
                    '/api/natbirzha/next-game/bank/loan/repay', headers=repay_headers,
                )
                assert paid.status_code == 200
                assert paid_replay.status_code == 200
                assert paid.json() == paid_replay.json()
                assert paid.json()['paid_amount'] == 5_050

                # Fund this banking/API fixture after construction and upgrades.
                async with sessions() as session:
                    company = await session.scalar(select(NatNextGameCompany).where(NatNextGameCompany.owner_tg_id == 990001))
                    company.cash += 5000
                    await session.commit()
                deposit_body = {'amount': 1_000, 'term_days': 7}
                deposit_headers = {'Idempotency-Key': 'next-game-bank-deposit-1'}
                deposit = client.post(
                    '/api/natbirzha/next-game/bank/deposits',
                    json=deposit_body, headers=deposit_headers,
                )
                deposit_replay = client.post(
                    '/api/natbirzha/next-game/bank/deposits',
                    json=deposit_body, headers=deposit_headers,
                )
                assert deposit.status_code == deposit_replay.status_code == 200
                assert deposit.json() == deposit_replay.json()
                assert deposit.json()['deposit']['maturity_amount'] == 1_017.5
                assert len(client.get('/api/natbirzha/next-game/map').json()['deposits']) == 1
                async with sessions() as session:
                    company = await session.scalar(select(NatNextGameCompany).where(
                        NatNextGameCompany.owner_tg_id == 990001
                    ))
                    company.level = 5
                    await session.commit()
                ipo_headers = {'Idempotency-Key': 'next-game-ipo-1'}
                ipo = client.post('/api/natbirzha/next-game/capital/ipo', headers=ipo_headers)
                ipo_replay = client.post('/api/natbirzha/next-game/capital/ipo', headers=ipo_headers)
                assert ipo.status_code == ipo_replay.status_code == 200
                assert ipo.json() == ipo_replay.json()
                assert ipo.json()['issue']['float_shares'] == 10_000
                assert client.get('/api/natbirzha/next-game/map').json()['equity']['own_issue']['id'] == ipo.json()['issue']['id']

                # New corporate accounts and transfers remain behind the server-side
                # admin gate and charge a real fee without minting cash.
                nat_settings.CREATOR_TG_IDS = '990001,990002,990003'
                actor['user'] = User(id=2, tg_id=990002, username='payer', full_name='Payer', role='student')
                sender = client.post('/api/natbirzha/next-game/company', json={'name': 'Плательщик'})
                assert sender.status_code == 200
                actor['user'] = User(id=3, tg_id=990003, username='payee', full_name='Payee', role='student')
                receiver = client.post('/api/natbirzha/next-game/company', json={'name': 'Получатель'})
                assert receiver.status_code == 200
                bank_id = created.json()['company']['id']
                account_headers = {'Idempotency-Key': 'next-game-account-1'}
                opened = client.post(
                    '/api/natbirzha/next-game/banking/accounts',
                    json={'bank_company_id': bank_id}, headers=account_headers,
                )
                opened_replay = client.post(
                    '/api/natbirzha/next-game/banking/accounts',
                    json={'bank_company_id': bank_id}, headers=account_headers,
                )
                assert opened.status_code == opened_replay.status_code == 200
                assert opened.json() == opened_replay.json()
                actor['user'] = User(id=2, tg_id=990002, username='payer', full_name='Payer', role='student')
                payer_account = client.post(
                    '/api/natbirzha/next-game/banking/accounts',
                    json={'bank_company_id': bank_id},
                    headers={'Idempotency-Key': 'next-game-account-2'},
                )
                actor['user'] = User(id=3, tg_id=990003, username='payee', full_name='Payee', role='student')
                payee_account = client.post(
                    '/api/natbirzha/next-game/banking/accounts',
                    json={'bank_company_id': bank_id},
                    headers={'Idempotency-Key': 'next-game-account-3'},
                )
                assert payer_account.status_code == payee_account.status_code == 200
                actor['user'] = User(id=2, tg_id=990002, username='payer', full_name='Payer', role='student')
                payment_body = {
                    'bank_company_id': bank_id,
                    'payee_company_id': receiver.json()['company']['id'],
                    'amount': 1_000,
                }
                payment_headers = {'Idempotency-Key': 'next-game-company-payment-1'}
                payment = client.post(
                    '/api/natbirzha/next-game/banking/payments',
                    json=payment_body, headers=payment_headers,
                )
                payment_replay = client.post(
                    '/api/natbirzha/next-game/banking/payments',
                    json=payment_body, headers=payment_headers,
                )
                assert payment.status_code == payment_replay.status_code == 200, (
                    payment.status_code, payment.text,
                    payment_replay.status_code, payment_replay.text,
                )
                assert payment.json() == payment_replay.json()
                assert payment.json()['payment']['fee'] == 9.5
                assert client.get('/api/natbirzha/next-game/map').json()['banking']['payments'][0]['amount'] == 1_000
                loan_headers = {'Idempotency-Key': 'next-game-corporate-loan-1'}
                business_loan = client.post(
                    '/api/natbirzha/next-game/banking/loans',
                    json={'bank_company_id': bank_id, 'amount': 1_000, 'term_days': 7},
                    headers=loan_headers,
                )
                business_loan_replay = client.post(
                    '/api/natbirzha/next-game/banking/loans',
                    json={'bank_company_id': bank_id, 'amount': 1_000, 'term_days': 7},
                    headers=loan_headers,
                )
                assert business_loan.status_code == business_loan_replay.status_code == 200, (
                    business_loan.status_code, business_loan.text,
                )
                assert business_loan.json() == business_loan_replay.json()
                assert business_loan.json()['loan']['maturity_amount'] == 1_035
                repay_headers = {'Idempotency-Key': 'next-game-corporate-loan-repay-1'}
                business_repaid = client.post(
                    f"/api/natbirzha/next-game/banking/loans/{business_loan.json()['loan']['id']}/repay",
                    headers=repay_headers,
                )
                assert business_repaid.status_code == 200, business_repaid.text
                assert business_repaid.json()['paid_amount'] >= 1_005

                direct_offer_body = {
                    'borrower_company_id': receiver.json()['company']['id'],
                    'principal': 1_000,
                    'daily_rate_bps': 25,
                    'term_days': 7,
                }
                direct_offer_headers = {'Idempotency-Key': 'next-game-direct-offer-1'}
                direct_offer = client.post(
                    '/api/natbirzha/next-game/finance/offers',
                    json=direct_offer_body, headers=direct_offer_headers,
                )
                direct_offer_replay = client.post(
                    '/api/natbirzha/next-game/finance/offers',
                    json=direct_offer_body, headers=direct_offer_headers,
                )
                assert direct_offer.status_code == direct_offer_replay.status_code == 200
                assert direct_offer.json() == direct_offer_replay.json()
                actor['user'] = User(id=3, tg_id=990003, username='payee', full_name='Payee', role='student')
                direct_contract_id = direct_offer.json()['contract']['id']
                accepted = client.post(
                    f'/api/natbirzha/next-game/finance/offers/{direct_contract_id}/accept',
                    headers={'Idempotency-Key': 'next-game-direct-accept-1'},
                )
                assert accepted.status_code == 200, accepted.text
                accepted_replay = client.post(
                    f'/api/natbirzha/next-game/finance/offers/{direct_contract_id}/accept',
                    headers={'Idempotency-Key': 'next-game-direct-accept-1'},
                )
                assert accepted_replay.status_code == 200
                assert accepted.json() == accepted_replay.json()
                direct_repay = client.post(
                    f'/api/natbirzha/next-game/finance/loans/{direct_contract_id}/repay',
                    headers={'Idempotency-Key': 'next-game-direct-repay-1'},
                )
                assert direct_repay.status_code == 200, direct_repay.text
        finally:
            nat_settings.CREATOR_TG_IDS = previous_ids
            await engine.dispose()

    asyncio.run(check())
